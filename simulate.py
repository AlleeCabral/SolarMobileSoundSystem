"""
Solar/Battery Mobile Sound System — Simulator CLI
==================================================
Usage:
  python simulate.py                   # runs built-in example (your system)
  python simulate.py my_system.json    # loads config from JSON file
  python simulate.py --help
"""

from __future__ import annotations
import json
import sys
from rules_engine import (
    SystemConfig, Load, Battery, Inverter,
    Panel, PVArray, Controller, Environment, Policy,
    RuleEngine,
)


# ─────────────────────────────────────────────
# JSON → dataclass loader
# ─────────────────────────────────────────────
def load_config_from_json(path: str) -> SystemConfig:
    with open(path, "r", encoding="utf-8") as f:
        d = json.load(f)

    loads = [
        Load(
            name=l["name"],
            power_w=l["power_w"],
            hours_per_day=l["hours_per_day"],
            load_type=l["load_type"],
            required_voltage=l.get("required_voltage"),
            surge_w=l.get("surge_w", 0.0),
        )
        for l in d["loads"]
    ]

    b = d["battery"]
    battery = Battery(
        chemistry=b["chemistry"],
        v_nom=b["v_nom"],
        ah=b["ah"],
        dod_max=b.get("dod_max", 0.85),
        bms_cont_a=b.get("bms_cont_a", 100.0),
        bms_peak_a=b.get("bms_peak_a", 200.0),
    )

    inverter = None
    if "inverter" in d and d["inverter"]:
        iv = d["inverter"]
        inverter = Inverter(
            v_in=iv["v_in"],
            p_cont_w=iv["p_cont_w"],
            p_surge_w=iv["p_surge_w"],
            eff=iv.get("eff", 0.90),
            idle_w=iv.get("idle_w", 8.0),
            pure_sine=iv.get("pure_sine", True),
        )

    pv = d["pv_array"]
    pan = pv["panel"]
    panel = Panel(
        p_stc_w=pan["p_stc_w"],
        voc_stc=pan["voc_stc"],
        vmp=pan["vmp"],
        isc=pan["isc"],
        imp=pan["imp"],
        beta_voc_pct_per_c=pan.get("beta_voc_pct_per_c", -0.30),
    )
    pv_array = PVArray(
        panel=panel,
        series_count=pv.get("series_count", 1),
        parallel_count=pv.get("parallel_count", 1),
    )

    ct = d["controller"]
    # JSON keys are always strings; convert voltage keys to float
    power_limits = {float(k): v for k, v in ct["pv_power_limit_by_batt_v"].items()}
    controller = Controller(
        type_=ct["type_"],
        battery_voltages_supported=[float(v) for v in ct["battery_voltages_supported"]],
        pv_max_voc=ct["pv_max_voc"],
        charge_a_max=ct["charge_a_max"],
        pv_power_limit_by_batt_v=power_limits,
        requires_vmp_margin_v=ct.get("requires_vmp_margin_v", 3.0),
    )

    ev = d["environment"]
    environment = Environment(
        psh=ev["psh"],
        t_min_c=ev["t_min_c"],
        pv_derate=ev.get("pv_derate", 0.75),
    )

    pol = d.get("policy", {})
    policy = Policy(
        autonomy_hours=pol.get("autonomy_hours", 8.0),
        mode=pol.get("mode", "balanced_low_cost"),
        energy_margin=pol.get("energy_margin", 1.15),
        controller_headroom=pol.get("controller_headroom", 1.10),
        fuse_factor=pol.get("fuse_factor", 1.25),
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


# ─────────────────────────────────────────────
# Built-in example — your system from the diagram
# ─────────────────────────────────────────────
def builtin_example() -> SystemConfig:
    loads = [
        Load("XDJ-XZ",          power_w=30,  hours_per_day=8, load_type="AC", surge_w=80),
        Load("Adam T5V",         power_w=30,  hours_per_day=8, load_type="AC", surge_w=70),
        Load("Phones x2",        power_w=20,  hours_per_day=8, load_type="AC"),
        Load("LED lights",       power_w=25,  hours_per_day=8, load_type="AC"),
        # Corrected amp: original 100 W + 100 W missing = 200 W total
        Load("Amp RUIZHI 2.1 (corrected)",
             power_w=200, hours_per_day=8, load_type="DC",
             required_voltage=24, surge_w=260),
    ]
    battery  = Battery("LiFePO4", v_nom=24, ah=150, dod_max=0.85, bms_cont_a=150, bms_peak_a=250)
    inverter = Inverter(v_in=24, p_cont_w=800, p_surge_w=1600, eff=0.90, idle_w=10, pure_sine=True)
    panel    = Panel(p_stc_w=400, voc_stc=22, vmp=18.5, isc=22.5, imp=21.6, beta_voc_pct_per_c=-0.30)
    pv_array = PVArray(panel=panel, series_count=2, parallel_count=2)
    controller = Controller(
        type_="MPPT",
        battery_voltages_supported=[12.0, 24.0],
        pv_max_voc=100,
        charge_a_max=60,
        pv_power_limit_by_batt_v={12.0: 800.0, 24.0: 1600.0},
        requires_vmp_margin_v=3.0,
    )
    environment = Environment(psh=5.0, t_min_c=0, pv_derate=0.75)
    policy      = Policy(autonomy_hours=8, mode="balanced_low_cost")
    return SystemConfig(loads, battery, inverter, pv_array, controller, environment, policy)


# ─────────────────────────────────────────────
# Pretty printer
# ─────────────────────────────────────────────
SEP = "─" * 62

def print_result(result: dict, cfg: SystemConfig):
    print()
    print(SEP)
    print("  SOLAR / BATTERY SOUND SYSTEM — SIMULATION RESULT")
    print(SEP)

    status = result["status"]
    icon   = "✅  PASS" if status == "PASS" else "❌  FAIL"
    print(f"\n  Status       : {icon}")
    print(f"  Bus Voltage  : {result['bus_voltage_v']:.0f} V")
    print()

    # ── Loads summary ──────────────────────────────────────
    print("  LOADS")
    print(f"  {'Name':<35} {'Type':<4} {'W':>6}  {'h/day':>5}  {'Surge W':>7}")
    print("  " + "─" * 58)
    for l in cfg.loads:
        print(f"  {l.name:<35} {l.load_type:<4} {l.power_w:>6.0f}  {l.hours_per_day:>5.1f}  {l.surge_w:>7.0f}")
    print()

    # ── Energy ─────────────────────────────────────────────
    m = result["metrics"]
    print("  ENERGY BUDGET (Wh)")
    print(f"    DC loads            : {m['e_dc_wh']:>8.1f} Wh")
    print(f"    AC loads (output)   : {m['e_ac_out_wh']:>8.1f} Wh")
    print(f"    AC via inverter     : {m['e_ac_in_wh']:>8.1f} Wh  (÷ inverter efficiency)")
    print(f"    Inverter idle       : {m['e_idle_wh']:>8.1f} Wh")
    print(f"    Battery daily need  : {m['e_bat_day_wh']:>8.1f} Wh")
    print(f"    Design target (+{(cfg.policy.energy_margin - 1)*100:.0f}%) : {m['e_design_wh']:>8.1f} Wh")
    print()

    # ── Battery ────────────────────────────────────────────
    print("  BATTERY")
    print(f"    Minimum Ah needed   : {m['ah_req']:>8.1f} Ah")
    print(f"    Installed           : {cfg.battery.ah:>8.1f} Ah")
    print(f"    Continuous bus draw : {m['i_bus_cont_a']:>8.2f} A")
    print(f"    Surge bus draw      : {m['i_bus_surge_a']:>8.2f} A")
    print()

    # ── Inverter ───────────────────────────────────────────
    if cfg.inverter:
        print("  INVERTER")
        print(f"    Min continuous needed : {m['p_inv_req_cont_w']:>6.0f} W")
        print(f"    Installed continuous  : {cfg.inverter.p_cont_w:>6.0f} W")
        print(f"    Min surge needed      : {m['p_inv_req_surge_w']:>6.0f} W")
        print(f"    Installed surge       : {cfg.inverter.p_surge_w:>6.0f} W")
        print()

    # ── PV ─────────────────────────────────────────────────
    arr = cfg.pv_array
    print("  PV ARRAY")
    print(f"    Configuration       : {arr.series_count}S × {arr.parallel_count}P")
    print(f"    Total power         : {m['pv_installed_w']:>8.0f} W")
    print(f"    Minimum needed      : {m['p_pv_min_w']:>8.1f} W")
    print(f"    Cold Voc (string)   : {m['voc_cold_string_v']:>8.2f} V  (controller max: {cfg.controller.pv_max_voc} V)")
    print(f"    Est. charge current : {m['i_charge_est_a']:>8.2f} A  (controller max: {cfg.controller.charge_a_max} A)")
    print()

    # ── Protection ─────────────────────────────────────────
    print("  PROTECTION (minimum fuse/cable ratings)")
    print(f"    Main battery fuse   : {m['main_battery_fuse_a_min']:>6} A")
    print(f"    Controller cable    : {m['controller_batt_cable_fuse_a_min']:>6} A")
    print()

    # ── Warnings ───────────────────────────────────────────
    if result["warnings"]:
        print("  WARNINGS")
        for w in result["warnings"]:
            for line in w.splitlines():
                print("  " + line)
        print()

    # ── Failures with explanations ─────────────────────────
    if result["fails"]:
        print("  FAILURES")
        print(SEP)
        for i, fail in enumerate(result["fails"], 1):
            print(f"\n  [{i}] {fail['summary']}")
            print()
            for line in fail["detail"].splitlines():
                print("      " + line)
        print()
        print(SEP)
        print("  ACTION REQUIRED: Fix all failures before purchasing or deploying.")
    else:
        print(SEP)
        print("  All checks passed. This configuration is electrically valid.")

    print(SEP)
    print()


# ─────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────
def main():
    args = sys.argv[1:]

    if args and args[0] in ("--help", "-h"):
        print(__doc__)
        sys.exit(0)

    if args:
        json_path = args[0]
        print(f"Loading config from: {json_path}")
        cfg = load_config_from_json(json_path)
    else:
        print("No config file specified — running built-in example (your system from the diagram).")
        cfg = builtin_example()

    result = RuleEngine(cfg).evaluate()
    print_result(result, cfg)


if __name__ == "__main__":
    main()
