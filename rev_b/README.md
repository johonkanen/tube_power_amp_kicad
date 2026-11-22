# Power amp rev B: schematic (second pass)

The next power amp board (4 octal output tubes, per-tube cold-by-default bias, cathode-current
measurement, over-current trip, hardware HV inhibit), drawn from the project's own documents and
simulations in [tube_amplifier_kicad](https://github.com/johonkanen/tube_amplifier_kicad):
`docs/bias_supply.md` + `sim/bias_supply` (bias supply, sense chain, trip), `docs/interfaces.md`
IF-1.1 (connectors, ribbons 6.1 / 6.3, map 7.3, safety lines 8), `docs/grounding.md`,
`sim/power_stage` (1k screen resistors, grid stoppers, bias range), SPECIFICATION.md PA-1..PA-6,
SAFE-1..SAFE-6, PS-2. Rev A (the 2010 `OUTPUT` board) at the repo root is frozen and not touched;
`rev_b/` is its own p2k board root (`p2k_config.py`, PROJECT `tube_power_amp_revb`).

Scope of this pass (2026-11-21): initial schematic, interface viability check, what has been
missed. **No layout, no footprints yet.** The check results, missed items, missing simulations and
missing requirements are in [STATUS.md](STATUS.md).

## Second pass (2026-11-23)

Brought into line with interfaces.md **IF-1.2** and the bias decisions of 2026-11-22
(bias_supply.md "Corrections 2026-11-22" / "Proposed wording", review 7.1). Interface check, open
items and next steps: [STATUS.md](STATUS.md) "Second pass". Footprints are assigned on every part
(`lib/footprint_map.csv`) and a first BOM is in [bom/tube_power_amp_revb_bom.csv](bom/tube_power_amp_revb_bom.csv).

**ERC (KiCad 10.0.7): 0 errors, 1 warning** (the same as the first pass: ADS7828 REF on the ADR4525
output, intended). **326 parts** (units counted once; 157 R, 77 C, 31 Q, 28 D, 16 U, 9 J, 4 net ties,
4 tubes), 97 BOM lines, 5 sheets.

### What changed, decision by decision

| # | Decision / request | What is drawn now | Why / check |
|---|---|---|---|
| 1 | Sense filter: two real poles, 47k / 220 nF twice (5.3 / 40 Hz) | Per tube a second 220n (A2n to KELVn), the old 330n now 220n (sheet 04). Gain set to exactly 10.0: 9.09k / **1.01k** 0.1 % (9.09k / 1k was 10.09, +0.9 %) | Master `run_sense_filter.py` variant `two_real_220` is this circuit: 25 ms to 400 mA, 45-50 ms mirror short, 13 mA pp at 82 Hz |
| 2 | 72 V string (2x 36 V) with 3.3k | 2x **BZT52H-B36** (SOD123F, ±2 %), 3.3k 1206 | TC checked against the Nexperia datasheet: SZ 30.4 / 33.0 / 37.4 mV/K at 2 mA, the figures the master's tolerance run used, so **no re-run of the corner check is needed**. New: self-heating. SOT-23 (BZX84) is 500 K/W: 2.4 mA x 36 V = 86 mW = +43 K per zener, +2.8 V on the string. BZT52H on 1 cm² cathode copper is 150 K/W: +12 K, about +0.8 V on the string at -80 V. That only makes VNC more negative (colder; the weakest-VNC corner, cold board at -78 V, carries the least current), and in the regulation corner (70 °C, +2 %, -78 V, 0.4 mA) it adds 2 K / 0.13 V, so the string stays in regulation. Choose SOD123F with the copper, not SOT-23 |
| 3 | BIAS_OK from two hardware monitors + "+15 V present", independent of BIAS_EN | Sheet 02, one LM2901B (U202): VNC monitor (169k + 234k / 29.4k 0.1 %, 3.57M hysteresis), rail monitor (271k / 16.9k 0.1 %, 7.32M), **+15 V monitor** (trip 13.0 V against VREF2V5, so it doesn't lean on VREF10), diode-OR into MON_FAULT (clamps every channel), fourth unit makes BIAS_OK_PRE (pulled up from +15 V) → 74LVC2G17 Schmitt → BIAS_OK_A. LM4040**A**10 (0.1 %) fed by 1.0k (was 2.2k: VREF10 now regulates down to 11.5 V of +15 V); low-leakage BAS416 clamps on the monitor nodes | `sim/bias_supply/monitors.py` → [results/monitors.md](sim/bias_supply/results/monitors.md): real circuit, 0-85 °C Monte Carlo. VNC trip -62.10 to -63.90 V, release -63.6 to -65.44 V (at 0 °C, where the weakest VNC -66.4 V sits: -65.08 V worst, 1.3 V clear); rail trip -73.95 to -76.05 V, release worst -76.57 V (1.2 V clear of the lowest rail -77.8 V); SPICE sweep of the drawn block: -62.98 / -64.51 V, -75.00 / -75.49 V, 13.00 / 13.25 V. Start-up with six rail orders and slow ramps: BIAS_OK never high while VNC, the rail or +15 V is outside its window; high 84-88 ms after the rails are good. -80 V lost with the HV on: BIAS_OK low after 28-65 ms, bias drift 0.02 V |
| 4 | Over-current 220 mA ±5 %, latched, powers up tripped; expander required | LM2901B (was LM339: 0-70 °C part), VOC 39k / 11k **0.1 %**, ADC/comparator clamp BAV199 (BAT54S leakage at 85 °C would be up to 2.5 mA of reading error through the 1k), latch ~R/D through the Schmitt (first-pass item: slow RC into a non-Schmitt 74HC74 input). Expander fitted (U501) | Worst-case threshold error **±3.4 %**: LM4040A 0.1 % + 100 ppm/K x 60 K = 0.7 %; divider 0.2 % + TCR 0.3 %; shunt 1 % + 50 ppm/K x 75 K = 1.4 %; gain 0.2 % + 0.3 %; offsets 0.3 % |
| 5 | -80 V: 25 mA, ±2 V, 10 Ω fusible, no hold-up | R201 10R 1 W fusible wirewound (CRF251-4 class), C201 100 µF kept (it is what the BIAS_OK timing assumes) | Current with the monitors and ADC dividers: **5.4 / 14.2 / 21.3 mA** (cold / typical / hot end, typical board), about 22.7 mA worst case (master 22.0 + 0.7 mA of dividers) — inside 25 mA. Open: the 8 A / 0.32 J inrush of C201 through the fusible part (datasheet gives energy 0.9 W·s but no peak-current time base) |
| 6 | BIAS_EN: ≥ 470 Ω or a buffer, re-check the pump | R230 **1k** in series with the pump capacitor, hold resistor R231 **56k** (was 100k) | monitors.md section 5: 74AHCT + 100 Ω + 100 Ω + 1k: **3.8 mA peak** (8 mA rating); release 1.2-4.5 ms; cold 123-131 ms (2N7002 Vth 1.0 V) / 76-79 ms (2.5 V) after stopping high or low, at 5, 10 and 15 kHz. With 100k the 5 V drive charged the pump higher and the cold time grew to 184-202 ms. No buffer needed |
| 7 | W24 280 V DC, up to 390 V | Coupling caps 630 V MKP on a 15 mm footprint (47n or 100n fit); grid leaks axial 0207, 350 V (blocking transients put -240 V across them) | **The KK-396 header is rated 250 V** (Molex 26-60-4050 sheet; JST VH 250 V too): it fails. TE MTA-156 (3.96 mm) is rated 600 V AC, Molex Mini-Fit Jr 600 V AC/DC. Footprint kept as a marked placeholder. STATUS proposal P1 |
| 8 | Grid leak / coupling cap OPEN; max fixed-bias grid resistance | 47n / 100k drawn, marked OPEN, footprints take 100n and 220k | See "Grid circuit resistance" below: the limit is **50 kΩ (6550, Tung-Sol)**, then 100 kΩ (6L6GC; KT88 GEC) |
| 9 | Grounding: bias, DAC, ADC on AGND; DGND island; ~100 Ω crossings | Unchanged from the first pass (it already matched): GND = AGND star at J101-2; GNDD island with J501, J502, U501, J201-2; soft tie 10 Ω ‖ 100 nF; 100 Ω on I2C, BIAS_EN, BIAS_OK, OC_TRIP_N, HV_PERMIT_MON, OC_CLR, HV_REQ | — |
| 10 | 70 °C under the plate | Every IC now rated to 125 °C except **LM4040-10 (I grade only, 85 °C)**, **ADS7828E (85 °C)** and PC817 (100 °C); electrolytics 105 °C; the zener filter capacitor is ceramic (an electrolytic's 3 µA leakage through 100k would move VNC 0.3 V) | Placement below |

### Grid circuit resistance (fixed bias), from the tube datasheets

| Tube | Fixed bias max | Cathode bias max | Source |
|---|---|---|---|
| EL34 | 500 kΩ (Philips class B; Mullard, Tung-Sol EL34B, New Sensor) | 700 kΩ | Philips 1959, Mullard 1962, Tung-Sol EL34B |
| 6L6GC | **100 kΩ** (GE, RCA, Tung-Sol) | 500 kΩ | GE ET-T1515A, RCA 8-60, Tung-Sol 1960 |
| KT88 | **100 kΩ** (GEC 1959); Gold Lion reissue 220 kΩ below 35 W, 100 kΩ above | 220 kΩ (GEC) | GEC Issue 2, Genalex 2002 draft |
| 6550 | **50 kΩ** (Tung-Sol) | 250 kΩ | tungsol.com 6550 sheet (GE 6550A not found) |

The DC grid circuit here is grid leak + 1k (bias output) + the bias source (a few Ω) + 5.6k
stopper: 107 kΩ with 100k, 227 kΩ with 220k. **The limit that sets it is 6550 at 50 kΩ**; with 6550
excluded it is 100 kΩ (6L6GC and KT88), which 100k + 6.6k already exceeds by 7 %. 220k exceeds
every type except EL34. The datasheet limit guards against runaway from grid (gas, leakage)
current with a fixed bias; here the bias is a closed firmware loop on each cathode current plus a
220 mA hardware trip, which catches a slow runaway, but that is an argument, not a rating.
Options for the user: keep ≤ 100k (and accept ~2x the 6550 rating, or drop the 6550 from the list),
or meet the 6550 too with 39k + 270n / 630 V (45.6 kΩ in all, 15 Hz like 100n / 100k), which costs
drive: two 39k per side load the PI's ~40 kΩ plate to about 20 kΩ, half the swing the PI + FX
simulations assumed. Decision with the PI + FX open-load simulation (interfaces.md 14).

### Placement and temperatures (for the layout pass)

The board hangs under the plate with the sockets on the solder side; the tubes stand above the
plate, so the board sees the 70 °C air, the hot socket pins (about 100 °C and more within 10 mm of
a power-tube socket) and the four 5 W screen resistors (up to about 1.6 W each in overdrive) below it.
- Sockets in the front strip as built; screen resistors, shunts, S3M diodes, coupling caps and grid
  parts next to their socket; the anode / screen / tab region at the end toward the HV supplies.
- **Reference end** (LM4040, the two 0.1 % monitor dividers, the zener string, ADR4525, DAC,
  ADC, the sense op amps' gain resistors): the rear edge, at the low-voltage end next to the
  ribbons, at least 40 mm from the nearest socket centre and not above or beside a screen resistor.
  Assumed **70 °C air + up to 15 K = 85 °C** (the Monte Carlo above runs at 0 / 25 / 85 °C); this is
  what the LM4040-10 and ADS7828 (85 °C parts) allow, with no margin.
- **Op amps and comparators** (OPA4197, LM2901B, 125 °C parts): in the same rear strip; assumed 85 °C.
- **300 V transistors** (MMBTA92 mirrors, MMBTA42 followers, BSP92P): between the reference end and
  the sockets, at least 25 mm from a socket; assumed **90 °C**. Leakage there is a bias error that
  the firmware loop removes; vendor data at temperature is still to check (S1).
- Measure the real board temperature (M39) before freezing the 85 °C parts.

### V_ANODE current

The board carries the whole plate current from J101 to the OT centre tap on J104 (OT_CT = V_ANODE):
**about 0.57 A average for a KT88 set at full sine overdrive** (more than the 0.5 A peak budget),
with peaks above that at the clipping edges. The board needs: V_ANODE / OT_CT copper and the 4.8 mm
tabs sized for the HV supplies' 1.0 A trip continuously (tabs are good for several A; traces 2.5 mm
in 2 oz or more). The figure to put in the budget is the HV side's question (review X35); from this
board: 0.6 A average, 1.0 A sized.

## Build

```
python3 rev_b/tools/make_lib.py          # lib/tube_power_amp_revb.kicad_sym from KiCad's stock libraries (flattened)
python3 rev_b/tools/make_project.py      # project, root sheet, empty sub-sheets
python3 rev_b/tools/make_footprints.py   # board-local footprints (octal, 5 W, blade-tab placeholders), fp-lib-table
python3 rev_b/tools/sheets/draw_all.py   # draws all five sheets, writes lib/footprint_map.csv and bom/*.csv
python3 rev_b/sim/bias_supply/monitors.py   # second pass: monitors, start-up, -80 V lost, pump -> results/monitors.md
python3 rev_b/sim/checks.py              # first pass (76 V string, old bias.py): kept for the record
cd rev_b/kicad && ../../tools/p2k/bin/kicad-cli sch erc tube_power_amp_revb.kicad_sch
```

The sheets are generated: edit `tools/sheets/draw_all.py`, not the `.kicad_sch` files, until the
draft is frozen. Drawing style is netlist-first (parts on a grid, a wire stub and a label on every
pin), exact for ERC and the netlist; a tidy layout pass comes later. The one change to a stock
symbol: the EL34's pins 1, 3, 8 are passive (two anodes share OT_A / OT_B; the stock types fail ERC).

**ERC (KiCad 10.0.7): 0 errors, 1 warning**, explained: ADS7828 `REF` (bidirectional) on the
ADR4525 output (power output). It is intended: the ADC uses the external 2.5 V reference shared
with the DAC, so the firmware must keep the ADC's internal reference off (command byte PD1 = 0).
301 symbols (units of a part counted once; 4 tubes, 4 net ties included), 216 nets.

| Sheet | Contents |
|---|---|
| 01 Output stage | 4 octal sockets V1-V4 (solder side as built), per tube 47n/630 V coupling cap, 100k grid leak to its own BIASn, 5.6k grid stopper, 1k 5 W flameproof screen resistor from V_SCREEN, 1 Ω 1 W cathode shunt with an S3M across it and a net-tie Kelvin tap (KELVn); pin 1 tied to pin 8 as built; heaters floating on pins 2 / 7. Tabs J101-J104, drive header J105. Optional anode flyback clamps (2x UF4007 per side, SAFE-5). HF decoupling 100n/630 V on V_ANODE / V_SCREEN (proposal) |
| 02 -80 V and VNC | J201 (-80 V, BIAS_RTN on DGND), 10 Ω fusible, reverse clamp, 100 µF hold-up; 76 V zener string (BZX84-B33 + -B43, 2 %), 100k / 10 µF filter with speed-up diode, two BSP92P followers (10 Ω each) → VNC ≈ -73.7 V, 47k / 100k / 10 µF. LM4040-10 reference (VREF10, VREF5). VNC monitor LM393: VNC_FAULT (15 V, clamps every channel) and BIAS_OK_A (pulled up from +15 V, so a missing +15 V is "not OK"); trip at VNC ≈ -68.4 V with 1.4 V hysteresis. Watchdog: BIAS_EN → 100n → BAT54S pump → 1 µF ‖ 100k → 2N7002 → CLAMP_WD |
| 03 Bias DAC + channels | DAC7578 (8-ch 12-bit I2C, power-on to zero, 4 channels used) on an ADR4525 2.5 V reference (VREF2V5, shared with the ADC); ~CLR pulled low while the watchdog clamps, so the DAC returns to zero whenever BIAS_EN stops. Per channel as [BIAS]: 10k / 330n / 1M, two 2N7002 clamps (CLAMP_WD, VNC_FAULT), OPA4197 + MMBT3904 V-to-I (1k), MMBTA92 mirror at +15 V (1k emitters), 30k ‖ 100n to VNC, MMBTA42 follower with 2x 22k (midpoint 1 µF) to -80 V, 1k / 1 µF to BIASn |
| 04 Sense, ADC, trip | Per tube: 10k / 10n, 47k + 47k into 330n (two real poles, as simulated), OPA4197 gain 10 (9.09k / 1k to KELVn), 1k / 100n to ISNSn with a BAT54S clamp: 10 V/A, 0-2.5 V = 0-250 mA. ADS7828 (8-ch 12-bit I2C): CH0-3 currents, CH4 VNC, CH5 -80 V, CH6 +15 V, CH7 spare. LM339 comparators at VOC = 2.20 V (220 mA) wired-OR into OC_ANY_N; 74HC74 latch: tripped at power-on (100k / 1 µF on ~R), set again only by an OC_CLR edge with no comparator tripped |
| 05 Control and safety | J501 template ribbon (W14-b), J502 bias ribbon (W15-b), both on the DGND island (GNDD); soft tie 10 Ω ‖ 100 nF to GND (AGND); MCP23S17 (addr 000) GPA0 OC_CLR, GPA1 HV_PERMIT_REQ with 100k pull-downs; 100 Ω crossings for I2C, BIAS_EN, BIAS_OK, OC_TRIP_N, HV_PERMIT_MON, OC_CLR, HV_REQ; 4.7k I2C pull-ups. Warm-up timer: isolated heater sense (330 Ω, MB1S bridge, 2.4 V zener, PC817), 74HC4060 at 267 Hz, Q14 after 31 s, latched by a diode stop; cleared while the heater is absent and by a power-on pulse. HV_PERMIT: 74LVC1G11 + 74LVC1G08 (BIAS_OK AND OC_OK AND WARM_OK AND HV_PERMIT_REQ) drive the high-side PNP; OC_OK alone drives the low-side NPN; loop +15 V → 1.3k → monitor opto (HV_PERMIT_MON) → J503 (W16-a) → HV supplies' opto → back → low side: 9.4 mA |

## First pass (2026-11-21)

The tables below are the first pass; where the second pass changed something the section above wins.

## Interface connectors (refs for interfaces.md section 2)

| Cable end | Ref | Type | Pins |
|---|---|---|---|
| W04-b | J101 | 2 blade tabs, 4.8 mm | 1 V_ANODE, 2 GND_PWR (= GND, the local star) |
| W05-b | J102 | 1 blade tab, 4.8 mm | 1 V_SCREEN |
| W06-b | J103 | 2 blade tabs, 6.3 mm | 1 HTR1, 2 HTR2 (floating) |
| W11-a | J104 | 3 blade tabs, 4.8 mm | 1 OT_A (V1, V2 anodes), 2 OT_B (V3, V4 anodes), 3 OT_CT (= V_ANODE) |
| W24-b | J105 | Lock-3.96 1x5 | 1 GND, 2 DRV_A, 3 GND, 4 DRV_B, 5 GND |
| W09-b | J201 | 2 blade tabs, 4.8 mm | 1 -80V, 2 BIAS_RTN (GNDD) |
| W14-b | J501 | IDC-2.54 2x7 (template 6.1) | as interfaces.md 6.1 (MUTE_ALL_N 100k pull-down, unused) |
| W15-b | J502 | IDC-2.54 2x5 (6.3) | 1 GND, 2 SCL, 3 GND, 4 SDA, 5 GND, 6 BIAS_EN, 7 BIAS_OK, 8 OC_TRIP_N, 9 HV_PERMIT_MON, 10 GND |
| W16-a | J503 | Lock-2.54 1x2 | 1 HV_PERMIT+, 2 HV_PERMIT- |

## I2C addresses and the over-current threshold (for interfaces.md 6.3)

| Device | Part | 7-bit address |
|---|---|---|
| Bias DAC | DAC7578 (TSSOP-16), ADDR0 = GND | **0x48** |
| Current ADC | ADS7828 (TSSOP-16), A1 = A0 = 1 | **0x4B** |

The bus is point to point on W15, 5 V, 100 kHz, 4.7k pull-ups on this board. Over-current
threshold: **2.20 V = 220 mA average** per tube (10 V × 11k / 50k from the 10 V reference), all tube
types; the firmware adds per-type limits.

## Rail currents (interfaces.md 3.2)

| Rail | Typical (bias about -30 V) | Max | Notes |
|---|---|---|---|
| -80 V | 13 mA | **19.4 mA** | sim (rev_b/sim/checks_results.md): 3.1 mA all cold, 13.4 mA at -28 V, 19.1 mA at full scale, + 0.25 mA for the monitor / ADC dividers. **Over the 13.4 mA allocation** (STATUS.md) |
| +15 V | 37 mA | 45 mA | mirrors 2 x Ic (20 mA at full scale), 2x OPA4197 (8 mA), LM339 / LM393 (1.2 mA), VREF10 (2.3 mA), pull-ups (2 mA), HV_PERMIT loop 9.4 mA + its drive (1.5 mA) |
| -15 V | 9 mA | 10 mA | the two OPA4197 |
| +5 V | 5 mA | 8 mA | DAC, ADR4525, ADC, MCP23S17, logic, I2C pull-ups, opto pull-ups |
| Heaters | 6.0 A (4x EL34) | 6.4 A (KT88) | 3.6 A with 6L6GC; + 4 mA for the warm-up sense |
| V_ANODE / V_SCREEN | — | 0.5 A / 0.25 A peak | through the board to the OT and the screens (power stage figures) |
