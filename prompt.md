Reading the existing code quickly to make the prompt maximally precise. 

Read [](file:///c%3A/Users/AlexandraCabral/Documents/Bike/rules_engine.py#1-1), lines 1 to 115

I have everything I need. Here's the precise, agent-ready prompt:

---

## Plan: Agent Prompt for Simple Tkinter UI

**TL;DR:** A tightly-scoped, unambiguous prompt that tells the agent exactly one file to create (`app.py`), exactly what library to use (tkinter, stdlib only), exactly what the layout is, and exactly how to wire it to the existing engine — leaving zero room for scope creep or paralysis.

---

**Prompt to give the agent:**

> **Task:** Create a single file `app.py` in Bike that is a Tkinter desktop GUI for the solar system simulator.
>
> **Rules — do not deviate:**
> - Use only `tkinter` and `tkinter.ttk` (Python stdlib, no pip installs).
> - Import `RuleEngine` and all dataclasses from rules_engine.py (already in the same folder).
> - Do NOT modify rules_engine.py or any other existing file.
> - Do NOT add any feature not listed below.
>
> **Layout — three columns side by side, then output below:**
>
> **Column 1 — Left panel (top to bottom, each as a labeled `LabelFrame`):**
> 1. **Solar Panel** — fields: `p_stc_w`, `voc_stc`, `vmp`, `isc`, `imp`, `beta_voc_pct_per_c`, `series_count`, `parallel_count`
> 2. **Controller (MPPT)** — fields: `type_` (Entry), `pv_max_voc`, `charge_a_max`, `battery_voltages_supported` (comma-separated Entry, e.g. "12,24"), `pv_power_limit_12v`, `pv_power_limit_24v`, `requires_vmp_margin_v`
>
> **Column 2 — Center panel:**
> 3. **Battery** — fields: `chemistry` (Entry), `v_nom`, `ah`, `dod_max`, `bms_cont_a`, `bms_peak_a`
> 4. **Inverter** — fields: `v_in`, `p_cont_w`, `p_surge_w`, `eff`, `idle_w`, `pure_sine` (Checkbutton)
>
> **Column 3 — Right panel:**
> 5. **Loads** — show each load as its own sub-`LabelFrame` using the load's `name` as title, with fields: `power_w`, `hours_per_day`, `load_type` (Entry, "AC"/"DC"), `surge_w`. The loads are hardcoded to the 5 loads from rules_engine.py's `builtin_example()` — no add/remove load feature needed.
>
> **Column 4 (or stacked below col 3):**
> 6. **Environment** — fields: `psh`, `t_min_c`, `pv_derate`
> 7. **Policy** — fields: `autonomy_hours`, `energy_margin`, `controller_headroom`, `fuse_factor`
>
> **Bottom — full width:**
> - A button labeled **"▶ Simulate"** (full width, prominent).
> - A `ScrolledText` widget (read-only, full width, ~15 lines tall) that shows the simulation output.
>
> **On startup:** populate all fields from `builtin_example()` in rules_engine.py.
>
> **On "Simulate" click:**
> 1. Read all field values, parse them to the correct Python types (float/int/bool/str/list).
> 2. Build a `SystemConfig` from the parsed values using the existing dataclasses.
> 3. Call `RuleEngine(cfg).evaluate()`.
> 4. Clear the output text box and write:
>    - First line: `✅ PASS` or `❌ FAIL` + `  Bus: XX V`
>    - Then the key metrics (same fields already printed in simulate.py's `print_result`).
>    - Then each failure's `summary` + `detail` on separate lines.
>    - Then any warnings.
> 5. On any parsing error, show the error message in the text box in red (use `tag_configure`).
>
> **Run with:** `python app.py` from the project folder (no args needed).

---

**Relevant files**
- rules_engine.py — import `RuleEngine`, all dataclasses, and `builtin_example()` from here (the `builtin_example` function is in simulate.py — agent should copy or import it from there)
- simulate.py — reuse `load_config_from_json` and `print_result` logic as reference for output formatting, but do not call the CLI main
- my_system.json — values reference only

**Verification**
1. Run `python app.py` — window opens without errors.
2. Click Simulate with default values — output shows `✅ PASS`.
3. Set battery `ah` to `50` → click Simulate → output shows `❌ FAIL` with battery Ah failure message.
4. Set inverter `pure_sine` unchecked → Simulate → warning appears in output.

**Decisions**
- Tkinter only — zero external dependencies, works in the existing .venv immediately.
- 5 loads are fixed (no add/remove) — keeps the UI simple and scoped.
- `battery_voltages_supported` is a comma-separated string field parsed to `[float]` — avoids a complex list widget.
- `pv_power_limit_by_batt_v` split into two plain fields (`pv_power_limit_12v`, `pv_power_limit_24v`) — avoids a dict widget.
- Output box replaces the terminal entirely — no separate window needed.