# Power amp rev C: plan

Rev B (`rev_b/`) grew to 336 parts on 4 layers, and its routing never closed: 228 unconnected and
62 clearance errors at the last run. Most of that came from the hardware safety chain packed into
rev A's outline. Rev C keeps rev B's mechanics and interface positions and replaces the bias,
measurement and safety circuits with a minimal set. The protections and their self-checks move
into the control board's FPGA logic. User decisions of 2026-11-25.

Rev A (repo root) and rev B (`rev_b/`) are frozen and not touched.

## Decisions (user, 2026-11-25)

| # | Decision |
|---|---|
| D1 | **Bias:** one high-voltage op amp per tube, driven by an I2C DAC. This replaces the current mirror, follower and VNC reference chain |
| D2 | **Cathode current:** I2C ADCs with a programmable-gain input read the 1 Ω shunts directly. No gain op amps |
| D3 | **No hardware protection logic:** no over-current comparators, latch, Schmitt gates, BIAS_OK monitors, warm-up timer, watchdog pump or expander. The FPGA logic does the protections, with self-checks |
| D4 | **No HV_PERMIT on this board:** no J503 / W16 current loop and no HV_PERMIT_DRV. The control board talks to the PSU, which cuts the main voltage if the control board is missing |
| D5 | **W15 pins 6-9 are spares.** Pin 6 was BIAS_EN; it goes with the watchdog |
| D6 | **No hardware guard for losing -80 V.** The bias then drifts toward 0 V, and the tubes withstand several seconds of 0 V bias. The FPGA sees it on the ADC and has the PSU cut the main voltage |
| D7 | **Use only necessary components** |

## Kept from rev B

- **Outline and mounting:** rev B's outline (x 280.33-519.09, y 127.05-187.38 in the chassis frame), H3 / H4 at the front, and the rear standoffs on the socket-flange holes.
- **Sockets:** the four octal sockets at rev A's centres, on the B side, turned 45 degrees so that pin 3 faces the front.
- **Output stage, unchanged:** 220 nF / 630 V coupling caps, 91k grid leaks, 5.6k stoppers, 1k 5 W flameproof screen resistors, 1 Ω shunts with an S3M across each and a Kelvin tap, four cathode test pads.
- **Open-load clamps:** RGP02-20E from GND to each plate, and 2x P6KE350CA from each plate to the centre tap. The 6.3 mm rule on OT_A / OT_B / CL_x stays.
- **Connectors, at their positions in interfaces.md 12.6:**

  | Ref | Cable | What it carries |
  |---|---|---|
  | J101 | W04 | V_ANODE, GND_PWR |
  | J102 | W05 | V_SCREEN |
  | J103 | W06 | heaters, floating |
  | J104 | W11 | OT_A, OT_CT, OT_B |
  | J105 | W24 | drive, Mini-Fit Jr 2x3 |
  | J201 | W09 | -80 V, BIAS_RTN |
  | J501 | W14 | template ribbon; supplies only now |
  | J502 | W15 | I2C |

- **Grounding (grounding.md):** GND = AGND star at J101-2. The GNDD island holds J501, J502 and J201-2, joined to GND by one soft tie (10 Ω ‖ 100 nF).

## The new circuit

### Sheet 01: output stage

As rev B sheet 01: tubes, grid parts, shunts, clamps, tabs, J105.

### Sheet 02: -80 V input, reference, DAC, four bias channels

- **-80 V input:** 10 Ω fusible resistor (interface requirement), S1G reverse clamp, 100 µF / 100 V hold-up, 100 nF.
- **Reference and DAC:**
  - ADR4525 2.5 V reference (VREF2V5), used by the DAC and by the bias offset.
  - DAC7578 in TSSOP-16, which resets to zero scale at power-on (TI product page). ADDR0 = VDD gives **0x4A** (datasheet table for the single-ADDR0 package: GND 0x48, VDD 0x4A, float 0x4C). Four of its eight channels are used.
- **Per tube, OPA462 (TI, 180 V, SO-8 PowerPAD):**
  - Supplies: V+ = +15 V and V- = -80 V, 95-97 V in all against the 12-180 V range.
  - Non-inverting stage: Rf / Rg = 280k / 10k (0.1 %), with Rg to VREF2V5. Input divider 10k / 115k from the DAC, so k = 0.920, with 330 nF across the 115k (about 50 Hz).
  - Output: **Vout = 29 · 0.920 · Vdac − 70 V**. DAC zero (power-on) gives **−70 V (cold)**, full scale gives −3.3 V. The 115k pull-down also gives cold when the DAC output is high-Z.
  - Input common mode 0-2.3 V, inside (V-)+1 to (V+)-3 V. Iq is 3.2 mA typical, 3.7 mA max (datasheet 6.5), so 4 op amps take at most 14.8 mA from -80 V, inside the 25 mA request.
  - E/D Com to GND and E/D to +5 V: enabled. E/D low would leave the output high-Z, so it is never driven low. Status flag not used.
  - Output 1k / 1 µF to BIASn, as rev B. Rf ‖ 1 nF.
  - Decoupling 100 nF on each supply. The PowerPAD is on V- (-80 V copper).
  - Dissipation about 0.35 W per op amp (RθJA about 40 K/W).

