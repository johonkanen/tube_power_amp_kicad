# Power stage simulation (simulation plan, section 1)

Push-pull output stage, 4 tubes, Hammond 1650TA, answering Q1 (bias supply), Q2 (maximum anode
voltage) and Q3 (screen supply) from [docs/simulation_plan.md](../../docs/simulation_plan.md).

> **Provisional.** Second pass (2026-11-19) uses the section 0 models: EL34_R and 6L6GC_R
> (Reefman, measured), KT88_X and 6550_X (our datasheet fits). Their errors from the push-pull
> bench are applied as corrections below ([sim/models](../models/README.md)). Final numbers need
> our own tubes measured.

## Files

| File | What |
|---|---|
| `stage.py` | Netlist generator and ngspice runs: DC bias servo, transient drive, AC bias-noise gain |
| `run_power_stage.py` | Case matrix runner; `--quick` for EL34 only, `--tables` to rebuild tables from `out/raw.json` |
| `run_bias_law.py` | Bias tracking laws for power scaling (fixed 70% / Vg1 ∝ V_SCREEN / constant current) |
| `run_screen_sweep.py` | Separate V_SCREEN swept at V_ANODE 400 and 450 V: power against screen dissipation |
| `results/bias_law.md`, `results/bias_law.png` | Bias law comparison |
| `results/screen_sweep.md` | Screen voltage sweep |
| `run_screen_resistor.py` | Screen resistor (470 Ω-4.7k per tube) against V_SCREEN at V_ANODE 400 V |
| `results/screen_resistor.md`, `results/screen_resistor.png` | Screen resistor sweep |
| `results/bias_table.md` | Q1: Vg1 for the idle targets, bias resolution, bias-noise gain |
| `results/power_table.md` | Q2, Q3: power at 1% / 5% THD and full drive, dissipation, screen, supply current |
| `results/pout_vs_va.png`, `results/pg2_vs_va.png` | Summary plots |
| `out/` | Raw data (ignored by git) |

Run: `python3 run_power_stage.py` (about 12 minutes on 32 cores), `python3 run_bias_law.py`
(about 20 minutes), `python3 run_screen_sweep.py` (about 3 minutes), `python3 run_screen_resistor.py`
(about 8 minutes).

## Circuit

- 4 tubes, two per side. Each tube has its own coupling cap (0.1 µF), grid leak (220k) to its
  own bias source, grid stopper (5.6k), 1 Ω cathode shunt and 1k screen resistor.
- PI: antiphase sources, 10k output impedance, soft clip at 80 V peak.
- 1650TA: coupled inductors from the datasheet. Lp 11.2 H plate to plate (2.8 H per half),
  k = 0.99715 from the 63.72 mH leakage, 47 Ω primary DCR, 8 Ω tap with 0.294 Ω.
- V_ANODE: stiff source, 5 Ω, 100 µF. This models the regulated HV supplies, not a sagging
  rectifier supply.
- **Screen option A:** from V_ANODE through a 1k dropper. **Option B:** separate V_SCREEN =
  min(V_ANODE, 90% of the lowest Vg2 rating in the set).
- Bias: a behavioural servo in the DC operating point finds the Vg1 that gives the idle plate
  dissipation, then the transient runs with that bias fixed.
- 1 kHz sine, 16 drive levels from 5 V to 160 V peak, measured over the last 5 ms of 65 ms.

## Findings, second pass (2026-11-19)

The first pass (Koren models, git history) had zero screen current at idle and far too little
under drive. With models that get the screen current right, **screen dissipation at full
overdrive is the limit** that drives the answers below.

### Q3: screen supply

With the screen at the anode voltage, full overdrive (PI clipped, sine) overloads the screens at
450 V. Worst tube, from the screen sweep with the bench correction applied:

| Tube | Pg2 with screen = 450 V | Rating | Highest V_SCREEN within rating | Output at that screen, V_ANODE 450 V (10% THD, model) | Bench power error |
|---|---|---|---|---|---|
| EL34 | 8.8 W (at 400 V; 450 V exceeds Vg2 max) | 8 W | **about 370 V** | about 112-125 W | +29% (real lower) |
| 6L6GC | 6.6 W | 5 W | **about 395 V** | about 100 W | -10% (real higher) |
| 6550 | 12.4 W (at 400 V, its Vg2 max) | 6 W | **about 290 V** | about 70 W | -15..-18% |
| KT88 | 18.6 W | 8 W | **about 320 V** | about 90-100 W | -23% (real higher) |

- **Verdict: V_SCREEN stays a separately controlled supply (PS-2), and its setpoint is per tube
  type**, held well below V_ANODE at the high settings: about 290-320 V for 6550/KT88, about 370 V
  for EL34, about 395 V for 6L6GC. For a mixed set, the lowest of its tubes. Tied screens (option A)
  can't do this.
- The screen limit is for sustained full overdrive with 1k screen resistors.
- **Screen resistor (2026-11-19, results/screen_resistor.md):** sweeping Rg2 from 470 Ω to 4.7k per
  tube against V_SCREEN at V_ANODE 400 V shows that **a larger screen resistor doesn't buy power.**
  For each tube type, every Rg2 / V_SCREEN combination falls on nearly one curve of output power
  against screen dissipation. The screen rating sets the power; Rg2 only moves the point along the
  curve (raising Rg2 lets V_SCREEN go up by the same amount of power it takes away). Best within
  the rating:

  | Tube | Best Rg2 / V_SCREEN | P10% | Same as 1k at the D13 setpoint? |
  |---|---|---|---|
  | EL34 | 1k / 370 V | 110 W | yes |
  | 6L6GC | 1k / 390 V | 89 W | yes |
  | 6550 | 1k / 290 V | 60 W | yes (lower Rg2 is slightly better at the same dissipation) |
  | KT88 | 2.2k / 380 V | 91 W | 1k / 320 V gives 90 W |

  **Choice: one value, 1k per tube, for every tube type,** with the per-type limit set by the
  V_SCREEN setpoint in software (D13). The resistors are fixed on the board, so a single value
  is what lets the tube types be swapped and mixed (PA-3). A larger Rg2 would only add screen sag
  (compression) as a voicing choice, and can't be switched per channel.
- **Screen resistor rating:** about 0.5-0.7 W average at full overdrive (25 mA average); peaks
  of 60-120 mA per tube. Use 3-5 W flameproof resistors: they also act as the fuse in a screen arc.
- **V_SCREEN supply budget (HV supplies, second output):** about 100 mA average at sustained full
  overdrive (4 tubes, about 21-25 mA each), peaks of about 160-240 mA (two tubes per side
  conducting). A reservoir capacitor carries the peaks.
- Bias follows the screen voltage more than the anode voltage (pentodes), so a lower screen also
  means less negative bias.

### Q2: anode voltage for 100 W

With the screens at their per-type setpoints, 100 W (onset of clipping, about 10% THD, corrected
for the bench error) needs about **450 V at the centre tap** for EL34, 6L6GC and KT88. The
6550 reaches about 80-85 W at 450 V, and needs about 500 V or more screen (with larger screen
resistors) for 100 W.

- **Decided (2026-11-19): the HV rail stays at 430 V and the lower output power is accepted**
  (PA-6). With V_ANODE max assumed about 400 V (430 V less the HV supplies' headroom, D14) and the
  screens at their setpoints, the expected full power is (screen_sweep.md, V_ANODE 400 V,
  corrected by the bench power error):

  | Tube | V_SCREEN | Power at 10% THD | At full overdrive |
  |---|---|---|---|
  | 6550 | 290 V | about 70 W | about 100 W |
  | EL34 | 370 V | about 85 W | about 100 W |
  | 6L6GC | 390 V | about 98 W | about 115 W |
  | KT88 | 320 V | about 90-115 W | about 120-155 W |

  The KT88 and 6550 corrections rest on one datasheet point each; treat them as ranges.
- Supply current at 100 W is 450-500 mA, above the 1650TA's 403 mA DC rating (ask Hammond what
  the rating assumes; guitar duty is intermittent).
