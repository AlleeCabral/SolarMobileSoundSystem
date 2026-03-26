"""
Solar / Battery Mobile Sound System — Tkinter UI
=================================================
Run:  python app.py
"""

from __future__ import annotations
import sys, os
import tkinter as tk
from tkinter import ttk, scrolledtext

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from rules_engine import (
    SystemConfig, Load, Battery, Inverter,
    Panel, PVArray, Controller, Environment, Policy,
    RuleEngine,
)
from simulate import builtin_example


MAX_LOADS = 10   # total load slots (5 built-in + 5 user-added)

# ─────────────────────────────────────────────
# Flowchart node definitions & failure mapping
# ─────────────────────────────────────────────
_FC_NODES = [
    {
        "id":    "solar",
        "title": "Solar Array",
        "params": [
            ("panel.p_stc_w",            "P_stc W"),
            ("panel.voc_stc",            "Voc STC"),
            ("panel.vmp",                "Vmp"),
            ("panel.beta_voc_pct_per_c", "Beta %/C"),
            ("panel.series_count",       "Series"),
            ("panel.parallel_count",     "Parallel"),
        ],
        "fail_codes": {"voc_cold", "pv_undersized", "vmp_low", "ctrl_current", "ctrl_power"},
    },
    {
        "id":    "ctrl",
        "title": "Charge Controller",
        "params": [
            ("ctrl.type_",        "Type"),
            ("ctrl.pv_max_voc",   "Max Voc V"),
            ("ctrl.charge_a_max", "Max chg A"),
            ("ctrl.batt_v",       "Batt V"),
            ("ctrl.vmp_margin",   "Vmp margin"),
        ],
        "fail_codes": {"voc_cold", "ctrl_batt_v", "vmp_low", "ctrl_current", "ctrl_power"},
    },
    {
        "id":    "battery",
        "title": "Battery",
        "params": [
            ("batt.chemistry",      "Chemistry"),
            ("batt.v_nom",          "Voltage V"),
            ("batt.ah",             "Ah each"),
            ("batt.parallel_count", "# parallel"),
            ("batt.dod_max",        "Max DoD"),
            ("batt.bms_cont_a",     "BMS cont A"),
            ("batt.bms_peak_a",     "BMS peak A"),
        ],
        "fail_codes": {"battery_ah", "bms_cont", "bms_peak", "ctrl_batt_v"},
    },
    {
        "id":    "inverter",
        "title": "Inverter",
        "params": [
            ("inv.v_in",      "V in"),
            ("inv.p_cont_w",  "P cont W"),
            ("inv.p_surge_w", "P surge W"),
            ("inv.eff",       "Efficiency"),
            ("inv.idle_w",    "Idle W"),
        ],
        "fail_codes": {"inverter_voltage", "inverter_cont", "inverter_surge", "no_inverter"},
    },
    {
        "id":    "loads",
        "title": "Loads",
        "params": [],   # computed dynamically from load vars
        "fail_codes": set(),
    },
]

# fail_code → param var-keys whose values caused the failure
_FAIL_PARAM_MAP: dict = {
    "battery_ah":       {"batt.ah", "batt.dod_max", "batt.parallel_count"},
    "bms_cont":         {"batt.bms_cont_a", "batt.parallel_count"},
    "bms_peak":         {"batt.bms_peak_a", "batt.parallel_count"},
    "no_inverter":      set(),
    "inverter_voltage": {"inv.v_in"},
    "inverter_cont":    {"inv.p_cont_w"},
    "inverter_surge":   {"inv.p_surge_w"},
    "voc_cold":         {"panel.voc_stc", "panel.beta_voc_pct_per_c",
                         "panel.series_count", "ctrl.pv_max_voc"},
    "ctrl_batt_v":      {"ctrl.batt_v", "batt.v_nom"},
    "vmp_low":          {"panel.vmp", "panel.series_count"},
    "ctrl_current":     {"panel.p_stc_w", "panel.series_count",
                         "panel.parallel_count", "ctrl.charge_a_max"},
    "ctrl_power":       {"panel.p_stc_w", "panel.series_count",
                         "panel.parallel_count", "ctrl.pv_lim_12", "ctrl.pv_lim_24"},
    "pv_undersized":    {"panel.p_stc_w", "panel.series_count",
                         "panel.parallel_count", "env.psh", "env.pv_derate"},
}


# ─────────────────────────────────────────────
# Small helpers
# ─────────────────────────────────────────────
def _add_field(parent, label: str, var: tk.Variable, row: int, width: int = 11):
    tk.Label(parent, text=label, anchor="w").grid(
        row=row, column=0, sticky="w", padx=4, pady=2)
    tk.Entry(parent, textvariable=var, width=width).grid(
        row=row, column=1, sticky="ew", padx=4, pady=2)


def _add_check(parent, label: str, var: tk.BooleanVar, row: int):
    tk.Label(parent, text=label, anchor="w").grid(
        row=row, column=0, sticky="w", padx=4, pady=2)
    tk.Checkbutton(parent, variable=var).grid(
        row=row, column=1, sticky="w", padx=4, pady=2)