### Sheet 03: cathode-current ADCs, rail readback, ribbons

- **Cathode currents:**
  - Three ADS1115 (16-bit, PGA, I2C). ADDR = GND **0x48**, VDD **0x49**, SCL **0x4B** (datasheet Table 7-2). SDA (0x4A) is not used, so there is no clash with the DAC.
  - ADC1 measures V1 and V2, ADC2 measures V3 and V4, each **differential across the shunt** (K-n to KELV-n). Range ±0.256 V gives 0-256 mA, about 7.8 µA per count.
  - Per channel: 1k in each leg and 1 µF across the pair (80 Hz), for fault current limiting and anti-aliasing. Not 10k: the ADS1115 differential input impedance at ±0.256 V is 710 kΩ, and 2x 10k would read 2.8 % low.
- **ADC3, rail and self-check channels:**

  | Input | Measures | How |
  |---|---|---|
  | AIN0 | -80 V | offset divider 536k to the rail / 10k to VREF2V5: 0.99 V at -80 V, 2.45 V at 0 V |
  | AIN1 | +15 V | 100k / 20k |
  | AIN2 | VREF2V5 | direct; cross-checks the ADC's internal reference against the DAC's |
  | AIN3 | +5 V | 10k / 10k |

- **Ribbons:**
  - J501 (W14): only +5 V, +15 V and GNDD are used. -15 V, SPI, MUTE_ALL_N and RESET_N are not connected; nothing on rev C uses them.
  - J502 (W15): GNDD, SCL, SDA, spares on pins 6-9. 4.7k I2C pull-ups to +5 V; 100 Ω in series on SDA / SCL where they leave the GNDD island.
- **Other parts:** soft tie 10 Ω ‖ 100 nF, bulk 10 µF on +15 V and +5 V, and power flags.

**Estimate: about 125 parts** (rev B 336, rev A 72).

## What the FPGA logic must do (requirements for the control board)

These used to be hardware on rev B:

| # | Requirement |
|---|---|
| F1 | **Over-current** per tube from ADC1 / ADC2. At 860 SPS the four channels are read at least every 10 ms. Trip by having the PSU cut the main voltage |
| F2 | **Rail monitoring** from ADC3: -80 V (D6), +15 V, +5 V, and VREF2V5 against the ADC's internal reference |
| F3 | **Stale-data rule:** an I2C error, an ADC that doesn't respond, or a reading that doesn't update counts as a fault |
| F4 | **Bias sequence:** DAC at zero (cold) until -80 V and +15 V are good. HV only after warm-up. The firmware clamps the DAC codes for each tube type. **Preferred, not required:** -80 V up no later than +15 V. Otherwise BIASn goes up to +14 V for a few ms at power-up (rev_c/sim/opamp/results.md item 4). That is harmless with no HV, and the board has no parts for it (sim P2 not fitted) |
| F5 | **Readback:** a DAC write must show up in the cathode current within the expected time once the HV is on. If it doesn't, that's a fault |

## Interface changes (for the coordinating session, tube_amplifier_kicad docs/interfaces.md)

| Item | Now | Rev C |
|---|---|---|
| SAFE-2 over-current | hardware comparator 220 mA, latch, OC_TRIP_N (DEFINED 2026-11-22) | FPGA from the ADC readings (F1) |
| SAFE-3 BIAS_OK | hardware monitors, W15-7 (DEFINED 2026-11-22) | FPGA from ADC3 (F2) |
| SAFE-1 BIAS_EN | watchdog pump, W15-6 | removed; the DAC resets to zero, and the FPGA logic owns the bias |
| SAFE-6 / W16 | HV_PERMIT loop power amp → HV supplies | removed (D4); the HV supplies' J501 goes too |
| 6.3 W15 | 6 BIAS_EN, 7 BIAS_OK, 8 OC_TRIP_N, 9 HV_PERMIT_MON | 6-9 spare |
| 6.3 I2C addresses | DAC 0x48, ADC 0x4B | ADC 0x48 / 0x49 / 0x4B, DAC 0x4A |
| 6.1 / 7.3 template on the power amp | expander, OC_CLR, HV_PERMIT_REQ | supplies only; no expander, SPI not connected |
| 8 WARM_OK | hardware timer (proposed) | firmware only |
| 3.2 rail currents | -80 V 5.4-22.7 mA; +15 V 41/50 mA; -15 V 9/10 mA; +5 V 6/9 mA | -80 V ≤ 14.8 mA (op amps) + about 1 mA (dividers, grid leaks); +15 V ≤ 15 mA; -15 V 0; +5 V about 5 mA |

