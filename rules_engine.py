"""
Solar / Battery Mobile Sound System — Rule Engine
=================================================
All electrical rules are deterministic functions. 
Call RuleEngine(cfg).evaluate() to get a structured result
with PASS/FAIL status, key metrics, and human-readable failure
explanations that describe WHY something fails and HOW to fix it.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional, Dict
import math


# ─────────────────────────────────────────────
# FAILURE EXPLANATIONS
# ─────────────────────────────────────────────
FAIL_EXPLANATIONS = {
    "battery_ah": (
        "WHY: The battery does not hold enough energy to power all loads for {hours:.0f} hours.\n"
        "     Stored energy = Ah × Voltage × DoD. Running below minimum means deep‑cycling,\n"
        "     which damages LiFePO4 cells and drastically shortens lifespan.\n"
        "FIX: Use a battery with at least {ah_req:.0f} Ah at {bus_v:.0f} V, "
        "     or reduce load hours, or add a second battery in parallel."
    ),
    "bms_cont": (
        "WHY: The total continuous current drawn from the battery ({i_cont:.1f} A) exceeds the\n"
        "     BMS continuous current rating ({bms_cont:.1f} A).\n"
        "     The BMS will trip or overheat under sustained load, cutting power to all equipment.\n"
        "FIX: Use a battery with a higher BMS continuous current rating, "
        "     or reduce simultaneous power draw."
    ),
    "bms_peak": (
        "WHY: The peak/surge current ({i_surge:.1f} A) exceeds the BMS peak rating ({bms_peak:.1f} A).\n"
        "     High‑inrush devices (subwoofer amp, DJ controller startup) can spike well above\n"
        "     steady‑state current for 10–200 ms. Exceeding the BMS peak causes trip or damage.\n"
        "FIX: Use a battery with a higher BMS peak current rating, or add a soft‑start circuit,\n"
        "     or stagger the startup of high‑surge devices."
    ),
    "no_inverter": (
        "WHY: AC loads are present in the system but no inverter has been defined.\n"
        "     AC equipment (XDJ, Adam monitors, phone chargers) cannot run directly\n"
        "     from a 12 V or 24 V battery without an inverter.\n"
        "FIX: Add a pure‑sine inverter rated for the total AC load with 25 % headroom."
    ),
    "inverter_voltage": (
        "WHY: The inverter's DC input voltage ({inv_v:.0f} V) does not match the battery bus\n"
        "     voltage ({bus_v:.0f} V). Connecting a mismatched inverter will either underperform\n"
        "     (12 V battery, 24 V inverter → low output) or damage the inverter (24 V battery,\n"
        "     12 V inverter → over‑voltage).\n"
        "FIX: Choose an inverter whose DC input voltage matches the battery bus voltage ({bus_v:.0f} V)."
    ),
    "inverter_cont": (
        "WHY: The inverter's continuous power rating ({inv_cont:.0f} W) is less than the required\n"
        "     minimum ({req_cont:.0f} W — 125 % of total AC load for headroom).\n"
        "     Running an inverter above its rating causes thermal shutdown and component failure.\n"
        "FIX: Use an inverter with a continuous rating ≥ {req_cont:.0f} W."
    ),
    "inverter_surge": (
        "WHY: The inverter's surge rating ({inv_surge:.0f} W) is less than the estimated startup\n"
        "     surge demand ({req_surge:.0f} W). Inverters that cannot handle startup surges will\n"
        "     trip immediately when devices spin up, cutting all AC power.\n"
        "FIX: Use an inverter with a surge rating ≥ {req_surge:.0f} W, or stagger device startup."
    ),
    "voc_cold": (
        "WHY: The PV string's cold‑corrected open‑circuit voltage ({voc_cold:.1f} V) is at or\n"
        "     above the MPPT controller's maximum safe PV input ({safe_v:.1f} V, with 10 % margin).\n"
        "     On a cold morning the panel voltage rises. If it exceeds the controller's input\n"
        "     limit, the controller's input stage can be permanently damaged.\n"
        "FIX: Reduce the number of panels in series, choose a controller with a higher Voc limit,\n"
        "     or select panels with a lower Voc."
    ),
    "ctrl_batt_v": (
        "WHY: The controller does not list {bus_v:.0f} V as a supported battery charging voltage.\n"
        "     Charging a battery at the wrong voltage profile will either undercharge it\n"
        "     (sulfation / capacity loss) or overcharge it (thermal runaway risk in LiFePO4).\n"
        "FIX: Choose a controller that explicitly supports {bus_v:.0f} V LiFePO4 battery profiles."
    ),
    "vmp_low": (
        "WHY: The PV string's operating voltage (Vmp = {vmp:.1f} V) is too close to or below\n"
        "     the battery charge voltage ({v_charge:.1f} V, plus MPPT margin {margin:.1f} V).\n"
        "     An MPPT controller needs the panel's Vmp to be a few volts above the battery\n"
        "     charge voltage to regulate current. Otherwise it cannot charge the battery fully.\n"
        "FIX: Add more panels in series to raise Vmp, or choose panels with a higher Vmp."
    ),
    "ctrl_current": (
        "WHY: The estimated charge current from the PV array ({i_charge:.1f} A) exceeds the\n"
        "     controller's maximum charge current ({ctrl_max:.1f} A).\n"
        "     Over‑current input will blow internal protection fuses or damage the controller.\n"
        "FIX: Use a controller with a higher current rating, reduce the number of parallel panel\n"
        "     strings, or split into two separate MPPT controllers."
    ),
    "ctrl_power": (
        "WHY: The total PV array power ({pv_w:.0f} W) exceeds the controller's maximum allowed\n"
        "     PV input power at {bus_v:.0f} V ({limit_w:.0f} W).\n"
        "     Exceeding this limit forces the controller to clip power or triggers a protection\n"
        "     shutdown — you lose charging efficiency and may damage the unit.\n"
        "FIX: Use a higher‑rated controller or remove some panels from the array."
    ),
    "pv_undersized": (
        "WHY: The installed PV array ({pv_w:.0f} W) produces less energy per day than what\n"
        "     is consumed ({pv_min:.0f} W minimum, calculated from {psh:.1f} peak sun hours\n"
        "     and a system derate of {derate:.0%}).\n"
        "     The battery will be net‑discharged every day and will eventually deplete.\n"
        "FIX: Add more panels (parallel strings) or increase PSH assumption (better placement),\n"
        "     or reduce daily load."
    ),
}


# ─────────────────────────────────────────────
# DATA MODELS
# ─────────────────────────────────────────────
@dataclass
class Load:
    name: str
    power_w: float
    hours_per_day: float
    load_type: str              # "DC" or "AC"
    required_voltage: Optional[float] = None  # V — for fixed‑voltage DC loads
    surge_w: float = 0.0


@dataclass
class Battery:
    chemistry: str              # "LiFePO4"
    v_nom: float                # nominal voltage (12 or 24 V typical)
    ah: float                   # Amp‑hours
    dod_max: float = 0.85       # maximum depth of discharge (0–1)
    bms_cont_a: float = 100.0   # BMS continuous discharge current
    bms_peak_a: float = 200.0   # BMS peak discharge current


@dataclass
class Inverter:
    v_in: float                 # DC input voltage must match bus
    p_cont_w: float             # continuous AC output power
    p_surge_w: float            # surge/peak AC output power
    eff: float = 0.90           # efficiency (0–1)
    idle_w: float = 8.0         # idle/standby DC draw
    pure_sine: bool = True


@dataclass
class Panel:
    p_stc_w: float              # rated power at STC
    voc_stc: float              # open‑circuit voltage at STC
    vmp: float                  # max‑power voltage at STC
    isc: float                  # short‑circuit current at STC
    imp: float                  # max‑power current at STC
    beta_voc_pct_per_c: float = -0.30  # temperature coefficient for Voc (%/°C)


@dataclass
class PVArray:
    panel: Panel
    series_count: int = 1       # panels wired in series (raises voltage)
    parallel_count: int = 1     # strings wired in parallel (raises current)

    @property
    def p_total_w(self) -> float:
        return self.panel.p_stc_w * self.series_count * self.parallel_count

    @property
    def voc_string_stc(self) -> float:
        return self.panel.voc_stc * self.series_count

    @property
    def vmp_string(self) -> float:
        return self.panel.vmp * self.series_count

    @property
    def isc_array(self) -> float:
        return self.panel.isc * self.parallel_count


@dataclass
class Controller:
    type_: str                              # "MPPT" or "PWM"
    battery_voltages_supported: List[float] # e.g. [12, 24]
    pv_max_voc: float                       # absolute max PV input Voc
    charge_a_max: float                     # max charge output current
    pv_power_limit_by_batt_v: Dict[float, float]  # {12: 520, 24: 1040}
    requires_vmp_margin_v: float = 3.0      # Vmp must exceed charge voltage by this much


@dataclass
class Environment:
    psh: float          # peak sun hours per day at installation location
    t_min_c: float      # minimum expected ambient temperature (°C)
    pv_derate: float = 0.75  # overall system derate factor (temp, wiring, dust, …)


@dataclass
class Policy:
    autonomy_hours: float = 8.0
    mode: str = "balanced_low_cost"
    energy_margin: float = 1.15       # 1.15 balanced / 1.25 high‑reliability
    controller_headroom: float = 1.10 # safety multiplier for Voc cold check
    fuse_factor: float = 1.25         # for sizing fuses and cable ratings


@dataclass
class SystemConfig:
    loads: List[Load]
    battery: Battery
    inverter: Optional[Inverter]
    pv_array: PVArray
    controller: Controller
    environment: Environment
    policy: Policy = field(default_factory=Policy)


# ─────────────────────────────────────────────
# RULE ENGINE
# ─────────────────────────────────────────────
class RuleEngine:
    def __init__(self, cfg: SystemConfig):
        self.cfg = cfg
        self.fails: List[Dict] = []   # {code, summary, detail}
        self.warnings: List[str] = []

    def _fail(self, code: str, summary: str, detail: str):
        self.fails.append({"code": code, "summary": summary, "detail": detail})

    # ── 1. BUS VOLTAGE ──────────────────────────────────────────────────────
    def derive_bus_voltage(self) -> float:
        """
        Auto‑derive preferred bus voltage from:
          1. Fixed‑voltage DC loads (hard requirement)
          2. Inverter input voltage (if defined)
          3. Load magnitude heuristic
        Falls back to battery nominal if no other signal.
        """
        loads = self.cfg.loads
        candidates: set = set(self.cfg.controller.battery_voltages_supported)

        # hard constraint — DC load at fixed voltage
        for l in loads:
            if l.load_type.upper() == "DC" and l.required_voltage is not None:
                if l.required_voltage >= 22:
                    candidates.discard(12.0)
                    candidates.add(24.0)

        # inverter input voltage as a strong hint
        if self.cfg.inverter:
            inv_v = self.cfg.inverter.v_in
            if inv_v in {24.0, 48.0}:
                candidates.discard(12.0)
                candidates.add(inv_v)

        # heuristic — large DC or AC load prefers 24 V
        p_dc = sum(l.power_w for l in loads if l.load_type.upper() == "DC")
        p_ac = sum(l.power_w for l in loads if l.load_type.upper() == "AC")
        if p_dc > 600 or p_ac > 1000:
            candidates.discard(12.0)
            candidates.add(24.0)

        # match battery nominal
        batt_v = self.cfg.battery.v_nom
        if batt_v in candidates:
            return batt_v
        # fallback
        return min(candidates) if candidates else batt_v

    # ── 2. ENERGY BUDGET ────────────────────────────────────────────────────
    def energy_budget(self) -> Dict[str, float]:
        inv = self.cfg.inverter
        pol = self.cfg.policy

        e_dc = sum(l.power_w * l.hours_per_day
                   for l in self.cfg.loads if l.load_type.upper() == "DC")
        e_ac_out = sum(l.power_w * l.hours_per_day
                       for l in self.cfg.loads if l.load_type.upper() == "AC")

        has_ac = e_ac_out > 0
        if has_ac and inv is None:
            self._fail(
                "no_inverter",
                "No inverter defined but AC loads are present.",
                FAIL_EXPLANATIONS["no_inverter"]
            )
            inv_eff, inv_idle_wh = 0.9, 0.0
        else:
            inv_eff = inv.eff if inv else 1.0
            inv_idle_wh = (inv.idle_w * pol.autonomy_hours) if (inv and has_ac) else 0.0

        e_ac_in = (e_ac_out / inv_eff) if inv_eff > 0 else float("inf")
        e_bat_day = e_dc + e_ac_in + inv_idle_wh
        e_design = e_bat_day * pol.energy_margin

        return {
            "e_dc_wh": round(e_dc, 1),
            "e_ac_out_wh": round(e_ac_out, 1),
            "e_ac_in_wh": round(e_ac_in, 1),
            "e_idle_wh": round(inv_idle_wh, 1),
            "e_bat_day_wh": round(e_bat_day, 1),
            "e_design_wh": round(e_design, 1),
        }

    # ── 3. BATTERY RULES ────────────────────────────────────────────────────
    def battery_rules(self, bus_v: float, e_design_wh: float) -> Dict[str, float]:
        batt = self.cfg.battery
        inv = self.cfg.inverter
        pol = self.cfg.policy

        ah_req = e_design_wh / (max(0.01, batt.dod_max) * bus_v)

        p_dc = sum(l.power_w for l in self.cfg.loads if l.load_type.upper() == "DC")
        p_ac_out = sum(l.power_w for l in self.cfg.loads if l.load_type.upper() == "AC")
        p_ac_in = (p_ac_out / inv.eff) if (inv and inv.eff > 0) else 0.0
        p_idle = inv.idle_w if inv else 0.0
        p_bus_cont = p_dc + p_ac_in + p_idle

        p_surge_loads = sum(l.surge_w for l in self.cfg.loads)
        p_surge = max(p_surge_loads, inv.p_surge_w if inv else 0)
        i_surge = p_surge / bus_v if p_surge > 0 else (p_bus_cont / bus_v)
        i_cont = p_bus_cont / bus_v

        if batt.ah < ah_req:
            self._fail(
                "battery_ah",
                f"Battery too small: need {ah_req:.0f} Ah, have {batt.ah:.0f} Ah.",
                FAIL_EXPLANATIONS["battery_ah"].format(
                    hours=pol.autonomy_hours, ah_req=ah_req, bus_v=bus_v)
            )
        if i_cont > batt.bms_cont_a:
            self._fail(
                "bms_cont",
                f"BMS continuous current exceeded: {i_cont:.1f} A drawn, {batt.bms_cont_a:.1f} A rated.",
                FAIL_EXPLANATIONS["bms_cont"].format(
                    i_cont=i_cont, bms_cont=batt.bms_cont_a)
            )
        if i_surge > batt.bms_peak_a:
            self._fail(
                "bms_peak",
                f"BMS peak current exceeded: {i_surge:.1f} A surge, {batt.bms_peak_a:.1f} A rated.",
                FAIL_EXPLANATIONS["bms_peak"].format(
                    i_surge=i_surge, bms_peak=batt.bms_peak_a)
            )

        return {
            "ah_req": round(ah_req, 1),
            "p_bus_cont_w": round(p_bus_cont, 1),
            "i_bus_cont_a": round(i_cont, 2),
            "i_bus_surge_a": round(i_surge, 2),
        }

    # ── 4. INVERTER RULES ───────────────────────────────────────────────────
    def inverter_rules(self, bus_v: float) -> Dict[str, float]:
        inv = self.cfg.inverter
        p_ac_cont = sum(l.power_w for l in self.cfg.loads if l.load_type.upper() == "AC")
        p_ac_surge = sum(l.surge_w for l in self.cfg.loads if l.load_type.upper() == "AC")
        p_req_cont = 1.25 * p_ac_cont
        p_req_surge = max(p_ac_surge, p_ac_cont * 1.5)

        if p_ac_cont <= 0 or inv is None:
            return {"p_inv_req_cont_w": round(p_req_cont, 1), "p_inv_req_surge_w": round(p_req_surge, 1)}

        if abs(inv.v_in - bus_v) > 1.5:
            self._fail(
                "inverter_voltage",
                f"Inverter input voltage ({inv.v_in:.0f} V) ≠ bus voltage ({bus_v:.0f} V).",
                FAIL_EXPLANATIONS["inverter_voltage"].format(inv_v=inv.v_in, bus_v=bus_v)
            )
        if inv.p_cont_w < p_req_cont:
            self._fail(
                "inverter_cont",
                f"Inverter too small: {inv.p_cont_w:.0f} W continuous, need {p_req_cont:.0f} W.",
                FAIL_EXPLANATIONS["inverter_cont"].format(inv_cont=inv.p_cont_w, req_cont=p_req_cont)
            )
        if inv.p_surge_w < p_req_surge:
            self._fail(
                "inverter_surge",
                f"Inverter surge too low: {inv.p_surge_w:.0f} W, need {p_req_surge:.0f} W.",
                FAIL_EXPLANATIONS["inverter_surge"].format(inv_surge=inv.p_surge_w, req_surge=p_req_surge)
            )
        if not inv.pure_sine:
            self.warnings.append(
                "WARNING: Modified‑sine inverter detected. Audio equipment (DJ gear, powered monitors)\n"
                "         can produce hum, overheat, or be damaged. Use a pure‑sine inverter."
            )

        return {"p_inv_req_cont_w": round(p_req_cont, 1), "p_inv_req_surge_w": round(p_req_surge, 1)}

    # ── 5. PV + CONTROLLER RULES ────────────────────────────────────────────
    def pv_controller_rules(self, bus_v: float, e_bat_day_wh: float) -> Dict[str, float]:
        arr = self.cfg.pv_array
        ctrl = self.cfg.controller
        env = self.cfg.environment
        pol = self.cfg.policy

        # target PV power
        p_pv_min = e_bat_day_wh / max(0.01, env.psh * env.pv_derate)

        # cold Voc
        beta_abs = abs(arr.panel.beta_voc_pct_per_c) / 100.0
        voc_cold_panel = arr.panel.voc_stc * (1 + beta_abs * (25 - env.t_min_c))
        voc_cold_string = voc_cold_panel * arr.series_count
        safe_voc_limit = ctrl.pv_max_voc / pol.controller_headroom

        if voc_cold_string >= safe_voc_limit:
            self._fail(
                "voc_cold",
                f"PV cold Voc ({voc_cold_string:.1f} V) exceeds safe MPPT input ({safe_voc_limit:.1f} V).",
                FAIL_EXPLANATIONS["voc_cold"].format(voc_cold=voc_cold_string, safe_v=safe_voc_limit)
            )

        # controller battery voltage
        if bus_v not in ctrl.battery_voltages_supported:
            self._fail(
                "ctrl_batt_v",
                f"Controller doesn't support {bus_v:.0f} V battery charging.",
                FAIL_EXPLANATIONS["ctrl_batt_v"].format(bus_v=bus_v)
            )

        # MPPT Vmp margin
        v_charge = 14.4 if bus_v <= 12.5 else 28.8
        if ctrl.type_.upper() == "MPPT":
            vmp_needed = v_charge + ctrl.requires_vmp_margin_v
            if arr.vmp_string < vmp_needed:
                self._fail(
                    "vmp_low",
                    f"PV Vmp ({arr.vmp_string:.1f} V) too low for {bus_v:.0f} V charging (need >{vmp_needed:.1f} V).",
                    FAIL_EXPLANATIONS["vmp_low"].format(
                        vmp=arr.vmp_string, v_charge=v_charge,
                        margin=ctrl.requires_vmp_margin_v)
                )

        # charge current
        i_charge_est = arr.p_total_w / v_charge
        if i_charge_est > ctrl.charge_a_max:
            self._fail(
                "ctrl_current",
                f"MPPT output current ({i_charge_est:.1f} A) exceeds controller max ({ctrl.charge_a_max:.1f} A).",
                FAIL_EXPLANATIONS["ctrl_current"].format(
                    i_charge=i_charge_est, ctrl_max=ctrl.charge_a_max)
            )

        # controller PV power limit
        p_limit = ctrl.pv_power_limit_by_batt_v.get(bus_v, float("inf"))
        if arr.p_total_w > p_limit:
            self._fail(
                "ctrl_power",
                f"PV array ({arr.p_total_w:.0f} W) exceeds controller power limit ({p_limit:.0f} W) at {bus_v:.0f} V.",
                FAIL_EXPLANATIONS["ctrl_power"].format(
                    pv_w=arr.p_total_w, bus_v=bus_v, limit_w=p_limit)
            )

        # PV size adequacy
        if arr.p_total_w < p_pv_min:
            self._fail(
                "pv_undersized",
                f"PV array ({arr.p_total_w:.0f} W) won't cover daily energy (need {p_pv_min:.0f} W minimum).",
                FAIL_EXPLANATIONS["pv_undersized"].format(
                    pv_w=arr.p_total_w, pv_min=p_pv_min,
                    psh=env.psh, derate=env.pv_derate)
            )

        return {
            "p_pv_min_w": round(p_pv_min, 1),
            "voc_cold_string_v": round(voc_cold_string, 2),
            "i_charge_est_a": round(i_charge_est, 2),
            "pv_installed_w": arr.p_total_w,
        }

    # ── 6. PROTECTION SIZING ────────────────────────────────────────────────
    def protection_hints(self, i_bus_cont_a: float, i_charge_est_a: float) -> Dict[str, float]:
        f = self.cfg.policy.fuse_factor
        return {
            "main_battery_fuse_a_min": math.ceil(i_bus_cont_a * f),
            "controller_batt_cable_fuse_a_min": math.ceil(i_charge_est_a * f),
        }

    # ── MAIN EVALUATE ────────────────────────────────────────────────────────
    def evaluate(self) -> Dict:
        self.fails.clear()
        self.warnings.clear()

        bus_v = self.derive_bus_voltage()
        energy = self.energy_budget()
        batt = self.battery_rules(bus_v, energy["e_design_wh"])
        inv = self.inverter_rules(bus_v)
        pv = self.pv_controller_rules(bus_v, energy["e_bat_day_wh"])
        prot = self.protection_hints(batt["i_bus_cont_a"], pv["i_charge_est_a"])

        return {
            "status": "PASS" if not self.fails else "FAIL",
            "bus_voltage_v": bus_v,
            "metrics": {**energy, **batt, **inv, **pv, **prot},
            "fails": self.fails,
            "warnings": self.warnings,
        }
