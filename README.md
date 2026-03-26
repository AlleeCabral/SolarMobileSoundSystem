# Solar / Battery Mobile Sound System — Simulator

A Python rule engine that validates whether a set of electrical components (solar panel, battery, MPPT controller, inverter, and loads) forms a safe and functional off-grid sound system. Swap any component value in the JSON config and instantly get a PASS/FAIL result with detailed electrical explanations.

---

## Files

| File / Folder | Description |
|---|---|
| `app.py` | **Tkinter desktop UI** — the main file to run; pre-filled with your system |
| `rules_engine.py` | Core rule engine — all electrical logic, data models, and failure explanations |
| `simulate.py` | CLI runner — loads a config and prints the full simulation report |
| `my_system.json` | Reference JSON config (from the diagram) — values are mirrored in the UI |
| `Theory/` | Electrical theory notes: energy budget formulas, series/parallel explained |
| `ForMac/` | macOS distributable — py2app config + GitHub Actions workflow that auto-builds a `.dmg` |
| `.venv/` | Python virtual environment — no external packages required (stdlib only) |

---

## Requirements

- Python 3.8 or newer
- No external packages — uses only the Python standard library (`dataclasses`, `json`, `math`, `typing`, `sys`)
- `tkinter` (included with the standard Python installer on Windows and macOS; on Linux install `python3-tk`)

---

## Setup

Activate the virtual environment once before running:

**Windows (PowerShell):**
```powershell
.\.venv\Scripts\Activate.ps1
```

**Windows (Command Prompt):**
```cmd
.venv\Scripts\activate.bat
```

**macOS / Linux:**
```bash
source .venv/bin/activate
```

You will see `(.venv)` appear in your prompt when it is active. No packages need to be installed.

---

## Running the Simulator

### Option 1 — Desktop UI (recommended)
```powershell
python app.py
```
The window opens pre-filled with your system. Edit any field and click **▶ Simulate**. A colour-coded flowchart shows which components are failing.

### Option 2 — Command line, built-in example
```powershell
python simulate.py
```

### Option 3 — Command line with a JSON config file
```powershell
python simulate.py my_system.json
```

---

## How to Simulate a Different Setup

### Using the UI (easiest)
1. Run `python app.py`.
2. Edit any field directly in the window — battery capacity, panel count, load wattage, etc.
3. Click **▶ Simulate**.
4. The output box explains every pass/fail with a WHY and a FIX. The flowchart turns green (pass) or red (fail).

### Using the JSON config (CLI)
1. Open `my_system.json` in any text editor.
2. Change any component value — for example:
   - Increase `battery.ah` from `150` to `200`
   - Change `pv_array.series_count` from `2` to `1`
   - Set `battery.v_nom` to `12` to test a 12 V system
   - Change `inverter.p_cont_w` to a lower value to test undersizing
3. Save the file and run `python simulate.py my_system.json`.

The simulator will tell you whether the system passes all electrical checks and, if not, exactly which rule failed and how to fix it.

---

## Understanding the Output

```
Status       : ✅  PASS   (or ❌  FAIL)
Bus Voltage  : 24 V       (auto-derived from components)
```

### Energy Budget
Shows daily Wh consumption broken down by DC loads, AC loads (converted through the inverter), inverter idle draw, and the design safety margin (+15% in balanced mode).

### Battery
- **Minimum Ah needed** — the absolute minimum capacity to sustain all loads for 8 hours given the battery's depth-of-discharge setting
- **Continuous bus draw** — steady-state current in Amps from the battery
- **Surge bus draw** — peak current at startup; must not exceed BMS peak rating

### Inverter
- Min continuous and surge required vs. what is installed
- A warning is shown if the inverter is not pure-sine (modified-sine damages audio gear)

### PV Array
- **Minimum needed** — calculated from daily energy need ÷ (peak sun hours × system derate factor)
- **Cold Voc** — open-circuit voltage corrected for the coldest expected temperature; must stay safely below the controller's input limit
- **Estimated charge current** — must stay within the controller's rated maximum

### Protection
Minimum fuse and cable ratings for the main battery line and controller-battery cable, calculated at 125% of continuous current.

### Failures
Each failure includes:
- A one-line summary of what failed
- A `WHY:` explanation of the electrical risk
- A `FIX:` with a concrete corrective action

---

## Config Reference (`my_system.json`)