## Steps

1. **Schematic** (`rev_c/tools/sheets/draw_all.py`, generated like rev B): three sheets, ERC clean, footprints, BOM. **Done 2026-11-25** (README.md): 128 parts, 124 after sim P1 (the 1 nF caps across Rf removed). Op amp simulation: rev_c/sim/opamp/results.md (TI's OPA462 model, all items pass). The shunt inputs are 1k + 1k with 1 µF, not 10k with 100 nF (the ADS1115 differential input impedance is 710 kΩ).
2. **Review against interfaces.md** and send the change list above to the coordinating session.
3. **Layout:** reuse rev B's frame and connector positions. Put the op amps 30 mm or more from the socket centres, and the DAC / ADC / reference near the ribbons. **Layout decisions (user, 2026-11-25):**
   - **4 layers,** standard 1.6 mm build. **Plate lanes OT_A / OT_B on B** (changed at placement, 2026-11-25: the decision said "F only, short", but OT_B has to run about 135 mm from J104 to V3 / V4). B carries no SMD parts in rev C, so a lane there blocks no part, and F tracks cross over it. In1 and In2 are voided under the lanes, with no vias near them. The clamps and tabs stay on F (THT). In1 is the GND plane. In2 has a -80 V area under the op amps (their PowerPADs are on V-) and GND elsewhere. Rev B's design rules otherwise.
   - **Single-sided SMD assembly:** every SMD part on F (facing down). Only the sockets and the lying 5 W screen resistors are on B. The 91k grid leaks move to F.
   - **East rear standoff:** interfaces.md 12.5's (513.5, 179.0) was tried and lands 1.0 mm from a leg of J101's GND_PWR tab. So H1 stays at rev B's (475.9, 165.3), also an existing plate hole.
   - **Connectors** at rev B's laid-out positions (interfaces.md 12.6). J503 removed.

   **Setup done 2026-11-25:** `rev_c/kicad/tube_power_amp_revc.kicad_pcb`, generated by `rev_c/tools/layout/make_pcb.py` (positions and rules in `placement.py`).
   - 49 parts at rev B's positions: sockets, grid stoppers, tabs and headers, clamps, coupling caps, screen resistors, cathode sets.
   - The other 91 parts (bias, DAC, ADCs, grid leaks, D108) are parked below the board for placement.
   - DRC: 0 clearance, 0 parity, silk warnings only; 298 unconnected (not routed).

   **Placement, first pass, done 2026-11-25** (`placement.py`, picture `rev_c/docs/placement.png`):
   - Grid leaks on F next to their coupling caps (R101 under C101; R105 / R109 / R113 on the rear edge strip). D108 on F next to R108.
   - Everything else is packed into the **front band** (y 127.6-142.3, in front of the OT_B lane's via-free band, at least 30 mm from every socket centre), west to east:
     - -80 V bulk (C201, D201, C202);
     - four op amp channels, 12.4 mm each;
     - the precision / ADC / ribbon cluster beside J501;
     - the fusible R201 next to J201.
   - DRC: 0 clearance, 0 parity, silk only; 290 unconnected.
   - The packer places by size, not by net.

   **Heater copper done 2026-11-25** (`heater_copper.py`, run by `rev_c/tools/layout/build.sh`; pictures `rev_c/docs/heater_B.png`, `heater_In1.png`):
   - Current: up to 1.6 A per tube. J103 sits between V2 and V3, so each side carries 3.2 A as far as its first socket.
   - **HTR2:** a pour on B along the rear band behind the sockets (pins 7), with a finger to both legs of J103's HTR2 tab.
   - **HTR1:** the same pour on In1 and In2 in parallel, stacked under HTR2, with a finger to J103's HTR1 tab. Each pin 2 (front) has a 1.8 mm spur on both inner layers, through the middle of its pin circle and out between pins 5 and 6.
   - Narrowest section: about 4 mm behind pin 6. On B that is 1 oz outer, and 3.2 A needs about 1.5 mm for 10 K. On In1 + In2 it is 2 x 0.5 oz, about 10 K at 3.2 A. **Order 1 oz inner copper** for margin.
   - Pads connect solid; the heater pours have priority 10, above the GND pours.
   - DRC: 0 clearance, 0 parity; all heater items connected. The order inside each channel and in the precision cluster gets tidied with the routing.
4. **DRC, renders, STATUS.**
