# Energy Budget — How Each Number Is Calculated

The simulator's energy budget is **not fixed** — every number recalculates live from your inputs each time you click Simulate.

---

## Step by Step — with the default system values

### 1. DC loads — 1600.0 Wh

$$E_{DC} = \sum (P_{W} \times h/day) \quad \text{for all DC loads}$$

Only the amp is DC:

$$200\text{ W} \times 8\text{ h} = 1600\text{ Wh}$$

---

### 2. AC loads output — 840.0 Wh

$$E_{AC,out} = \sum (P_{W} \times h/day) \quad \text{for all AC loads}$$

XDJ (30 W) + Adam T5V (30 W) + Phones (20 W) + LED (25 W) = **105 W × 8 h = 840 Wh**

---

### 3. AC via inverter — 933.3 Wh

$$E_{AC,in} = \frac{E_{AC,out}}{\eta_{inv}} = \frac{840}{0.90} = 933.3\text{ Wh}$$

The extra 93 Wh is the inverter's **conversion loss**.  
A 90 % efficient inverter means the battery pays more than the load receives — the remaining 10 % becomes heat.

---

### 4. Inverter idle — 80.0 Wh

$$E_{idle} = P_{idle} \times autonomy\_hours = 10\text{ W} \times 8\text{ h} = 80\text{ Wh}$$

The inverter burns 10 W just staying on, even under zero load.  
This is significant for long runtimes — 8 h × 10 W = 80 Wh ≈ the same as running the XDJ all day.

---

### 5. Battery daily need — 2613.3 Wh

$$E_{bat} = E_{DC} + E_{AC,in} + E_{idle} = 1600 + 933.3 + 80 = 2613.3\text{ Wh}$$

This is how many watt-hours the battery must supply in one full day of use.

---

### 6. Design target (+margin) — 3005.3 Wh

$$E_{design} = E_{bat} \times margin = 2613.3 \times 1.15 = 3005.3\text{ Wh}$$

The **15 % headroom** (`energy_margin = 1.15` in the Policy panel) is a safety buffer.  
Battery sizing is calculated against this inflated number — not the raw daily need.

> **Why add margin?**  
> Batteries degrade over time, real-world PSH varies, wiring losses accumulate.  
> A 15 % buffer ensures the system still works after 2–3 years of use.

---

## What changes these numbers?

| Change | Effect |
|---|---|
| Increase amp power (DC) | Raises `DC loads` and `Battery daily need` directly |
| Add an AC load | Raises `AC loads output`, and also `AC via inverter` (÷ efficiency) |
| Lower inverter efficiency | `AC via inverter` increases — poor efficiency wastes more |
| Increase `Idle draw (W)` | Raises `Inverter idle` proportionally |
| Change `Autonomy (h)` | Scales `Inverter idle` — also used for battery Ah sizing |
| Raise `Energy margin` | Raises `Design target` — larger battery required |

---

## Series vs Parallel — Solar Panels

These change **voltage** and **current** independently. Total power is always:

$$P_{total} = series \times parallel \times P_{panel}$$

| Wiring | Voltage | Current | Example (400 W / 22 Voc / 18.5 Vmp panel) |
|---|---|---|---|
| **2 series** | doubles | unchanged | Voc = 44 V, Vmp = 37 V, Isc = 22.5 A |
| **2 parallel** | unchanged | doubles | Voc = 22 V, Vmp = 18.5 V, Isc = 45 A |
| **2S × 2P** (default) | doubles | doubles | Voc = 44 V, Vmp = 37 V, Isc = 45 A, total = 1600 W |

### Why series matters here

The MPPT controller needs panel Vmp to exceed the battery charge voltage plus a margin:

$$V_{mp,string} > V_{charge} + V_{margin} = 28.8 + 3.0 = 31.8\text{ V}$$

A single panel gives Vmp = 18.5 V → **fails**. Two in series gives 37 V → **passes**.

### Why parallel matters

It multiplies charge current. The 4-panel array pushes ~55 A estimated into a 60 A controller — close to the limit.  
Add a 3rd parallel string → hits the `ctrl_current` failure.

### Rule of thumb

| Goal | Action |
|---|---|
| Need higher voltage to reach MPPT window | Add panels in **series** |
| Have enough voltage, want more power | Add panels in **parallel** |
| Reduce cold Voc risk | Fewer panels in **series** |
| Increase total energy without changing voltage | More panels in **parallel** |

---

## Key Formulas Reference

| Rule | Formula |
|---|---|
| Minimum battery Ah | $E_{design} \div (DoD \times V_{bus})$ |
| Design energy | $(E_{DC} + E_{AC} \div \eta + E_{idle}) \times margin$ |
| Minimum PV power | $E_{battery,day} \div (PSH \times derate)$ |
| Cold Voc (string) | $V_{oc,stc} \times [1 + \lvert\beta\rvert \times (25 - T_{min})] \times series$ |
| Estimated charge current | $P_{array} \div V_{charge}$ |
| Bus voltage forced to 24 V | Any DC load ≥ 22 V, or inverter = 24 V, or DC load > 600 W |