### `loads[]`
| Field | Type | Description |
|---|---|---|
| `name` | string | Label for this load |
| `power_w` | number | Rated power in Watts |
| `hours_per_day` | number | Hours of use per day |
| `load_type` | `"DC"` or `"AC"` | DC loads connect directly to the battery bus; AC loads go through the inverter |
| `required_voltage` | number (optional) | Fixed DC voltage required (e.g. `24` for a 24 V amp — forces 24 V bus) |
| `surge_w` | number | Peak startup power in Watts (0 if unknown) |

### `battery`
| Field | Description |
|---|---|
| `v_nom` | Nominal voltage (12 or 24 V) |
| `ah` | Capacity in Amp-hours |
| `dod_max` | Max depth of discharge — use 0.85 for LiFePO4 |
| `bms_cont_a` | BMS continuous discharge current rating |
| `bms_peak_a` | BMS peak/surge current rating |

### `inverter`
| Field | Description |
|---|---|
| `v_in` | DC input voltage — must match the battery bus voltage |
| `p_cont_w` | Continuous AC output power rating |
| `p_surge_w` | Surge/peak AC output power rating |
| `eff` | Efficiency as a decimal (e.g. `0.90` = 90%) |
| `idle_w` | Standby power draw when on but under no load |
| `pure_sine` | `true` = pure sine, `false` = modified sine (pure sine required for audio) |

### `pv_array.panel`
| Field | Description |
|---|---|
| `p_stc_w` | Rated power at Standard Test Conditions (W) |
| `voc_stc` | Open-circuit voltage at STC (V) |
| `vmp` | Max-power voltage at STC (V) |
| `isc` | Short-circuit current at STC (A) |
| `imp` | Max-power current at STC (A) |
| `beta_voc_pct_per_c` | Temperature coefficient for Voc in %/°C (negative, e.g. `-0.30`) |

### `pv_array`
| Field | Description |
|---|---|
| `series_count` | Panels wired in series — multiplies voltage |
| `parallel_count` | Strings wired in parallel — multiplies current |

### `controller`
| Field | Description |
|---|---|
| `type_` | `"MPPT"` (recommended) or `"PWM"` |
| `battery_voltages_supported` | List of supported battery voltages, e.g. `[12, 24]` |
| `pv_max_voc` | Absolute maximum PV input voltage — from the controller datasheet |
| `charge_a_max` | Maximum charge output current (A) |
| `pv_power_limit_by_batt_v` | Max PV input power per battery voltage, e.g. `{"12": 800, "24": 1600}` |
| `requires_vmp_margin_v` | MPPT minimum margin: panel Vmp must exceed charge voltage by this much (default 3 V) |

### `environment`
| Field | Description |
|---|---|
| `psh` | Peak Sun Hours at your location per day (e.g. 4–6 for most of Europe/Brazil) |
| `t_min_c` | Coldest expected temperature in °C (used for cold Voc calculation) |
| `pv_derate` | Overall system efficiency derate: accounts for temperature, wiring, dust, MPPT losses (default 0.75) |

### `policy`
| Field | Description |
|---|---|
| `autonomy_hours` | Target runtime with no solar input (default 8) |
| `energy_margin` | Multiply daily energy need by this before sizing battery (1.15 = +15% headroom) |
| `controller_headroom` | Safety factor applied to cold Voc check (1.10 = 10% safety margin) |
| `fuse_factor` | Fuse/cable rating multiplier above continuous current (1.25 = 125%) |

---

## Key Electrical Rules (summary)

| Rule | Formula |
|---|---|
| Minimum battery Ah | `E_design ÷ (DoD × V_bus)` |
| Design energy | `(E_DC + E_AC÷η_inv + E_idle) × margin` |
| Minimum PV power | `E_battery_day ÷ (PSH × derate)` |
| Cold Voc (string) | `Voc_stc × [1 + |β| × (25 − T_min)] × series_count` |
| Est. charge current | `P_array ÷ V_charge` |
| Bus voltage 24 V trigger | Any DC load at ≥ 22 V, or inverter input = 24 V, or DC load > 600 W |

---

## Example — Effect of changing the amp to 24 V DC

If the amp requires 24 V DC:
- The bus voltage is forced to **24 V**
- The battery must be a 24 V pack
- The inverter must have a 24 V DC input
- The MPPT controller must support 24 V charging
- The solar panel Vmp (per series string) must exceed ~31.8 V (28.8 V charge + 3 V margin)
- A single 22 Voc / 18.5 Vmp panel **cannot** string to 24 V charging — two in series (Vmp = 37 V) passes
