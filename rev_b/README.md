# Power amp rev B: initial schematic

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

## Build

```
python3 rev_b/tools/make_lib.py          # lib/tube_power_amp_revb.kicad_sym from KiCad's stock libraries (flattened)
python3 rev_b/tools/make_project.py      # project, root sheet, empty sub-sheets
python3 rev_b/tools/sheets/draw_all.py   # draws all five sheets (overwrites them)
python3 rev_b/sim/checks.py              # quick ngspice checks -> paste into sim/checks_results.md
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