- The 5%-THD power figures in power_table.md are pessimistic for KT88_X and 6550_X: those models
  distort earlier than the datasheets show (bench THD 4-6% against 2.5-3%), so use 10% THD or
  full drive for them.

### Q1: bias supply

| Requirement | Provisional value | From |
|---|---|---|
| Output range | With the screens at their setpoints, Vg1 at 70% idle is -33 to -47 V at V_ANODE 450 V (KT88 at 400 V screen); about -5 V at the lowest settings. With ±20% tube spread and margin, about **-5 to -65 V**. The -80 V raw rail is then enough for a linear supply. | screen_sweep.md, bias_law.md |
| Resolution | 12-bit minimum (1 mA idle is about 80 mV of Vg1 at the most sensitive point) | bias_table.md |
| Noise | 100 µVrms per tube is enough, even behind a post-PI master | bias_table.md |
| Load current | Under 1 mA per tube (grid current at hard drive) | power_table.md |
| **Tracking law** | **Constant idle current below the reference setting, capped at 70% dissipation above it**: Ia_idle = min(I_ref, 0.7·Pa_max / Va). See below. | bias_law.md |

**Tracking law** (results/bias_law.md, bias_law.png):
- **Fixed 70% dissipation fails below about 250 V:** the bias pins at 0 V (grid current) and
  crossover distortion at 1 W reaches 4-7%.
- **Vg1 ∝ V_SCREEN** keeps the operating point's shape, but the idle current falls about as
  V^1.5, to 4-7% of Pa max at 150 V. Crossover at 1 W rises to 1-1.7% for the beam tetrodes. Above
  the reference it overshoots: 80-92% dissipation at 500 V.
- **Constant idle current** never pins, gives the lowest crossover distortion (0.3-1.3% at 1 W at
  150 V), and costs nothing in power. Above the reference voltage it reaches 79% dissipation,
  so cap it there.
- The cathode shunts (PA-4) already measure each tube's current, so **closed-loop bias on the
  measured current** implements this directly, with one target current per tube type and no
  table. Vg1 ∝ V_SCREEN serves as the feed-forward when the setting changes (the bias leads when
  the voltage goes up), and the current loop trims it.

### Mixed tubes (PA-3)

- One EL34 and one 6L6GC on each side behaves like a matched set (with per-tube bias).
- One type per side is not usable: even-harmonic distortion reaches 5% at 4-9 W (first pass).
  Allow mixing only within a side.
- V_SCREEN is shared, so a mixed set runs at the lowest screen setpoint of its tubes.

## Next

1. Measure our own power tubes (high-voltage curves) and refit; rerun all three runners.
2. Screen current on a guitar-like signal (crest factor, duty) instead of a sustained clipped
   sine: the V_SCREEN setpoints may go up if real playing dissipates less than the worst case.
3. Ultralinear (40% taps) as screen option C.
4. Loads: 0.5x, 2x, open, and a speaker impedance model.
5. Burst runs for blocking recovery; coupling cap and grid leak against bias shift.
6. Supply ripple and output impedance from the HV supplies' control loop.

**Updates for the shared documents** (applied 2026-11-20: open_decisions D13, SPECIFICATION PS-2,
system_architecture power table, docs/interfaces.md section 3):
- D13 (V_SCREEN setpoints): screen resistor fixed at 1k for all types; the setpoints stand.
- System architecture, power table: V_SCREEN about 100 mA average, about 0.25 A peak.
- HV supplies redesign (PS-2): the output that becomes V_SCREEN has R26 || R27 = 500 R in series on
  the built v2 board (HV supplies finding 11; intended there, because it fed the milliamp preamp).
  At the V_SCREEN budget (about 100 mA average) that is about a 50 V drop and 5 W, so it must be
  removed or made much smaller when the output is repurposed.
