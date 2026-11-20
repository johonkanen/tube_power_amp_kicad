# Power amp rev B: status

2026-11-21, initial schematic session. What is drawn and how to build it: [README.md](README.md).
Contract: tube_amplifier_kicad `docs/interfaces.md` IF-1.1. Nothing here changes it; the changes
this board needs are listed as proposals (section 3) for the coordinating session.

## 1. Interface check

One row per interface item that touches the power amp. **OK** = viable as written; **problem** =
does not work as written (a proposal follows in section 3); **question** = works, but something
must be confirmed by another board or the user.

| # | Item (interfaces.md section) | Verdict | Notes |
|---|---|---|---|
| 1 | W04-b V_ANODE + GND_PWR, 4.8 mm tabs (2.1, 4.3) | OK | 0.5 A peak; one ground entry, the local star (J101 pin 2) |
| 2 | W05-b V_SCREEN, 4.8 mm tab (2.1) | OK | 0.25 A peak, returns through GND_PWR |
| 3 | W06-b heaters, 6.3 mm tabs, 6.0-6.4 A (2.1, 3.1, 4.3) | question | Tabs fine. "6.3 V ±5 % at the sockets": 6.4 A through 2x (lead + 2 tabs + receptacles) costs 0.1-0.2 V; who regulates the socket voltage (set point, remote sense)? See requirement Q5 |
| 4 | Heater reference: none on this board, heaters float (5) | OK | No connection from HTR1 / HTR2 to GND; the warm-up sense is opto-isolated so it works at 0 V or +90 V (elevated option). EL34 Vhk 100 V max against +90 V: inside, but only 10 V margin |
| 5 | W09-b -80 V + BIAS_RTN tabs (2.1, 4.3, 5) | OK | BIAS_RTN on the DGND island, the -80 V current returns through GND_PWR, as grounding.md 4 |
| 6 | -80 V allocation 13.4 mA (3.1, 3.2, 3.3, 14) | **problem** | Needs **19.4 mA** with all four tubes at the hot end (low power settings, Vg1 near 0); 13.4 mA covers only bias ≤ -28 V on all four. Proposal P1 |
| 7 | -80 V tolerance ±2 V (3.1) | **problem** | The 76 V ±2 % zener string drops out at -78 V when the string is on the high side (77.5 V: 0.13 mA left in it). Proposal P2 (±1 V, or a lower string with a re-run) |
| 8 | -80 V input protection "100 mA fuse or 100 Ω fusible resistor" (3.1) | **problem** | 100 Ω drops 1.9 V at 19 mA: no headroom left. Drawn: 10 Ω fusible (0.2 V). Proposal P3 |
| 9 | -80 V sequencing: up and BIAS_OK high before the HV (3.1, 3.4) | OK | sim: cold 170 ms, BIAS_OK 200 ms after the rail |
| 10 | W11-a OT_A / OT_B / OT_CT tabs (2.1, 4.3) | OK | OT_CT = V_ANODE through the board; UL taps unused (D7) |
| 11 | W24-b drive, Lock-3.96 1x5, PI plate DC on the line, coupling caps here (2.3, 10) | question | Drawn: 47n/630 V + 100k per tube (sim: bias node moves 0.26 V in a 150 V overdrive). The line carries 200-250 V DC + up to 70 V peak: confirm the 3.96 mm header family's voltage rating (KK-396 class parts are rated 250-600 V depending on the series) |
| 12 | W24 grounds solid at the power amp end (5) | OK | J105 pins 1 / 3 / 5 on GND |
| 13 | W14-b template ribbon 2x7, pinout (6.1) | OK | Same pinout; MUTE_ALL_N 100k pull-down, unused; RESET_N 10k pull-up |
| 14 | Expander "optional" (6.3, 7.3) | **problem** | It is the only source of OC_CLR and HV_PERMIT_REQ: without it the latch never clears and HV_PERMIT never comes on. Drawn as fitted. Proposal P4 |
| 15 | Expander map: GPA0 OC_CLR, GPA1 HV_PERMIT_REQ, GPA2-5 MODE_* reserved (7.3) | OK | 100k pull-downs: reset / unconfigured = no clear, no request |
| 16 | W15-b bias ribbon 2x5 pinout (6.3) | OK | |
| 17 | I2C 5 V, 100 kHz, 4.7k pull-ups on the power amp (6.3) | OK | DAC7578 and ADS7828 at VDD = 5 V; pull-ups on the DGND side, 100 Ω to the AGND devices (low level + 0.1 V) |
| 18 | I2C addresses (6.3, 14) | OK | Chosen: DAC 0x48, ADC 0x4B (README) |
| 19 | BIAS_EN 5 V, 10 kHz ±50 %, firmware-toggled (6.3, 8) | OK | sim with 5 V / 10 kHz: commanded bias 17 ms after BIAS_EN starts; stopped (high or low) = cold in about 130 ms; pump is AC-coupled, so a static level never releases |
| 20 | BIAS_OK meaning "VNC good and bias released" (6.3) | question | Implemented as "VNC good and +15 V present". It can't include "released": 3.4 step 2 has BIAS_OK high before BIAS_EN starts (step 4). Proposal P5 (wording) |
| 21 | OC_TRIP_N, latched, card-side pull-down (6.3, 8) | question | Works. New behaviour to state: **the latch starts tripped at power-on**, so the firmware must check the currents and pulse OC_CLR before asking for HV. Proposal P6 |
| 22 | HV_PERMIT_MON (6.3, 8) | OK | A second opto in the loop: high = loop current flowing (a W16 short to ground also reads high; the HV supplies' HV_PERMIT_STAT on the 40-pin tells them apart) |
| 23 | HV_PERMIT current loop 5-10 mA from +15 V into an opto on the HV supplies (8) | question | 9.4 mA with a 1.3k and two LEDs in series (monitor + HV side). The HV supplies must confirm their opto's LED (Vf ≤ 1.5 V) and CTR at 9 mA, and how fast their drivers stop |
| 24 | HV_PERMIT = BIAS_OK AND NOT OC_TRIP AND WARM_OK AND HV_PERMIT_REQ (8) | OK | Plus a second, independent switch: OC_OK alone on the low side (one shorted transistor can't permit) |
| 25 | Hardware warm-up timer about 30 s (8) | OK | Recommend keeping it (cheap, independent of the firmware): 31 s, opto-isolated heater sense, works for AC or DC heaters |
| 26 | Logic 5 V CMOS, no 3.3 V parts on the board (6.2) | OK | |
| 27 | Fail-safe: card absent / unconfigured / ribbon unplugged (6.2, 8) | OK | W15 out: BIAS_EN low → cold, DAC cleared, card reads BIAS_OK and OC_TRIP_N low. W14 out: no rails → op amps dead → cold, no +15 V → no loop current → HV off. Expander in reset: no request → HV off |
| 28 | Fail-safe: -15 V missing (6.2) | OK | Op amps run single supply, bias stays where it is (as [BIAS]); comparators and logic don't use -15 V |
| 29 | Fail-safe: -80 V lost while the HV is on (8) | question | VNC_FAULT clamps and BIAS_OK drops 185-250 ms later, but with no -80 V the follower's pull-down goes to 0 V and the bias goes **hot** while the HV decays. Needs the HV supplies' turn-off / discharge time. Missing simulation S6, requirement Q2 |
| 30 | Grounding: AGND star at GND_PWR, DGND island with ribbons / expander / BIAS_RTN, one soft tie, 100 Ω crossings (5, grounding.md 4) | OK | Drawn as GND / GNDD; the bias circuit, DAC, ADC, comparators and logic on GND; Kelvin net ties per shunt |
| 31 | No OT secondary COM on this board (5) | OK | |
| 32 | Over-current threshold 220 mA average, about 23 ms (8, SAFE-2) | question | Drawn at 2.20 V. At full sine overdrive the KT88 set draws 570 mA from V_ANODE (power_table.md), about 140 mA per tube plus the screen: 170-200 mA average per tube, so one tube 15 % above its partner nears the trip. Missing simulation S4 |
| 33 | Envelope: same outline 239 x 60 mm, sockets and holes as built (12.1, 12.3, chassis_fit.md) | question | No room to grow along x (PI + FX 1.6 mm to the left, control board 5 mm, HV supplies 11 mm); the octal sockets take the strip next to the front edge (centres 5.7 mm from it). The other ~35 mm x 239 mm holds the tabs, four 5 W screen resistors, shunts, coupling caps and about 250 SMD parts: looks feasible on one side, but a placement study is needed. Precision parts (reference, op amps, DAC) away from the tubes and screen resistors |
| 34 | Connector positions: tabs toward the HV supplies / OT, J105 toward the PI + FX, ribbons and W16 at the low-voltage end (12.3) | OK | Ribbons and W16 at the right end (toward the control board and HV supplies) |
| 35 | Rail budget row: +15 / -15 / +5 V (3.2) | OK | +15 V 37 / 45 mA (the row said about 40), -15 V 9 / 10 mA (said 25), +5 V 5 / 8 mA (said 15) |
| 36 | Relay family (3.1) | OK | No relay on this board |

**36 rows: 24 OK, 4 problems (6, 7, 8, 14), 8 questions (3, 11, 20, 21, 23, 29, 32, 33).**

## 2. What has been missed

Ranked by importance.

1. **-80 V current over the allocation**: 19.4 mA against 13.4 mA (row 6). The PSU 5.2 must
   give at least 22 mA (with margin), or the follower becomes push-pull (S3) so the 22k
   pull-downs can go.
2. **The documented sense filter was never simulated.** The master's netlist
   (`sim/bias_supply/run_bias_supply.py`, SHUNT) has `Cb1 a2 b1 330n` with node b1 connected to
   nothing: a floating capacitor. The "2nd-order 3.3 Hz Sallen-Key" of bias_supply.md, PA-4 and
   SAFE-2 was really two real poles (about 4.6 Hz) and a gain of 10. With the capacitor returned to
   the op amp's inverting input (the only place a gain-10 Sallen-Key can take it) the trip takes
   28 ms and the class-AB ripple is 3.4x larger (`rev_b/sim/checks_results.md`). Drawn as
   simulated (23 ms, 1.2 mA pp); the master documents should say so.
3. **VNC monitor threshold against the VNC spread.** VNC = string - |Vgs|: -70.8 V with a -2 %
   string and |Vgs(th)| 4 V, which is above the -71 V trip: such a board would never give BIAS_OK.
   Drawn: trip at -68.4 V and BSP92P followers (|Vgs(th)| 0.8-2 V, VNC -72.3 to -76.7 V). Cost:
   BIAS_OK drops 247 ms (not 185 ms) after the -80 V source goes and the bias drifts 5.1 V hot
   (not 2.5 V) before the clamp (checks_results.md). Choose by S2.
4. **-80 V headroom** (rows 7, 8): the ±2 V tolerance and a 100 Ω input resistor together leave the
   reference without regulation at the low end.
5. **Expander required, not optional** (row 14).
6. **-80 V lost with the HV on** (row 29): the bias goes hot until the HV is gone. Nothing in the
   documents limits how long the HV may stay after HV_PERMIT drops.
7. **Over-current nuisance trips** with KT88 at full overdrive (row 32).
8. **The over-current latch starts tripped**, and BIAS_OK can't mean "released" (rows 20, 21):
   behaviour the firmware and the documents must reflect.
9. **The warm-up timer's heater sense must be isolated** (heaters float, maybe at +90 V; AC or DC
   still open, PRE-4). Drawn with an opto and a bridge. The 74HC4060 also needs a power-on clear
   (a heater already present at power-up would otherwise leave the counter in a random state):
   drawn with a diode-OR pulse.
10. **Board area and heat** (row 33): no placement study yet; no operating temperature stated (Q6).
11. **The DAC's power-on state** is a requirement (PA-2) that many I2C DACs miss (MCP4728 loads
    EEPROM, AD5696R needs RSTSEL). DAC7578 chosen for its power-on reset to zero; confirm in the
    datasheet. Added layer: ~CLR held low while the watchdog clamps.