# ─────────────────────────────────────────────
# Main application
# ─────────────────────────────────────────────
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Solar Sound System Simulator")
        self.minsize(900, 640)
        self._vars: dict = {}        # key → tk.StringVar / tk.BooleanVar
        self._load_frames: list = []  # LabelFrame refs for load sub-panels
        self._fc_result = None        # last simulation result for flowchart redraws
        self._fc_canvas = None
        self._build_ui()
        self._populate(builtin_example())

    # ─────────────────────────────────────────
    # Variable factory helpers
    # ─────────────────────────────────────────
    def _sv(self, key: str, default="") -> tk.StringVar:
        v = tk.StringVar(value=str(default))
        self._vars[key] = v
        return v

    def _bv(self, key: str, default: bool = True) -> tk.BooleanVar:
        v = tk.BooleanVar(value=default)
        self._vars[key] = v
        return v

    def _lf(self, parent, title: str) -> tk.LabelFrame:
        """Create a titled LabelFrame and pack it."""
        lf = tk.LabelFrame(parent, text=title,
                           font=("TkDefaultFont", 9, "bold"), padx=6, pady=4)
        lf.pack(fill="x", pady=4)
        lf.columnconfigure(1, weight=1)
        return lf

    # ─────────────────────────────────────────
    # UI construction
    # ─────────────────────────────────────────
    def _build_ui(self):
        # ── scrollable panel area ──────────────────────────────────────
        outer = tk.Frame(self)
        outer.pack(fill="both", expand=True)

        canvas = tk.Canvas(outer, borderwidth=0, highlightthickness=0)
        vsb = tk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        inner = tk.Frame(canvas)
        _win = canvas.create_window((0, 0), window=inner, anchor="nw")

        def _resize_inner(e):
            canvas.configure(scrollregion=canvas.bbox("all"))
        inner.bind("<Configure>", _resize_inner)

        def _resize_canvas(e):
            canvas.itemconfig(_win, width=e.width)
        canvas.bind("<Configure>", _resize_canvas)

        canvas.bind_all("<MouseWheel>",
                        lambda e: canvas.yview_scroll(int(-1*(e.delta/120)), "units"))

        # ── 3 columns ──────────────────────────────────────────────────
        inner.columnconfigure(0, weight=1, minsize=220)
        inner.columnconfigure(1, weight=1, minsize=220)
        inner.columnconfigure(2, weight=1, minsize=260)

        col0 = tk.Frame(inner)
        col1 = tk.Frame(inner)
        col2 = tk.Frame(inner)
        col0.grid(row=0, column=0, sticky="nsew", padx=6, pady=6)
        col1.grid(row=0, column=1, sticky="nsew", padx=6, pady=6)
        col2.grid(row=0, column=2, sticky="nsew", padx=6, pady=6)

        self._build_solar_panel(col0)
        self._build_controller(col0)
        self._build_battery(col1)
        self._build_inverter(col1)
        self._build_loads(col2)
        self._build_environment(col2)
        self._build_policy(col2)

        # ── Flowchart canvas ───────────────────────────────────────────
        fc_lf = tk.LabelFrame(
            self,
            text=("System Flowchart   "
                  "[ gray = not yet simulated  |  green = PASS  |  red = FAIL ]"),
            font=("TkDefaultFont", 8), padx=4, pady=4)
        fc_lf.pack(fill="x", padx=10, pady=(4, 2))
        self._fc_canvas = tk.Canvas(
            fc_lf, height=230, bg="white",
            highlightthickness=1, highlightbackground="#cccccc")
        self._fc_canvas.pack(fill="x", expand=True)
        self._fc_canvas.bind(
            "<Configure>",
            lambda e: self.after_idle(lambda: self._redraw_flowchart(self._fc_result)))

        # ── Simulate button ────────────────────────────────────────────
        btn_bar = tk.Frame(self, pady=6)
        btn_bar.pack(fill="x", padx=10)
        tk.Button(
            btn_bar, text="▶   Simulate",
            command=self._simulate,
            font=("TkDefaultFont", 11, "bold"),
            bg="#2d7d46", fg="white",
            activebackground="#1e5c33", activeforeground="white",
            relief="flat", padx=20, pady=8,
        ).pack(fill="x")

        # ── Output text box ─────────────────────────────────────────────
        out_bar = tk.Frame(self)
        out_bar.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        self._out = scrolledtext.ScrolledText(
            out_bar, height=14, font=("Courier", 9),
            state="disabled", wrap="word",
        )
        self._out.pack(fill="both", expand=True)

        self._out.tag_configure("pass",  foreground="#1a7a3c", font=("Courier", 10, "bold"))
        self._out.tag_configure("fail",  foreground="#c0392b", font=("Courier", 10, "bold"))
        self._out.tag_configure("warn",  foreground="#e67e22")
        self._out.tag_configure("error", foreground="#c0392b", font=("Courier", 10, "bold"))
        self._out.tag_configure("head",  font=("Courier", 9, "bold"))

    # ── Panel frames ─────────────────────────────────────────────────
    def _build_solar_panel(self, parent):
        lf = self._lf(parent, "☀  Solar Panel")
        for row, (key, label) in enumerate([
            ("panel.p_stc_w",            "Rated power (W)"),
            ("panel.voc_stc",            "Voc STC (V)"),
            ("panel.vmp",                "Vmp (V)"),
            ("panel.isc",                "Isc (A)"),
            ("panel.imp",                "Imp (A)"),
            ("panel.beta_voc_pct_per_c", "β Voc (%/°C)"),
            ("panel.series_count",       "Series count"),
            ("panel.parallel_count",     "Parallel count"),
        ]):
            _add_field(lf, label, self._sv(key), row)

    def _build_controller(self, parent):
        lf = self._lf(parent, "⚙  Charge Controller")
        for row, (key, label) in enumerate([
            ("ctrl.type_",        "Type (MPPT/PWM)"),
            ("ctrl.pv_max_voc",   "Max PV Voc (V)"),
            ("ctrl.charge_a_max", "Max charge A"),
            ("ctrl.batt_v",       "Batt V (e.g. 12,24)"),
            ("ctrl.pv_lim_12",    "PV limit @ 12 V (W)"),
            ("ctrl.pv_lim_24",    "PV limit @ 24 V (W)"),
            ("ctrl.vmp_margin",   "Vmp margin (V)"),
        ]):
            _add_field(lf, label, self._sv(key), row)

    def _build_battery(self, parent):
        lf = self._lf(parent, "🔋  Battery")
        for row, (key, label) in enumerate([
            ("batt.chemistry",      "Chemistry"),
            ("batt.v_nom",          "Voltage nom (V)"),
            ("batt.ah",             "Capacity Ah (each)"),
            ("batt.dod_max",        "Max DoD (0–1)"),
            ("batt.bms_cont_a",     "BMS cont A (each)"),
            ("batt.bms_peak_a",     "BMS peak A (each)"),
            ("batt.parallel_count", "# batteries (∥)"),
        ]):
            _add_field(lf, label, self._sv(key), row)

    def _build_inverter(self, parent):
        lf = self._lf(parent, "🔌  Inverter")
        for row, (key, label) in enumerate([
            ("inv.v_in",     "DC input (V)"),
            ("inv.p_cont_w", "Cont. power (W)"),
            ("inv.p_surge_w","Surge power (W)"),
            ("inv.eff",      "Efficiency (0–1)"),
            ("inv.idle_w",   "Idle draw (W)"),
        ]):
            _add_field(lf, label, self._sv(key), row)
        _add_check(lf, "Pure sine", self._bv("inv.pure_sine"), row=5)

    def _build_loads(self, parent):
        lf = self._lf(parent, "⚡  Loads")
        # Inner frame for load boxes so the Add button stays pinned below them
        inner = tk.Frame(lf)
        inner.pack(fill="x")
        self._loads_inner = inner

        self._load_frames = []
        self._hidden_loads: set = set()

        for li in range(MAX_LOADS):
            sub = tk.LabelFrame(inner, text=f"Load {li+1}",
                                font=("TkDefaultFont", 8), padx=3, pady=3)
            sub.columnconfigure(1, weight=1)
            self._load_frames.append(sub)

            self._sv(f"load{li}.name")   # LabelFrame title updated in _populate
            for row, (key, label) in enumerate([
                (f"load{li}.power_w",       "Power (W)"),
                (f"load{li}.hours_per_day", "Hours/day"),
                (f"load{li}.load_type",     "Type (AC/DC)"),
                (f"load{li}.surge_w",       "Surge (W)"),
                (f"load{li}.req_v",         "Req. V (DC, blank=any)"),
            ]):
                _add_field(sub, label, self._sv(key), row, width=8)

            # Optional slots (5-9) get a remove button and start hidden
            if li >= 5:
                tk.Button(
                    sub, text="✕ Remove this load",
                    command=lambda l=li: self._remove_load(l),
                    bg="#fde8e8", fg="#c0392b",
                    font=("TkDefaultFont", 7), relief="flat",
                ).grid(row=5, column=0, columnspan=2, sticky="ew", padx=2, pady=2)
                self._hidden_loads.add(li)
            else:
                sub.pack(fill="x", pady=2, padx=2)

        self._add_load_btn = tk.Button(
            lf, text="＋ Add Load",
            command=self._add_load,
            bg="#2d5fa8", fg="white",
            font=("TkDefaultFont", 8, "bold"), relief="flat",
        )
        self._add_load_btn.pack(fill="x", pady=(4, 2), padx=4)

    def _build_environment(self, parent):
        lf = self._lf(parent, "🌤  Environment")
        for row, (key, label) in enumerate([
            ("env.psh",       "Peak sun hours"),
            ("env.t_min_c",   "Min temp (°C)"),
            ("env.pv_derate", "PV derate (0–1)"),
        ]):
            _add_field(lf, label, self._sv(key), row)

    def _build_policy(self, parent):
        lf = self._lf(parent, "📋  Policy")
        for row, (key, label) in enumerate([
            ("policy.autonomy_hours",      "Autonomy (h)"),
            ("policy.energy_margin",       "Energy margin"),
            ("policy.controller_headroom", "Controller headroom"),
            ("policy.fuse_factor",         "Fuse factor"),
        ]):
            _add_field(lf, label, self._sv(key), row)

    # ─────────────────────────────────────────
    # Add / Remove load slots dynamically
    # ─────────────────────────────────────────
    def _add_load(self):
        """Show the next hidden load slot (up to MAX_LOADS)."""
        if not self._hidden_loads:
            return
        li = min(self._hidden_loads)
        self._hidden_loads.discard(li)
        self._load_frames[li].pack(fill="x", pady=2, padx=2)
        if not self._hidden_loads:
            self._add_load_btn.config(state="disabled",
                                     text=f"Max {MAX_LOADS} loads reached")

    def _remove_load(self, li: int):
        """Clear and hide an optional load slot."""
        self._vars[f"load{li}.name"].set("")
        self._vars[f"load{li}.power_w"].set("")
        self._vars[f"load{li}.hours_per_day"].set("")
        self._vars[f"load{li}.load_type"].set("AC")
        self._vars[f"load{li}.surge_w"].set("")
        self._vars[f"load{li}.req_v"].set("")
        self._load_frames[li].config(text=f"Load {li+1}")
        self._load_frames[li].pack_forget()
        self._hidden_loads.add(li)
        self._add_load_btn.config(state="normal", text="＋ Add Load")
    # ─────────────────────────────────────────
    def _populate(self, cfg: SystemConfig):
        p, arr = cfg.pv_array.panel, cfg.pv_array
        self._vars["panel.p_stc_w"].set(p.p_stc_w)
        self._vars["panel.voc_stc"].set(p.voc_stc)
        self._vars["panel.vmp"].set(p.vmp)
        self._vars["panel.isc"].set(p.isc)
        self._vars["panel.imp"].set(p.imp)
        self._vars["panel.beta_voc_pct_per_c"].set(p.beta_voc_pct_per_c)
        self._vars["panel.series_count"].set(arr.series_count)
        self._vars["panel.parallel_count"].set(arr.parallel_count)

        c = cfg.controller
        self._vars["ctrl.type_"].set(c.type_)
        self._vars["ctrl.pv_max_voc"].set(c.pv_max_voc)
        self._vars["ctrl.charge_a_max"].set(c.charge_a_max)
        self._vars["ctrl.batt_v"].set(",".join(str(int(v)) for v in c.battery_voltages_supported))
        self._vars["ctrl.pv_lim_12"].set(c.pv_power_limit_by_batt_v.get(12.0, ""))
        self._vars["ctrl.pv_lim_24"].set(c.pv_power_limit_by_batt_v.get(24.0, ""))
        self._vars["ctrl.vmp_margin"].set(c.requires_vmp_margin_v)

        b = cfg.battery
        self._vars["batt.chemistry"].set(b.chemistry)
        self._vars["batt.v_nom"].set(b.v_nom)
        self._vars["batt.ah"].set(b.ah)
        self._vars["batt.dod_max"].set(b.dod_max)
        self._vars["batt.bms_cont_a"].set(b.bms_cont_a)
        self._vars["batt.bms_peak_a"].set(b.bms_peak_a)
        self._vars["batt.parallel_count"].set(1)  # default single battery

        if cfg.inverter:
            iv = cfg.inverter
            self._vars["inv.v_in"].set(iv.v_in)
            self._vars["inv.p_cont_w"].set(iv.p_cont_w)
            self._vars["inv.p_surge_w"].set(iv.p_surge_w)
            self._vars["inv.eff"].set(iv.eff)
            self._vars["inv.idle_w"].set(iv.idle_w)
            self._vars["inv.pure_sine"].set(iv.pure_sine)

        # Reset optional slots 5-9 (hide them all first)
        for li in range(5, MAX_LOADS):
            if li not in self._hidden_loads:
                self._load_frames[li].pack_forget()
                self._hidden_loads.add(li)
            # Clear their vars
            self._vars[f"load{li}.name"].set("")
            self._vars[f"load{li}.power_w"].set("")
            self._vars[f"load{li}.hours_per_day"].set("")
            self._vars[f"load{li}.load_type"].set("AC")
            self._vars[f"load{li}.surge_w"].set("")
            self._vars[f"load{li}.req_v"].set("")

        for li, load in enumerate(cfg.loads[:MAX_LOADS]):
            self._vars[f"load{li}.name"].set(load.name)
            self._load_frames[li].config(text=load.name)
            self._vars[f"load{li}.power_w"].set(load.power_w)
            self._vars[f"load{li}.hours_per_day"].set(load.hours_per_day)
            self._vars[f"load{li}.load_type"].set(load.load_type)
            self._vars[f"load{li}.surge_w"].set(load.surge_w)
            self._vars[f"load{li}.req_v"].set(
                load.required_voltage if load.required_voltage is not None else "")
            # Show optional slots that have data from cfg
            if li >= 5 and li in self._hidden_loads:
                self._hidden_loads.discard(li)
                self._load_frames[li].pack(fill="x", pady=2, padx=2)

        # Sync Add Load button state
        if self._hidden_loads:
            self._add_load_btn.config(state="normal", text="＋ Add Load")
        else:
            self._add_load_btn.config(state="disabled",
                                     text=f"Max {MAX_LOADS} loads reached")

        e = cfg.environment
        self._vars["env.psh"].set(e.psh)
        self._vars["env.t_min_c"].set(e.t_min_c)
        self._vars["env.pv_derate"].set(e.pv_derate)

        pol = cfg.policy
        self._vars["policy.autonomy_hours"].set(pol.autonomy_hours)
        self._vars["policy.energy_margin"].set(pol.energy_margin)
        self._vars["policy.controller_headroom"].set(pol.controller_headroom)
        self._vars["policy.fuse_factor"].set(pol.fuse_factor)

    # ─────────────────────────────────────────
    # Parse all fields → SystemConfig
    # ─────────────────────────────────────────
    def _parse(self) -> SystemConfig:
        def f(key: str) -> float:
            return float(self._vars[key].get())
        def i(key: str) -> int:
            return int(float(self._vars[key].get()))
        def s(key: str) -> str:
            return self._vars[key].get().strip()
        def b(key: str) -> bool:
            return bool(self._vars[key].get())

        panel = Panel(
            p_stc_w=f("panel.p_stc_w"),
            voc_stc=f("panel.voc_stc"),
            vmp=f("panel.vmp"),
            isc=f("panel.isc"),
            imp=f("panel.imp"),
            beta_voc_pct_per_c=f("panel.beta_voc_pct_per_c"),
        )
        pv_array = PVArray(
            panel=panel,
            series_count=i("panel.series_count"),
            parallel_count=i("panel.parallel_count"),
        )

        batt_v_str = s("ctrl.batt_v")
        batt_voltages = [float(v.strip()) for v in batt_v_str.split(",") if v.strip()]
        pv_limits: dict = {}
        for bv, key in [(12.0, "ctrl.pv_lim_12"), (24.0, "ctrl.pv_lim_24")]:
            raw = s(key)
            if raw:
                pv_limits[bv] = float(raw)

        controller = Controller(
            type_=s("ctrl.type_"),
            battery_voltages_supported=batt_voltages,
            pv_max_voc=f("ctrl.pv_max_voc"),
            charge_a_max=f("ctrl.charge_a_max"),
            pv_power_limit_by_batt_v=pv_limits,
            requires_vmp_margin_v=f("ctrl.vmp_margin"),
        )

        n_batt = max(1, i("batt.parallel_count"))
        battery = Battery(
            chemistry=s("batt.chemistry"),
            v_nom=f("batt.v_nom"),
            ah=f("batt.ah") * n_batt,
            dod_max=f("batt.dod_max"),
            bms_cont_a=f("batt.bms_cont_a") * n_batt,
            bms_peak_a=f("batt.bms_peak_a") * n_batt,
        )

        inv_keys = ["inv.v_in", "inv.p_cont_w", "inv.p_surge_w", "inv.eff", "inv.idle_w"]
        has_inverter = all(s(k) for k in inv_keys)
        inverter = None
        if has_inverter:
            inverter = Inverter(
                v_in=f("inv.v_in"),
                p_cont_w=f("inv.p_cont_w"),
                p_surge_w=f("inv.p_surge_w"),
                eff=f("inv.eff"),
                idle_w=f("inv.idle_w"),
                pure_sine=b("inv.pure_sine"),
            )

        loads = []
        for li in range(MAX_LOADS):
            try:
                pw = float(self._vars[f"load{li}.power_w"].get())
                lt = self._vars[f"load{li}.load_type"].get().strip().upper()
                if pw <= 0 or lt not in ("AC", "DC"):
                    continue
                rv_raw = s(f"load{li}.req_v")
                rv = float(rv_raw) if rv_raw else None
                loads.append(Load(
                    name=s(f"load{li}.name") or f"Load {li+1}",
                    power_w=pw,
                    hours_per_day=f(f"load{li}.hours_per_day"),
                    load_type=lt,
                    surge_w=float(self._vars[f"load{li}.surge_w"].get() or 0),
                    required_voltage=rv,
                ))
            except (ValueError, KeyError):
                continue

        environment = Environment(
            psh=f("env.psh"),
            t_min_c=f("env.t_min_c"),
            pv_derate=f("env.pv_derate"),
        )
        policy = Policy(
            autonomy_hours=f("policy.autonomy_hours"),
            energy_margin=f("policy.energy_margin"),
            controller_headroom=f("policy.controller_headroom"),
            fuse_factor=f("policy.fuse_factor"),
        )

        return SystemConfig(
            loads=loads,
            battery=battery,
            inverter=inverter,
            pv_array=pv_array,
            controller=controller,
            environment=environment,
            policy=policy,
        )

    # ─────────────────────────────────────────
    # Output helpers
    # ─────────────────────────────────────────
    def _write(self, text: str, tag: str = ""):
        self._out.configure(state="normal")
        if tag:
            self._out.insert("end", text, tag)
        else:
            self._out.insert("end", text)
        self._out.configure(state="disabled")

    def _clear(self):
        self._out.configure(state="normal")
        self._out.delete("1.0", "end")
        self._out.configure(state="disabled")

    # ─────────────────────────────────────────
    # Flowchart
    # ─────────────────────────────────────────
    def _redraw_flowchart(self, result=None):
        """
        Draw the real system topology:

          [Solar] -DC-> [Controller] -DC-> [Battery] -DC-> [Inverter] -AC-> [AC Loads]
                                               |
                                           DC direct
                                               |
                                               v
                                          [DC Loads]   (amp etc., wired straight to battery)

        After simulation: failing nodes get a red border; failing parameter
        labels turn red; passing nodes turn green.
        """
        c = self._fc_canvas
        if c is None:
            return
        c.delete("all")
        W = c.winfo_width()
        H = c.winfo_height()
        if W < 40 or H < 40:
            return

        # ── failing sets ──────────────────────────────────────────────────
        failing_nodes: set = set()
        failing_params: set = set()
        if result and result.get("fails"):
            for fail in result["fails"]:
                code = fail["code"]
                for nd in _FC_NODES:
                    if code in nd["fail_codes"]:
                        failing_nodes.add(nd["id"])
                failing_params |= _FAIL_PARAM_MAP.get(code, set())

        simulated = result is not None

        def _col(node_id):
            if not simulated:
                return "#f5f5f5", "#aaaaaa", 1, "#444444"
            if node_id in failing_nodes:
                return "#fde8e8", "#c0392b", 3, "#c0392b"
            return "#e8fdf0", "#1a7a3c", 3, "#1a7a3c"

        # ── layout constants ──────────────────────────────────────────────
        px       = 10
        aw       = 22          # horizontal gap between boxes (arrow space)
        title_h  = 18
        divider  = title_h + 2
        top_h    = 108          # height of main bus row
        bot_h    = 82           # height of DC-direct row
        top_y    = 8
        bot_y    = top_y + top_h + 24

        n_top    = 5            # Solar, Controller, Battery, Inverter, AC Loads
        avail    = W - 2 * px - (n_top - 1) * aw
        bw       = max(78, avail // n_top)
        pf_size  = max(7, min(11, bw // 12))   # param font scales with box width
        param_h  = int(pf_size * 1.9)           # real pixel height for bold font
        max_chars = max(10, bw // (pf_size - 1)) # chars before truncation
        total    = n_top * bw + (n_top - 1) * aw
        sx       = px + max(0, (W - 2 * px - total) // 2)

        # ── helper: draw one box, return (centre_x, bottom_y) ─────────────
        def _box(x0, y0, w, h, node_id, title, plabels, pkeys):
            x1  = x0 + w
            y1  = y0 + h
            cxx = (x0 + x1) / 2
            bg, bd, lw, tc = _col(node_id)
            c.create_rectangle(x0, y0, x1, y1, fill=bg, outline=bd, width=lw)
            c.create_text(cxx, y0 + 3, text=title,
                          font=("TkDefaultFont", 8, "bold"), fill=tc, anchor="n")
            c.create_line(x0 + lw, y0 + divider, x1 - lw, y0 + divider,
                          fill=bd, width=1)
            ry = y0 + divider + 4
            for pk, lbl in zip(pkeys, plabels):
                if ry + param_h > y1 - 2:
                    break
                var = self._vars.get(pk)
                val = var.get() if var else "\u2014"
                row = f"{lbl}: {val}"
                if len(row) > max_chars:
                    row = row[:max_chars - 1] + "\u2026"
                col = ("#c0392b" if (simulated and pk in failing_params)
                       else "#333333")
                c.create_text(cxx, ry, text=row,
                              font=("Courier", pf_size, "bold"), fill=col, anchor="n")
                ry += param_h
            return cxx, y1

        def _arr_h(x0, x1, y, lbl=""):
            c.create_line(x0, y, x1, y, arrow="last", fill="#555555", width=2)
            if lbl:
                c.create_text((x0 + x1) / 2, y - 8, text=lbl,
                              font=("TkDefaultFont", 7, "bold"), fill="#555555")

        def _arr_v(x, y0, y1, lbl=""):
            c.create_line(x, y0, x, y1, arrow="last", fill="#1a5fa8", width=2,
                          dash=(4, 3))
            if lbl:
                c.create_text(x + 5, (y0 + y1) / 2, text=lbl,
                              font=("TkDefaultFont", 7, "bold"), fill="#1a5fa8",
                              anchor="w")

        # ── TOP ROW: Solar → Controller → Battery → Inverter → AC Loads ───
        top_nodes = [
            ("solar",    "\u2600  Solar Array",
             ["P_stc W", "Voc STC", "Vmp", "Beta %/C", "Series", "Parallel"],
             ["panel.p_stc_w", "panel.voc_stc", "panel.vmp",
              "panel.beta_voc_pct_per_c", "panel.series_count", "panel.parallel_count"]),
            ("ctrl",     "\u26d9  Charge Controller",
             ["Type", "Max Voc V", "Max chg A", "Batt V", "Vmp margin"],
             ["ctrl.type_", "ctrl.pv_max_voc", "ctrl.charge_a_max",
              "ctrl.batt_v", "ctrl.vmp_margin"]),
            ("battery",  "\U0001f50b Battery",
             ["Chemistry", "Voltage V", "Ah each", "# parallel", "Max DoD", "BMS cont A", "BMS peak A"],
             ["batt.chemistry", "batt.v_nom", "batt.ah",
              "batt.parallel_count", "batt.dod_max", "batt.bms_cont_a", "batt.bms_peak_a"]),
            ("inverter", "\U0001f50c Inverter",
             ["V in", "P cont W", "P surge W", "Efficiency", "Idle W"],
             ["inv.v_in", "inv.p_cont_w", "inv.p_surge_w", "inv.eff", "inv.idle_w"]),
            ("ac_loads", "\u26ac AC Loads (via inverter)", [], []),
        ]

        box_cx = []
        box_by = []
        mid_y  = top_y + top_h // 2

        for idx, (nid, title, plabels, pkeys) in enumerate(top_nodes):
            x0 = sx + idx * (bw + aw)
            if nid == "ac_loads":
                x1  = x0 + bw
                y1  = top_y + top_h
                cxx = (x0 + x1) / 2
                bg, bd, lw, tc = _col("loads")
                c.create_rectangle(x0, top_y, x1, y1, fill=bg, outline=bd, width=lw)
                c.create_text(cxx, top_y + 3, text=title,
                              font=("TkDefaultFont", 8, "bold"), fill=tc, anchor="n")
                c.create_line(x0 + lw, top_y + divider, x1 - lw, top_y + divider,
                              fill=bd, width=1)
                ry = top_y + divider + 4
                try:
                    for li in range(MAX_LOADS):
                        if self._vars[f"load{li}.load_type"].get().upper() != "AC":
                            continue
                        name = self._vars[f"load{li}.name"].get() or f"Load {li+1}"
                        pw   = float(self._vars[f"load{li}.power_w"].get())
                        txt  = f"{name}: {pw:.0f}W"
                        if len(txt) > max_chars:
                            txt = txt[:max_chars - 1] + "\u2026"
                        if ry + param_h > y1 - 2:
                            break
                        c.create_text(cxx, ry, text=txt, font=("Courier", pf_size, "bold"),
                                      fill="#333333", anchor="n")
                        ry += param_h
                except Exception:
                    pass
                box_cx.append(cxx)
                box_by.append(y1)
            else:
                cxx, by = _box(x0, top_y, bw, top_h, nid, title, plabels, pkeys)
                box_cx.append(cxx)
                box_by.append(by)

        # horizontal arrows between top-row boxes
        arrow_labels = ["DC", "DC", "DC", "AC ~"]
        for idx in range(n_top - 1):
            xa = sx + (idx + 1) * (bw + aw) - aw + 2
            xb = sx + (idx + 1) * (bw + aw) - 2
            _arr_h(xa, xb, mid_y, arrow_labels[idx])

        # ── BOTTOM ROW: Battery → DC Loads (direct) ───────────────────────
        batt_cx  = box_cx[2]
        batt_bot = box_by[2]

        # vertical dashed blue arrow indicating direct DC wiring
        _arr_v(batt_cx, batt_bot + 1, bot_y - 2, "DC direct")

        # DC Loads box — same x-alignment as Battery
        dc_x0 = sx + 2 * (bw + aw)
        dc_x1 = dc_x0 + bw
        dc_cx = (dc_x0 + dc_x1) / 2
        dc_y1 = bot_y + bot_h
        bg, bd, lw, tc = _col("loads")
        c.create_rectangle(dc_x0, bot_y, dc_x1, dc_y1, fill=bg, outline=bd, width=lw)
        c.create_text(dc_cx, bot_y + 3, text="\u26a1 DC Loads (direct)",
                      font=("TkDefaultFont", 8, "bold"), fill=tc, anchor="n")
        c.create_line(dc_x0 + lw, bot_y + divider, dc_x1 - lw, bot_y + divider,
                      fill=bd, width=1)
        ry = bot_y + divider + 4
        try:
            for li in range(MAX_LOADS):
                if self._vars[f"load{li}.load_type"].get().upper() != "DC":
                    continue
                name = self._vars[f"load{li}.name"].get() or f"Load {li+1}"
                pw   = float(self._vars[f"load{li}.power_w"].get())
                rv   = self._vars[f"load{li}.req_v"].get()
                txt  = f"{name}: {pw:.0f}W @{rv}V"
                if len(txt) > max_chars:
                    txt = txt[:max_chars - 1] + "\u2026"
                if ry + param_h > dc_y1 - 2:
                    break
                c.create_text(dc_cx, ry, text=txt, font=("Courier", pf_size, "bold"),
                              fill="#333333", anchor="n")
                ry += param_h
        except Exception:
            pass

    # ─────────────────────────────────────────
    # Simulate
    # ─────────────────────────────────────────
    def _simulate(self):
        self._clear()

        try:
            cfg = self._parse()
        except Exception as exc:
            self._write(f"❌  Input error — check your values:\n   {exc}\n", "error")
            return

        try:
            result = RuleEngine(cfg).evaluate()
        except Exception as exc:
            self._write(f"❌  Engine error:\n   {exc}\n", "error")
            return

        # update flowchart before writing text output
        self._fc_result = result
        self._redraw_flowchart(result)

        m = result["metrics"]
        arr = cfg.pv_array
        sep = "─" * 56 + "\n"

        # ── Status ──────────────────────────────────
        self._write(sep)
        if result["status"] == "PASS":
            self._write(
                f"  ✅  PASS      Bus Voltage: {result['bus_voltage_v']:.0f} V\n", "pass")
        else:
            self._write(
                f"  ❌  FAIL      Bus Voltage: {result['bus_voltage_v']:.0f} V\n", "fail")
        self._write(sep)

        # ── Energy ──────────────────────────────────
        self._write("\n  ENERGY BUDGET\n", "head")
        self._write(f"    DC loads             : {m['e_dc_wh']:>8.1f} Wh\n")
        self._write(f"    AC loads (output)    : {m['e_ac_out_wh']:>8.1f} Wh\n")
        self._write(f"    AC via inverter      : {m['e_ac_in_wh']:>8.1f} Wh\n")
        self._write(f"    Inverter idle        : {m['e_idle_wh']:>8.1f} Wh\n")
        self._write(f"    Battery daily need   : {m['e_bat_day_wh']:>8.1f} Wh\n")
        self._write(f"    Design target (+margin): {m['e_design_wh']:>6.1f} Wh\n")

        # ── Battery ─────────────────────────────────
        self._write("\n  BATTERY\n", "head")
        self._write(f"    Min Ah needed : {m['ah_req']:>7.1f} Ah   installed: {cfg.battery.ah:.1f} Ah\n")
        self._write(f"    Continuous    : {m['i_bus_cont_a']:>7.2f} A\n")
        self._write(f"    Surge         : {m['i_bus_surge_a']:>7.2f} A\n")

        # ── Inverter ────────────────────────────────
        if cfg.inverter:
            self._write("\n  INVERTER\n", "head")
            self._write(
                f"    Continuous needed : {m['p_inv_req_cont_w']:>5.0f} W   installed: {cfg.inverter.p_cont_w:.0f} W\n")
            self._write(
                f"    Surge needed      : {m['p_inv_req_surge_w']:>5.0f} W   installed: {cfg.inverter.p_surge_w:.0f} W\n")

        # ── PV ──────────────────────────────────────
        self._write("\n  PV ARRAY\n", "head")
        self._write(f"    Config         : {arr.series_count}S × {arr.parallel_count}P  =  {m['pv_installed_w']:.0f} W installed\n")
        self._write(f"    Min needed     : {m['p_pv_min_w']:.1f} W\n")
        self._write(f"    Cold Voc       : {m['voc_cold_string_v']:.2f} V  (controller max: {cfg.controller.pv_max_voc} V)\n")
        self._write(f"    Charge current : {m['i_charge_est_a']:.2f} A  (controller max: {cfg.controller.charge_a_max} A)\n")

        # ── Protection ──────────────────────────────
        self._write("\n  PROTECTION (minimum fuse / cable ratings)\n", "head")
        self._write(f"    Main battery fuse  : {m['main_battery_fuse_a_min']} A\n")
        self._write(f"    Controller cable   : {m['controller_batt_cable_fuse_a_min']} A\n")

        # ── Warnings ────────────────────────────────
        if result["warnings"]:
            self._write("\n  WARNINGS\n", "head")
            for w in result["warnings"]:
                self._write(f"{w}\n", "warn")

        # ── Failures ────────────────────────────────
        if result["fails"]:
            self._write(f"\n{sep}", "fail")
            self._write(f"  {len(result['fails'])} FAILURE(S) — fix before purchasing\n", "fail")
            self._write(sep, "fail")
            for idx, fail in enumerate(result["fails"], 1):
                self._write(f"\n  [{idx}] {fail['summary']}\n", "fail")
                for line in fail["detail"].splitlines():
                    self._write(f"      {line}\n")
        else:
            self._write(f"\n{sep}")
            self._write("  All checks passed. Configuration is electrically valid.\n", "pass")

        self._out.see("1.0")


# ─────────────────────────────────────────────
if __name__ == "__main__":
    App().mainloop()