12. **W24 header voltage rating** (row 11) and **EL34 Vhk with the elevated heater** (row 4).
13. Small items: the latch's ~R comes from a slow RC into a non-Schmitt 74HC74 input (add a
    74LVC1G17 or use the comparator's own hysteresis); the ADC's REF is the external 2.5 V (firmware
    keeps the internal reference off); inrush into the 100 µF on -80 V at power-up; the 1650TA's
    403 mA DC rating against 450-570 mA at full overdrive (power_stage, still open with Hammond).

### 2a. Missing simulations

| # | Simulate | Question it answers | Needs |
|---|---|---|---|
| S1 | The drawn bias channel with vendor models (OPA4197, MMBT3904, MMBTA92 / A42, BSP92P, DAC7578 + ADR4525 noise) | Stability of the op amp + NPN + mirror loop (phase margin with the 1k base resistor and the mirror's capacitance), noise against 100 µVrms, the real -80 V / +15 V currents | Vendor SPICE models |
| S2 | VNC monitor Monte Carlo: zener ±2 %, Vgs(th) spread, 1 % resistors, LM4040 0.5 %, LM393 offset; with the -80 V hold-up | The trip threshold (-68 to -71 V) that never false-trips and still clamps early enough on a lost rail | Part tolerances; the PSU's -80 V output capacitance and the board's 100 µF |
| S3 | Push-pull (NPN + PNP) follower instead of the 22k pull-downs | Can the -80 V current drop to about 5-8 mA while still sinking about 1 mA of grid current in overdrive? Noise and ripple rejection | bias.py; only if the PSU can't give 22 mA |
| S4 | Per-tube average cathode current (plate + screen) at full overdrive for each type, with ±20 % tube imbalance and guitar-like signal | Is 220 mA a safe hardware threshold for KT88 / 6550 without nuisance trips, and still a useful fault trip for 6L6GC? | sim/power_stage models |
| S5 | Sense filter decision: two real poles (drawn) against a true 2nd-order filter | Trip time against tube-fault energy, ripple, ADC settling for the bias loop | checks.py |
| S6 | -80 V lost (or VNC follower failure) with the HV on: bias going hot while V_ANODE / V_SCREEN decay | Tube current and dissipation in the 185-250 ms before BIAS_OK drops plus the HV fall time; does the OC comparator trip first? | The HV supplies' output capacitance, their turn-off delay after HV_PERMIT drops, discharge path |
| S7 | Arc / flashover in a tube: the shunt diode, sense input and comparator under a 10-20 A pulse | Survival of the sense chain, false latch behaviour | V_ANODE output capacitance and its current limit |
| S8 | Thermal (not SPICE): board temperature near the sockets and screen resistors | Placement of the reference, op amps and 300 V transistors (leakage at temperature, [BIAS] open item 2) | Layout, ambient (Q6) |

### 2b. Missing requirements (SPECIFICATION.md), with proposed wording

| # | Topic | Today | Proposed wording |
|---|---|---|---|
| Q1 | -80 V rail | "-80 V ±2 V", 13.4 mA (interfaces.md only) | **PS-10 (new):** "The tube PSU's -80 V bias rail delivers -80 V ±1 V at 0-25 mA, ripple below 50 mVpp, and stays in tolerance for at least 300 ms after the mains is lost or the PSU shuts down, longer than the HV takes to fall below 50 V." |
| Q2 | HV removal time | none | **SAFE-7 (new):** "When HV_PERMIT drops, the HV supplies stop switching within 1 ms and V_ANODE and V_SCREEN fall below 50 V within 200 ms (value TBD by S6)." |
| Q3 | Over-current trip behaviour | SAFE-2: 220 mA, about 23 ms | add: "threshold 220 mA ±10 %; the trip latches; the latch powers up tripped and is cleared only by the control card (OC_CLR) when no tube is above the threshold; HV stays off until cleared. The firmware clears it only after reading the four currents and logs every trip." |
| Q4 | BIAS_OK and the power-up state | SAFE-3: BIAS_OK = VNC monitor | "BIAS_OK is high when the VNC reference is within its window and the board's +15 V is present; it does not depend on BIAS_EN. BIAS_OK, the over-current latch and WARM_OK are all low at power-up." |
| Q5 | Heaters | PS-7: 6.3 V; PRE-4: AC or DC TBD | "6.3 V ±5 % measured at the output-tube sockets at 3.6-6.4 A; DC (or AC: decide); warm-up interlock: WARM_OK 30 s ±20 % after the heater voltage exceeds 5 V, cleared within 1 s when it falls below 4.5 V." |
| Q6 | Operating environment | none | "Ambient 0-40 °C around the amplifier; the boards' parts are rated for 70 °C (85 °C next to the output tubes); bias set point drift under 2 mA per tube from 25 to 70 °C." |
| Q7 | Creepage / clearance (SAFE-4 "values TBD") | TBD | "On the PCBs: at least 3.0 mm creepage and 2.0 mm clearance between nets that differ by more than 300 V (up to 500 V peak); 1.5 mm between 50 and 300 V; HV tabs with insulated receptacles; slots where the spacing can't be met." |
| Q8 | Supported tube types (PA-3 "TBD") | TBD | "Supported: EL34, 6L6GC, 6550, KT88, mixed per side allowed (the lowest screen rating sets V_SCREEN). Pin 1 is tied to the cathode, pin 6 is unused. Heater feed sized for 4x 1.6 A." |
| Q9 | Bias accuracy and supervision | PA-2: range, resolution | "The idle current of each tube is held within ±2 mA of its set point by the firmware loop on the measured currents; the firmware reads back every DAC write and drops HV_PERMIT_REQ if a read-back or an ADC read fails." |
| Q10 | HV_PERMIT signal | interfaces.md 8 (PROPOSED) | "HV_PERMIT is a 5-10 mA current loop on a twisted pair; any open, short or loss of the power amp's +15 V inhibits the HV; the HV supplies report the loop state on the 40-pin (HV_PERMIT_STAT)." |
| Q11 | Missing speaker load (SAFE-5 "TBD") | TBD | "Tolerate: open load at full drive for 1 minute without damage (anode flyback clamps fitted if the simulation shows the primary voltage exceeding 2.5 x V_ANODE)." |
| Q12 | Ribbon / cable unplugged | rule in interfaces.md 6.2 | add to SAFE-1: "Any control or bias ribbon unplugged, or the -80 V lead off, gives cold bias and inhibits the HV within 300 ms." |

## 3. Interface changes proposed (to the coordinating session)

| # | What | Why | Boards | interfaces.md |
|---|---|---|---|---|
| P1 | -80 V allocation 13.4 mA → **≥ 22 mA** (the power amp row: 3 mA cold, 13 mA typical, 19.4 mA max) | Measured in sim with all four channels; hot end at low power settings | Tube PSU 5.2, power amp | 3.1, 3.2, 3.3, 14 |
| P2 | -80 V tolerance ±2 V → **±1 V** (or keep ±2 V and lower the zener string to 75 V after S2) | Zener string drop-out at -78 V | Tube PSU 5.2, power amp | 3.1 |
| P3 | -80 V input protection: **10 Ω fusible resistor** (not 100 Ω) or the 100 mA fuse | 100 Ω drops 1.9 V | Power amp | 3.1 |
| P4 | Power amp expander **required** (not optional) | Only source of OC_CLR and HV_PERMIT_REQ | Power amp, control board firmware | 6.3, 7.3 |
| P5 | BIAS_OK: "high = VNC reference good and +15 V present (independent of BIAS_EN)" | The sequence in 3.4 needs BIAS_OK before BIAS_EN starts | Power amp, control board | 6.3, 8 |
| P6 | State that the over-current latch **powers up tripped**; the firmware pulses OC_CLR after checking the currents, before HV_PERMIT_REQ | Defined, fail-safe power-up | Power amp, control board firmware | 6.3, 7.3, 8, 3.4 step 4 |
| P7 | HV_PERMIT_MON: "high = loop current flowing (sensed by an opto in the loop)" | Exact meaning of the drawn circuit | Power amp, control board | 6.3, 8 |
| P8 | Connector refs: J101 (W04-b), J102 (W05-b), J103 (W06-b), J104 (W11-a), J105 (W24-b), J201 (W09-b), J501 (W14-b), J502 (W15-b), J503 (W16-a); I2C DAC 0x48, ADC 0x4B; OC threshold 2.20 V = 220 mA | Replace the P- refs and close the address item | — | 2.1-2.3, 6.3, 14 |

## 4. Open questions (need a decision)

- **User / PSU session:** P1 and P2 (-80 V current and tolerance), or a push-pull follower (S3).
- **User:** keep the hardware warm-up timer (recommended: yes, drawn).
- **User:** fit the anode flyback clamps (SAFE-5)? Drawn as an option.
- **User / PI + FX session:** coupling caps stay here (drawn, as PROPOSED in 10).
- **HV supplies session:** opto LED / CTR at 9.4 mA, turn-off and discharge times (rows 23, 29).
- **Coordinating session:** correct the sense-filter description in bias_supply.md / PA-4 / SAFE-2
  (item 2), or decide to build a true 2nd-order filter (S5).

## 5. Next steps

1. S2 and S4 (threshold choices), then S1 with vendor models; S6 with the HV supplies' data.
2. Footprints (`lib/footprint_map.csv`): octal sockets as rev A (solder side), 4.8 / 6.3 mm tabs,
   5 W screen resistors as rev A, SMD for the bias / sense / logic.
3. Placement study inside the fixed 239 x 60 mm outline (row 33); then a tidy schematic pass.
4. Datasheet checks: DAC7578 power-on state and ~CLR behaviour, ADS7828 external-reference mode,
   BSP92P Vgs(th) and SOA, MMBTA92 / A42 leakage at temperature, LM393 input range at 5 V with
   a 15 V supply, PC817 CTR at 4 mA, 74HC4060 stop trick.
5. Silkscreen "IF-1" and the cable IDs next to each interface connector (interfaces.md 13).
