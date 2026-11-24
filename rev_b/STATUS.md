# Power amp rev B: status

## Where we left off (2026-11-24)

Second layout pass is in progress. The committed board is the last complete chain run.

**What changed in the second pass**
- **Plate lanes.** OT_A / OT_B and CL_A / CL_B now run on **In2** at the B1 inner spacing of 3.2 mm. They surface only at the socket plate pins, the J104 tabs and the clamp pads, which keep 6.3 mm.
  - B is voided within 4.2 mm of the lane copper. Vias stay 4.6 mm from it.
  - Dielectric relied on: In2 to In1 is the 1.065 mm core. In2 to B is only the 0.21 mm 7628 prepreg, which is why B is voided rather than relied on.
  - **Stack-up to order.** A 4-layer build with **at least 0.4 mm prepreg between In2 and B** (or the lanes moved to In1 with at least 0.4 mm on both sides). Until then the B void stays.
- **V_ANODE** lane moved to In1.
- **Router fences round the 1.25 kV pads.** 6.3 mm + 0.3 mm 32-gon rule areas plus a User.2 copy for KRT `--keepout`. `pours.py` removes them before the fill.
- **Clearances.** BIAS80 (−80 V rail, 72 V reference, bias nets) is 0.6 mm outer and 0.2 mm inner/pad-to-pad at the parts' own pitch. Nets at 30 V or less use 0.2 mm.
- **Stitching vias before routing.** `ground_vias.py` places one stitching via (with stub) per SMD GND / GNDD pad: 37 of 141 placed.
- **Thermals.** Zones use THT-only thermals with 0.5 mm spokes, and SMD pads connect solid. Starved thermals went from 41 to 5.
- **Thermal distances.** U302 is now 41.9 mm from the nearest socket centre and D203 43.9 mm (the D202 / D203 / R20x / C20x / U302 cluster moved).
- **H1** stays at (475.9, 165.3).
- **Connectors.** No connector positions changed.

**DRC on the committed file** (`kicad-cli pcb drc --severity-all --schematic-parity`, no refill)

| Check | Result |
|---|---|
| Unconnected | 228 (eab84c8: 239) |
| Clearance errors | 62 (eab84c8: 8) |
| Shorts | 0 (eab84c8: 1) |
| Starved thermals | 5 (eab84c8: 41) |
| Parity | 0 |
| Warnings | 41 (silk) and 1 dangling track |

- **Clearance errors.** 60 are near misses at 6.21–6.29 mm against the 6.3 mm rule round the D103 / D104 / D105 / D106 clamp pads. Two are real: M80_IN at 5.44 mm from V3 pin 3, and WARM_OK at 5.59 mm from V1 pin 3.
  - The User.2 `--keepout` fences, added after this run, are meant to fix these. That chain run was stopped at wrap-up before it finished.
- **Caveat.** The committed run used the old 3-layer route args (F/In2/B, no `--net-clearances`) because `routing.json` was reset during the run. `routing.json` now carries the 4-layer args, `net_clearances.json` and the keepout.

**Still open and why**
- **228 unconnected:** 34 of them are GND / GNDD, the rest are spread over about 100 nets, mostly in the dense front band (precision / bias / logic cluster) and the corridor.
  - The router has not yet had In1 as a signal layer, or the inner 3.2 mm value for the plate nets.
- **5 starved thermals** on J105 pin 3 and on J201 / J501 GNDD pins. These need solid connections on those tab/header pins.

**Resume** (from `~/dev/tube_power_amp_kicad`; runs about 1.5 h, kill only its own PID):

    rev_b/tools/layout/route_chain.sh > build/layout/chain.out 2>&1
    rev_b/tools/layout/check.sh rev_b/kicad/tube_power_amp_revb.kicad_pcb build/check_final

Do not `git checkout rev_b/routing.json` afterwards: the chain adds a "rest" group, so drop just that key.

**Next three steps**
1. Run the chain with the 4-layer args and fences. Then check that the 6.3 mm near misses and the two real errors are gone.
2. Raise the stitching-via hit rate (104 SMD ground pads have no via yet). Make the 5 starved tab pins solid.
3. If the front band still leaves nets open, decide on the board-level change: spread the precision / bias cluster west into the space the B-side lanes freed, or extend the outline at the front where the chassis allows. Then do renders, the docs/drc_layout.rpt refresh and the second-pass STATUS write-up.

## Layout, first pass (2026-11-24)

**State: placed, the HV / power copper drawn and clean, the low-voltage routing NOT closed.** This first
pass is a reviewable layout, but it is not DRC-clean yet. The board is `kicad/tube_power_amp_revb.kicad_pcb`,
4 layers, 238.76 x 60.33 mm (rev A outline). It is built entirely by scripts (`tools/layout/route_chain.sh`).
Nothing is ordered.

| Check (KiCad 10.0.7, `--severity-all --schematic-parity`, `docs/drc_layout.rpt`) | Result |
|---|---|
| Schematic parity | **0** |
| Unconnected items | **238**: 71 GND pads the pours and the ground step did not reach, the rest about 100 low-voltage nets (bias, reference, monitors, logic, sense) the router left open |
| Clearance errors | **8**: router tracks (HS_AC1, POR_W, FLT1, KELV1) 5.0-6.0 mm from clamp / J104 pads, where 6.3 mm is required |
| Short | **1**: a ground-stub via on the drawn GRID4 track (B) |
| Starved thermals | 40 (ground pads with fewer than 2 spokes) |
| Warnings | silkscreen only, plus 1 dangling stub |
| HV / heater / grid copper drawn by `hv_copper.py` (before the router) | **0 violations** on its own (DRC of `build/layout/01_hv.kicad_pcb`) |
| ERC | 0 errors, 1 warning (the ADS7828 REF one, unchanged) |

Renders: [placement](docs/layout_placement.png), [F](docs/layout_top.png), [B](docs/layout_bottom.png),
[In1](docs/layout_in1.png), [In2](docs/layout_in2.png), 3D [bottom (component side)](docs/layout_3d_bottom.png),
[perspective](docs/layout_3d_iso.png). These are KiCad F views, which show the chassis plan mirrored: the east
end (HV supplies) is on the left. The interface sketch is `docs/layout_sketch*.png`.

### A. Frame, mechanics, socket arrangement

- **Coordinates.** Every position is written in chassis coordinates (D748, mm, y measured from the front
  panel) in `tools/layout_frame.py` and `tools/layout/placement.py`. They map to KiCad as
  x_k = 620 - X, y_k = 250 - Y, which is rev A's frame shifted by (205.05, 97.55). The board hangs 15 mm
  below the plate with KiCad F facing down (components down); the socket footprints sit on B.
- **Socket mechanics, kept from rev A.** The sockets are screwed to the plate through the 3.5 mm flange
  holes at r 20 mm (D748). Their 20 mm legs reach down to the board, which is why the board can sit 15 mm
  below the plate (2 mm plate + 15 mm gap + 1.6 mm board; about 1.4 mm of leg passes through to the
  solder side).
  - The board courtyard of each socket is therefore only the pin circle (r 11 mm). Parts on B within
    r 15 mm of a socket centre must stay below the socket body under the plate (13 mm; the B-side screen
    resistors are 8.4 mm).
  - The flange holes also fix the socket rotation. Rev B keeps rev A's orientation (pin 3, the plate, at
    the front-east). The sketch's 45-degree turn is withdrawn: it would need new flange holes.
- **Mounting holes.** All four are 3.2 mm unplated, with a copper keep-out of r 3.5 mm on F / B and
  r 2.2 mm inside.
  - H3 (514.95, 131.45) and H4 (284.95, 131.45): as rev A.
  - H2 (315.4, 178.9): flange hole, per C3.
  - **H1 (475.9, 165.3)**: this is V4's other flange hole, as fallback C1b stated, **not (513.5, 179.0)**.
    With J502 turned 90 degrees, the east strip holds J502 plus three tabs and has no room left for a
    standoff at (513.5, 179.0).
- **Stack-up.** JLC04161H-7628, 1.6 mm, 4 layers, 2 oz outer, 1 oz inner (JLCPCB capabilities page read
  2026-11-24: 4-layer up to 663 x 593 mm; 2 oz multilayer 0.15 / 0.15 mm; PTH ring 0.254 mm at 2 oz;
  non-plated slot 1.0 mm; copper to edge 0.2 mm). Used here: 0.25 / 0.2 mm, vias 0.6 / 0.3 mm, 0.5 mm to
  the edge (2.0 mm for HV).
- **Why 4 layers, not 2.** The HV clearances leave no room on 2 layers:
  - The plate lanes (OT_A / OT_B) with their 6.3 mm moats take a 14.6 mm band right across the board in
    front of the sockets.
  - Every crossing of that band has to be on F. Under the lanes the inner copper is cut back 3.2 mm, and
    on B nothing comes within 6.3 mm.
  - The drive lines, V_SCREEN, V_ANODE and the long G2 / GRID4 leads therefore run on the inner layers
    (internal spacing B1: 0.25 mm at 301-500 V), some of them through the sockets' pin circles.

### B. Design rules (in the board: net classes and `kicad/tube_power_amp_revb.kicad_dru`)

- **Standards.** IPC-2221B table 6-1: B2 (external, uncoated) on F / B for the HV classes, B1 inside. This
  was cross-checked against IEC 60664-1 functional insulation, pollution degree 2, material group IIIb.
- **HV1250** (OT_A, OT_B, CL_A, CL_B): 6.3 mm outer, 3.2 mm inner.
- **HV450** (V_ANODE, V_SCREEN, DRV_A / DRV_B, G2_n): 2.5 mm outer, 0.5 mm inner, 1.25 mm between two HV450
  nets.
- **Chassis standoffs**: hole clearance 8.0 / 4.2 mm outer (the 6.4 mm standoff), 3.2 / 0.5 mm inner.
- **HV to the board edge**: 2.0 mm.
- **BIAS80 / HTR** (up to 100 V): 0.2 / 0.25 mm under solder mask (IPC B4, coated: 0.13 mm). **This
  changes the STATUS assumption** (B2 0.6 mm) for these low-voltage nets only; their pads are exposed only
  at the parts' own pitch.
- **Exceptions:**
  - between the octal socket's own pins: 2.0 mm (2.77 mm between pads; the tube base sets it);
  - HV copper that reaches into a socket area (SKT1-4, r 13.5 mm) keeps 2.0 mm from what lies wholly
    inside that area;
  - J105's own pads: 1.4 mm (Mini-Fit Jr is rated 600 V).
- **Keep-outs drawn with the OT copper**: In1 / In2 have no copper within 4.2 mm of it; no vias within
  7.7 mm on any layer.

### C. Placement (`tools/layout/placement.py`: one table plus HV-aware packed groups)

- **Rear band, the gaps between the sockets.**
  - F: the coupling caps (220n / 630 V, 26.5 x 8.5 mm). V1 / V2 / V3 have theirs in the rear row of
    their east gap; V4's (C106) is in the front row of the V3-V4 gap.
  - B: the screen resistors, lying (5 W, P27.94), with V4's in the V3-V4 gap. V3's (R111) stands on F in
    the V2-V3 gap (`..._Vertical_Tight` footprint).
  - B: the 91k grid leaks (2512 HV).
  - The cathode sets (1R 2512 shunt, S3M, Kelvin net tie, test pads TP101-TP108 on F, probed from below).
  - The heater tabs J103, at (383.0 / 394.5, 166.5) in the front row of the V2-V3 gap.
- **Grid stoppers.** The 5.6k stoppers are 1206 parts inside each pin circle, at pin 5.
- **Front band, x 296-380: the HV cluster.**
  - J104: OT_A (311.7, 139.0), OT_CT (338.1, 132.5), OT_B (364.5, 139.0).
  - Clamp row at y 145.5: RGP02 + 2x P6KE350CA per side on 10.16 mm.
  - RGP02 D104 at (370.5, 137.5).
  - C101 at the centre tap.
  - The output transformer primary comes down the west lead hole (331.4, 90.1), 25-50 mm from the tabs.
    The OT bolt at (331.4, 128.1) is cleared: CT legs 4.2 mm horizontally, 6.5 mm in 3D.
- **Front band, x 384-470: low-voltage analog.**
  - -80 V input (R201, C201).
  - The four bias channels in 8.2 mm columns, with U303 in the middle.
  - Precision strip (U405, U301, U302, U201, the zener string; the dividers under them on B), measured
    from the nearest socket centre:

| Parts | Requirement | Measured |
|---|---|---|
| U405 at (452.9, 131.0) | ≥ 40 mm | 47.8 mm |
| U301 at (460.9, 131.0) | ≥ 40 mm | 52.3 mm |
| U201 | ≥ 40 mm | 49.7 mm |
| D202 | ≥ 40 mm | 41.0 mm |
| **U302 (ADR4525)** | ≥ 40 mm | **39.4 mm: short** |
| **D203** | ≥ 40 mm | **37.2 mm: short** |
| U401 / U402 (op amps / comparators) | ≥ 30 mm | 42.9 / 34.6 mm |
| U303 | ≥ 30 mm | 36.4 mm |
| U202 (on B under C201) | ≥ 30 mm | 48.0 mm |
| 300 V transistors (bias columns) | ≥ 25 mm | ≥ 32 mm |

U302 and D203 must move about 3 mm toward the front edge in the second pass.

- **Digital island, x 469-519.** J501 / J502 / J201 / J503, with U501 in the corridor over OT_B.
- **Corridor, y 147-162, over the OT lanes.** Non-sensitive SMD only: logic, watchdog, followers,
  heater sense.

### D. How it is routed (`tools/layout/route_chain.sh`, about 90 minutes)

1. `make_pcb.py` places the board.
2. `hv_copper.py` draws the HV copper and locks it:
   - OT lanes (B, 2.0 mm, y 154.3);
   - V_ANODE (F at the CT, then In2 along y 130.3 and up the east strip);
   - V_SCREEN as an In2 "chord" at y 175.2 through all four pin circles (between pins 4/5 and 7/8),
     with spurs;
   - DRV_A / DRV_B on In2 from J105 through V1's pin circle, DRV_A on through V2's, DRV_B along the rear
     edge;
   - G2 leads and grid leads;
   - the heater pair: HTR1 F over HTR2 B, 2.4 mm, at y 185, with pin-7 stubs and HTR1 to pin 2 inside each
     circle.
3. KiCadRoutingTools in locked group steps: supply, kelvin, sense, bias, ref, digital, rest.
4. Pours (`pours.py`: GND on 4 layers, GNDD island) and a ground step.
5. Fab fixes (the chain stopped after the ground step; refill, unlock and fab fixes were run by hand from
   the same scripts).

### E. Mechanical checks against the neighbours

| Neighbour | Check | Number |
|---|---|---|
| Rear I/O (8.3 mm) and W19 | nothing past the rear edge | ✓ (outline unchanged, receptacles inboard) |
| HV arm (5.9 mm) | east tab envelopes end at x 517.75; jumpers cross below the boards | ✓ |
| Control board | headers W14 / W15 at the front edge (J4 / J5 unchanged) | ✓ |
| Control board, W14 | J501 pin 1 (499.40, 132.80), a translation | flat, 0 folds |
| Control board, W15 | J502 pin 1 (511.30, 141.10), long axis +y, odd row at x 511.30 | one 45° fold under J502 |
| PI + FX | J105 pin 1 (286.50, 141.00), pins 1 / 4 west, as agreed (12.5) | ✓ |

### F. Interface positions that differ from interfaces.md 12.5 (for the coordinator)

- **Tabs.** J101: V_ANODE (514.50, 171.50) and GND_PWR (514.50, 181.70). J102: V_SCREEN (514.50, 161.30).
  Blades along y, legs at ±2.5 mm in y. The tabs moved about 10 mm north because J502 now takes the strip
  in front of them (the C1b cost).
- **J201** (-80 V / BIAS_RTN) at (482.5 / 492.0, 143.2), blades along y.
- **J503** pin 1 at (499.00, 145.50), pin 2 at (501.54, 145.50).
- **J103** (heaters) at (383.0 / 394.5, 166.5), moved from (390 / 401.5, 181); the harness runs along the
  floor.
- **J104** OT tabs as in C. above.
- **H1** at (475.9, 165.3), as in A. above.

### G. Not closed: what the second pass has to do

1. **The corridor is the blocker.** No via may sit within 6.3 mm of the B-side OT copper, so the parts
   placed over the lanes (about 70: logic, watchdog, heater sense, followers) can only route on F. The
   digital step left 33 of 41 nets open.
   - (a) Move them out of the corridor. That needs room the front band does not have; the front band
     would have to drop parts.
   - (b) **User decision:** treat solder-masked traces and tented vias as coated (IPC B4: 1.25 kV ->
     3.8 mm). The via-free band would shrink to ±5.2 mm round the lanes.
   - (c) Put the OT lanes inside (In2) with voids above and below.
2. Use In1 as a routing layer as well, and move V_ANODE to In1 (prepared, not run).
3. The 8 router clearance errors near the clamp pads: add keep-out areas round the HV1250 pads (KRT applies
   the net-class clearance, not the pad's).
4. Ground: fix the 71 open GND pads with stitching vias placed before the router; fix the starved thermals.

### H. Part checks before ordering

- The 4.8 / 6.3 mm PCB tab order codes (2 legs on 5.00 mm).
- Mini-Fit Jr 5566-06A order code.
- 220n / 630 V box width ≤ 8.5 mm.
- 91k 2512 at ≥ 500 V working.
- 5.6k 1206 at the grid pin.
- SMD PC817 (SMDIP-4).
- The 5 W screen resistor's real body: 25 x 6.4 mm at P27.94 on B, raised 2 mm.
- Socket leg length with the 15 mm standoffs (20 mm legs: about 1.4 mm through the board).

---

## Layout sketch: interfaces (2026-11-24)

The step before the layout, at the coordinator's request: **only the interfaces to the other boards**, so they
can be agreed before any detailed placement or routing. Drawing (script-generated, chassis frame, plan from
above): [docs/layout_sketch.png](docs/layout_sketch.png), east end zoomed:
[docs/layout_sketch_east.png](docs/layout_sketch_east.png). Positions live in one file,
`tools/layout_frame.py` (the layout will read them from there); `python3 rev_b/tools/layout_sketch.py` redraws.

### Frame and fixed features

- **Chassis frame** (D748 top plate, mm, y from the front panel's inner face). The board keeps rev A's outline,
  **x 280.33-519.09, y 127.05-187.38** (238.76 x 60.33 mm), 15 mm below the plate, **components down**
  (KiCad F faces down), the four octal sockets on the B side (toward the plate) at rev A's centres
  **(296.55 / 362.59 / 428.63 / 494.67, 172.13)** on the 30 mm plate holes. Rev A to chassis:
  X = 414.95 - x, Y = 152.45 - y (mechanical/README.md). Planned KiCad frame for rev B: x_k = 620 - X,
  y_k = 250 - Y (= rev A + (205.05, 97.55)); the KiCad F view is the plan mirrored left-right.
- **Socket pins:** the sockets sit 15.3 mm from the **rear** edge and 45 mm from the front edge. (The second
  and third passes wrote "sockets in the front strip" and "reference strip on the rear edge": in the chassis
  frame it is the other way round, so the cool strip is the **front** edge. On the rear edge no point is
  even 37 mm from a socket centre.) Rev B turns each socket 45 deg from rev A so that **pin 3 (plate) faces
  the front**: 4 G2 front-east, 5 G1 east, 6 rear-east, 7 heater rear, 8 cathode rear-west, 1 cathode west,
  2 heater front-west. The plate hole is round, so the rotation is free; pads and drills stay rev A's
  (1.6 mm drill / 3.81 mm pad, checked against the rev A board: identical; the 5 W resistor 1.2 / 2.4 mm also).
- **Side A = V1, V2 (west), side B = V3, V4 (east)**: DRV_A is short from J105, OT_A and OT_B split at J104
  without crossing.
- **Mounting holes**, board holes 3.2 mm **unplated**, 4 mm copper keep-out: H3 (514.95, 131.45) and H4
  (284.95, 131.45) as rev A, on D748 holes. Rev A's H1 / H2 (514.95 / 284.95, 182.45) have **no plate hole**.
  Rear support: see open choice C3.
- **Old bias pot / test point holes** (D748, y 198.1, 5-6 mm, x 279-510): **10.7 mm behind the board's rear
  edge, off the board**. Rev B sets the bias from the DAC and reads the cathode currents with the ADC, so
  it has no pots and no test point jacks (the schematic has none): the holes stay unused (plug them).
- **Output transformer bolts** (1650TA pattern) at (331.4, 128.1) and (415.5, 128.1) are 1 mm inside this
  board's front edge: their screw tips stop at least 10 mm below the plate (5 mm above the board's B side);
  no HV copper on B within 6.3 mm of either axis.
- The seven unused 3.5 mm plate holes at r 20 mm round the sockets (old chassis-socket flange screws) lie
  over the board's rear band; nothing passes through them unless C3 uses two of them.

### Connectors and tabs that leave the board

All on the F side (facing down, away from the plate); mates plug in from below. "Pin 1" = chassis
coordinates of pad 1. Receptacle envelopes: 4.8 mm tab 8.0 x 6.5 mm, 6.3 mm tab 9.5 x 7.5 mm (fully
insulated on every HV rail). Tab footprint (interfaces.md 4.1, DEFINED): 2 legs on 5.00 mm, 1.4 mm drill.

| Ref | Cable | Mating end | Part / footprint | Pin 1 (chassis) | Long axis, rows, key | Cable leaves | Path, length, gauge |
|---|---|---|---|---|---|---|---|
| J105 | W24-b drive | PI + FX J201 | Molex Mini-Fit Jr 5566-06A 2x3 vertical (39-28-1063 class), 600 V; body 14.8 x 12.0 mm at x 283.3-298.1, y 138.3-150.3 | **(286.50, 141.00)** | rows along +x: pins 1 / 2 / 3 at x 286.50 / 290.70 / 294.90, y 141.00; pins 4 / 5 / 6 at y 146.50 (4 under 1). Latch on the 4-6 (rear) side by KiCad's outline: confirm with the Molex drawing | down, then west | discrete two twisted pairs (DRV_A + GND, DRV_B + GND) in a 39-01-2060 housing, wire ≥ 600 V insulation (silicone / PTFE), AWG 20-22; 0.10-0.15 m depending on the PI + FX header; this header is the reference for W24 |
| J501 | W14-b template ribbon | control board J4 | 2x7 shrouded IDC, 2.54 mm; body x 469.7-496.1, y 128.1-139.0 | **(490.50, 132.80)** (needs J4 at (490.50, 115.73), choice C1) | long axis along x, pin 14 at (475.26, 135.34); odd row at the front (y 132.80), even row y 135.34; key as J4 (a pure translation of J4 in y) | flat ribbon toward the front | straight 1:1, **0 folds**, conductor 1 on pin 1 at both ends; pin rows 17.07 mm apart, cable 25-30 mm between socket centres (a small down-loop); lies about 18 mm below both boards across the 5 mm gap |
| J502 | W15-b bias ribbon | control board J5 | 2x5 shrouded IDC; body x 496.7-518.1, y 135.5-146.4 | **(512.50, 140.20)** (needs J5 at (512.50, 115.73), C1) | long axis along x, pin 10 at (502.34, 142.74); odd row front (y 140.20); key as J5 (translation) | flat ribbon toward the front | straight 1:1, **0 folds**, conductor 1 on pin 1 both ends; 24.5 mm between pin rows, cable 30-35 mm. One row behind J501 so it clears H3; its ribbon passes beside J501's socket (x 501-514), not under it, and below H3's screw head |
| J503 | W16-a HV_PERMIT | HV supplies J501 (562, 48) | Molex KK-254 1x2 vertical (22-27-2021); body x 489.2-495.3, y 143.1-149.9 | **(491.00, 146.50)** | pins along +x (pin 2 at 493.54); friction lock toward the rear | down, then east | twisted pair AWG 24-26 through the HV arm's ribbon corridor (y 127-147), then south along the control board's east edge (x ~556) to J501: about 0.20 m. Wired pin to pin, orientation only sets the lead dress |
| J101 | W04-b | HV supplies J201 (x 527-537, y 166-190) | 2x 4.8 mm PCB tab, blade plane along y | tab 1 **V_ANODE (514.50, 161.00)**, tab 2 **GND_PWR (514.50, 170.50)** | legs at y ± 2.5; receptacle envelopes x 511.3-517.8 (inside the outline, 1.3 mm from the east edge) | down | jumpers 1.0 mm² (AWG 18) silicone ≥ 600 V, V_ANODE and GND_PWR twisted, about 0.10 m, a U under both boards into the arm's receptacles from below; tabs and leads sized for the 3.0 A trip (0.6-0.7 A continuous). GND_PWR is this board's star |
| J102 | W05-b | HV supplies J202 (527-537, 150-160) | 1x 4.8 mm tab, blade along y | **V_SCREEN (514.50, 151.50)** | as J101 | down | 1.0 mm² silicone ≥ 600 V, about 0.10 m, run with the W04 pair |
| J103 | W06-b heaters | tube PSU HT_6V3 / HT_GND | 2x 6.3 mm tab, blade along x | **HTR1 (390.00, 181.00)**, **HTR2 (401.50, 181.00)** | envelopes y 177.3-184.8, x 385.3-406.3 (rear gap between V2 and V3) | down | twisted pair ≥ 1.5 mm², 6.0-6.4 A, about 0.4-0.5 m from the PSU's cable hole (route C5). Entry in the middle: 3.2 A each way on the board (stacked HTR1 on F / HTR2 on B along the rear edge, pins 7 at the rear) |
| J104 | W11-a | output transformer primary P1 / P2 / CT (its own leads) | 3x 4.8 mm tab, blade along x; pad 1 OT_A, pad 3 OT_CT in the middle, pad 2 OT_B | **OT_A (393.00, 134.00)**, **OT_CT (405.00, 134.00)**, **OT_B (417.00, 134.00)** | 12 mm pitch: 9.4 mm between pads (≥ 6.3 mm), envelopes y 130.8-137.3 | down | the OT's leads drop through the 15 mm lead hole (415.5, 90.1) (assumed the primary's, C4) and run about 40 mm back to the board's front edge: about 80 mm from the hole; fully insulated receptacles. Clamps (RGP02-20E, 2x P6KE350CA per side) beside J104 |
| J201 | W09-b | tube PSU -80V OUT / SEC GND | 2x 4.8 mm tab, blade along x | **-80V (475.00, 147.00)**, **BIAS_RTN (484.50, 147.00)** | envelopes y 143.8-150.3 | down | twisted pair 0.5 mm², ≥ 600 V insulation (it travels in the HV harness), about 0.4 m, route with the heater lead (C5) |

No low-voltage supply tabs: +15 / +5 / -15 V come on W14 pins 1 / 3 / 5 (interfaces.md 6.1).

### Block zones (drawing)

Tube circuits V1-V4 in the rear band (y 157-187) with the gaps; heater entry J103 and screen-resistor
overflow in the V2-V3 gap; **1.25 kV corridor** y 149.5-157 from x 290 to 505 (OT_A west, OT_B east, on
B, plate pins at the front) plus the **J104 cluster** x 383-427, y 127-150, 6.3 mm keep-outs drawn;
V_ANODE (440 V) on F over the OT_B corridor from J101 to J104-3; drive entry, side-A coupling caps and the
bias channels (300 V parts ≥ 25 mm from a socket: the whole front band y ≤ 147 qualifies) at x 300-382;
the **≥ 40 mm strip** = the front band clipped by 40 mm circles round the socket centres; the digital
island (DGND) x 469-519, y 127-147 with J501, J502, J503, J201; the star at J101-2.

**Finding for the layout (not an interface):** the ≥ 40 mm area is small. Front band (y ≤ 145): 2275 mm²
over the whole board, but most of it is a 5 mm strip along the front edge; between V3 and V4 (x 430-470,
next to the ribbons) only 463 mm². At ≥ 35 mm: 610 mm² there, at ≥ 30 mm 697 mm². The reference, the
dividers, the zener string (2x 1 cm² copper), DAC, ADC, two OPA4197 and two LM2901B need about
900-1000 mm². Proposal for the layout pass (user): 40 mm for the 85 °C parts (LM4040-10, ADS7828), the
reference, zener string and 0.1 % dividers; ≥ 30 mm for the 125 °C op amps and comparators.

### Keep-outs

| Against | Mine for them | Theirs for me |
|---|---|---|
| Rear I/O (x 276-322, its SMD end y 195.7, 8.3 mm gap) and W19 | Nothing past the rear edge y 187.38 **over the whole length** (W19 runs from the HV arm west behind this board to x 264); tabs and receptacles inboard | none needed beyond that |
| HV arm (x 525, 5.9 mm from the east end x 519.09) | No overhang at the east end: J101 / J102 envelopes end at x 517.8; the three jumpers cross the gap **below** the boards (y 150-185, 17-45 mm below the plate) | W19 must not cross the gap at y 145-175 at the boards' level (use the corridor and pass below 50 mm there, or behind the arm) |
| Ribbon corridor y 127-147 under the arm | W16 uses it; W14 / W15 do not (straight to J4 / J5) | stays free of bottom-side parts (as the HV supplies drew it) |
| Control board (front edge y 122, 5 mm gap over x 426-519) | No overhang at the front edge; W14 / W15 cross the gap at x 469-514 | J4 / J5 moved by -8.90 mm (C1); nothing tall under the two ribbons at y 116-127 |
| PI + FX (x ≤ 278.7, 1.6 mm gap over y 127-176) | No overhang at the west edge; J105 body from x 283.3 | its W24 header toward this board (C2) |
| OT primary leads (x 393-417, y 90-134 in front of the board) | — | **W13 (control board J3 → PI + FX, PVC ribbon about 300 V) must not touch the OT primary leads (1.25 kV peak in an open-load event)**: cross at right angles, ≥ 10 mm apart, or sleeve (cable rule for the coordinator) |
| Plate (15 mm above) | B side: socket bodies and solder joints only; HV copper ≥ 6.3 mm from the OT bolt axes | OT bolts ≤ 10 mm below the plate |

### What the mating boards need to do

- **Control board (J4 / J5):** move **J4 and J5 by -8.90 mm in x** (J4 pin 1 → (490.50, 115.73), J5 pin 1 →
  (512.50, 115.73)), same rotation, odd rows at the front as now. Reason: J5 as placed spans x 505.6-527.0,
  past this board's east edge (519.09) and into H3 (514.95, 131.45); no straight W15 exists. Their J15 debug
  header (x 468.73) then sits on J4's body (x 469.7) and needs to move a few mm; J9 (x 444-466) stays clear.
- **PI + FX (J201, W24-a):** a Mini-Fit Jr 2x3 on its downward face at its east end, within x 255-278,
  y 130-160 (so W24 stays ≤ about 0.15 m); orientation free (discrete wires), pin 1 marked; same circuit
  assignment (1 GND, 2 DRV_A, 3 GND, 4 DRV_B, 5 GND, 6 N/C).
- **HV supplies:** tell which of J201's two tabs is V_ANODE (assumed the south one, y ~172) so the jumpers
  don't cross; keep J201 / J202 where they are.
- **Tube PSU harness:** heater pair and -80 V pair from its cable hole to J103 (x 390-402, y 181) and J201
  (x 475-485, y 147), C5.

### Open choices (two reasonable options each; preference first)

- **C1 W15 / W14:** (a, preferred) control board moves J4 and J5 by -8.90 mm, both ribbons flat, 0 folds;
  (b) control board unchanged: J501 stays straight at pin 1 (499.40, 132.80), J502 turns 90 deg (long
  axis along y at x 511.3-513.8, pin 1 at the south end, odd row on the west side) behind H3, and W15 takes
  **one 45 deg fold** under it (conductor 1 still on pin 1); costs the east tab strip about 9 mm
  (V_SCREEN / V_ANODE / GND_PWR move north) and the rear standoff H1 moves to (475.9, 165.3). A paper
  ribbon check is needed for (b).
- **C2 W24 header row direction:** (a, preferred) rows along x as above, pins 1 / 4 at the west end
  (nearest the PI + FX; DRV_B leaves east along the 4-5-6 row past GND 5); (b) rows along y (long axis
  front-rear) if the PI + FX header ends up behind y 150. Electrically the same.
- **C3 rear support:** (a, preferred) H1 / H2 on two of the old socket flange holes already in the plate,
  **(513.5, 179.0)** and **(315.4, 178.9)** (3.5 mm, unused; no new chassis work), optionally a third at
  (447.4, 179.0); rev A's H1 / H2 dropped. (b) keep rev A's H1 / H2 (514.95 / 284.95, 182.45) and drill two
  new plate holes. Rev A was held only at the front edge (2 of 4 holes on the chassis), 45 mm from the
  sockets: a rear standoff takes the tube insertion force.
- **C4 OT lead hole:** the primary is assumed to come down the east hole (415.5, 90.1); if it is the west
  hole (331.4, 90.1), J104 stays where it is and the leads run about 85 mm along the front (user: which
  hole carries the primary?).
- **C5 heater and -80 V lead route** from the tube PSU's cable hole (658.5, 154.6): (a, preferred) along the
  chassis floor under the HV supplies and this board (below 50 mm depth), rising into J103 / J201 from
  below; (b) along the rear panel behind the HV arm's rear strip and this board (it then shares the
  y 187-210 strip with W19).
- **C6 test points:** (a, preferred) none (currents over the ADC / Ethernet), plate holes plugged;
  (b) four cathode-current test pads on the board, reachable from below (no plate jacks).

---

## Third pass (2026-11-23)

The user's decisions of 2026-11-23 (coordinator's list, through V1-V5, V15, 16) drawn. ERC 0 errors /
1 warning (the same intended ADS7828 REF one); **328 parts**, 98 BOM lines.

### What changed

| # | Decision | Drawn | Check |
|---|---|---|---|
| 1 | Grid leak 91k, coupling cap 220 nF film ≥ 630 V, all four types (V1, V2) | R101/105/109/113 91k axial 0207 (350 V); C103-C106 220n / 630 V MKP on a 22.5 mm MKS4 footprint | Grid circuit 91k + 5.6k + 1k = **98 kΩ**. **6550 deviation:** 98 kΩ against its 50 kΩ fixed-bias rating (Tung-Sol), accepted by the user; covered by the cold-default bias, the per-tube firmware current loop and the 220 mA hardware over-current trip. Within rating for 6L6GC and KT88 (100 kΩ) and EL34 (500 kΩ). Stated on sheet 01 and in the README |
| 2 | Open-load protection fitted (V3) | Per plate **D101 / D104 RGP02-20E** (Vishay, 2 kV, 0.5 A, 300 ns, DO-41) from GND to the plate; per primary half **D102+D103 / D105+D106: 2x P6KE350CA** in series (Littelfuse, bidirectional, VBR 332 / 350 / 368 V at 1 mA, VC 482 V at 1.24 A, 600 W, 5 W steady state, DO-15) from the plate to OT_CT (= V_ANODE). The optional UF4007 clamps are gone | One 2 kV part instead of 2x UF4007: no static sharing to manage (2x 1 kV in series at 1.1-1.25 kV would need sharing resistors of about 1 MΩ each, 0.6 kV rated, permanently loading the plate). The TVS string needs no sharing resistors (a resistor would be a DC path plate to centre tap); a leakage imbalance only puts one TVS into its knee at µA, the string stays off. Re-run of the study's clamp check with these parts (`sim/pi_nfb/run_clamp_check.py`, copy; results `sim/pi_nfb/results/clamp_check.md`): string 664 / 700 / 736 V (VBR min / nom / max), 184 Ω dynamic, 15 pF; 220n / 91k, Rf 100k, V_ANODE 400 V, 18 V at the PI input |
| 3 | W24 = Molex Mini-Fit Jr (V5) | J105 2x3, **Molex 39-28-1063 class** (5566-06A vertical; order code to confirm), receptacle 39-01-2060; circuits 1-5 = GND, DRV_A, GND, DRV_B, GND; circuit 6 N/C; footprint Connector_Molex:Molex_Mini-Fit_Jr_5566-06A_2x03_P4.20mm_Vertical | 600 V AC/DC. Pad layout: row 1 = 1 2 3, row 2 = 4 5 6 (5.5 mm). DRV_A (2) has GND at 1, 3 and 5; DRV_B (4) has GND at 1 and 5; the two drive lines are diagonal (6.9 mm), antiphase on the same DC (≤ about 140 V between them). No reason to change the assignment |
| 4 | V_ANODE 0.6 A continuous; HV trips at 2.0 A (decision 15) | Layout rule: V_ANODE / OT_CT / OT_A / OT_B copper and the 4.8 mm tabs for **2.0 A** continuous (about 3 mm in 2 oz external at a 20 K rise) | `sim/power_stage/run_anode_current.py` (results/anode_current.md), below |
| 5 | +15 V present 13.0 / 13.25 V; pump 56k + 1k; DAC 0x48 / ADC 0x4B; X9 wording | As drawn in the second pass | — |
| 6 | Rear edge and the HV arm | Layout notes (README) | — |

### Clamp check with the chosen parts

| Case (all four types, 100 Hz and 1 kHz) | Plate to ground | Plate to centre tap (across the string) | Clamp |
|---|---|---|---|
| Loaded (speaker model or 8 Ω), full overdrive | 0.71-1.03 kV | **≤ 631 V** (EL34 1 kHz; KT88 624, 6550 616, 6L6GC 548) | off with the lowest string (664 V): 0.00 W, ≤ 0.1 mJ of knee current |
| Speaker pulled while playing | **1.10-1.24 kV** (664-736 V strings) | 0.70-0.84 kV | ≤ **6.9 mJ** per event, then ≤ 0.46 W for both halves together (≤ 0.12 W per TVS) with no load at full drive |
| Lowest plate | -2 V (the plate diodes conduct) | | |

The "real voltage across the clamp" is plate-to-ground minus V_ANODE: the 0.87-1.09 kV plate peaks of
the study are 0.47-0.69 kV across the string. Margin of the lowest string to the loaded peak: 33 V
at 25 °C; the TVS breakdown falls about 0.1 %/K when cold, so at 0 °C about 16 V is left (it then
starts to conduct a little in the EL34 1 kHz overdrive case, not a hazard: µA to mA in a 600 W part).
If more margin is wanted: P6KE350CA + P6KE400CA (VBR min 712 V; unplug peak then up to 1.29 kV).

**Creepage / clearance:** OT_A, OT_B and the TVS midpoints CL_A / CL_B reach **1.25 kV peak to GND**
and up to 1.25 kV between OT_A and OT_B. IPC-2221B B2 (external, uncoated): 0.005 mm/V above
500 V = **6.3 mm**. Rule for the layout: ≥ 6.3 mm creepage and clearance from those nets to anything
else (and between them), slots where it can't be met; the RGP02-20E on a 12.7 mm pitch (body 5.2 mm),
the TVS on 12.7 mm (each sees ≤ 0.42 kV); the 4.8 mm OT tabs with fully insulated receptacles. The
OT primary's own insulation at 1.25 kV is a question for Hammond (output_stage_stability.md).

### V_ANODE current (stage.py with the decided parts, V_ANODE 400 V, idle 70 % of Pa max, 8 Ω, stiff 5 Ω supply)

| Set | Drive | V_ANODE average | V_ANODE peak | V_SCREEN average | One plate peak |
|---|---|---|---|---|---|
| 4x KT88 | sine, 160 V into the PI clip | **0.59-0.60 A** | 0.62-0.76 A | 0.13 A | 0.39 A |
| 4x KT88 | square (PI fully clipped) | **0.64-0.66 A** | 0.65-0.79 A | 0.18 A | 0.40 A |
| 4x EL34 | sine | 0.53-0.54 A | 0.56-0.69 A | 0.12 A | 0.35 A |
| 4x EL34 | square | 0.61-0.62 A | 0.62-0.71 A | 0.15 A | 0.36 A |
| 4x 6550 | sine / square | 0.50-0.51 / 0.55-0.57 A | 0.52-0.65 A | 0.14-0.18 A | 0.33 A |
| 4x 6L6GC | sine / square | 0.48 / 0.55-0.56 A | 0.50-0.59 A | 0.03-0.04 A | 0.30 A |

(Ranges: 1 kHz to 100 Hz; the 100 Hz peaks are higher. The output in these runs is 110-200 W, deep overdrive with a stiff supply: the worst case, not a rated power.)

**0.6 A continuous holds for sine overdrive with every type; a square-wave overdrive (the PI fully
clipped, a fuzz into the loop) takes KT88 to 0.64-0.66 A and EL34 to 0.61-0.62 A**, and the KT88 model
reads about 12 % low on plate current at full signal (sim/models), so a real KT88 set could reach
about 0.7 A average. That is 10-20 % over 0.6 A only in a sustained square-wave case; the real
supply's sag lowers it. Proposal: state V_ANODE as 0.6 A continuous with 0.7 A for minutes (thermal
check on the HV supplies), peaks 0.8 A; the 2.0 A trip doesn't come near. **New: V_SCREEN averages
0.12-0.18 A at full overdrive** (EL34, KT88, 6550), above the 100 mA average in interfaces.md 3.2
(the 0.25 A peak holds); the screen resistors then dissipate about 2-2.5 W each (5 W parts: OK).

### Interface check (changes since the second pass)

Row 12 (W24 header) **OK** now (Mini-Fit Jr, 600 V). Row 14 (grid circuit) **OK** (decided; 6550
deviation recorded). Rows 25, 27 (X9 wording) **OK** (accepted). Row 37 (V_ANODE) **OK** with the
note above. New row 43: V_SCREEN average at overdrive, **question** (0.18 A against 100 mA). New row
44: open-load protection fitted, **OK** (creepage rule above). New row 45: the OT primary's insulation
at 1.25 kV peak to ground with the clamps, **question** (Hammond). Row 38 (rear edge): **OK** as a
layout constraint (README). **45 rows: 40 OK, 0 problems, 5 questions (3, 8, 41, 43, 45).**

### Proposals / new items

- V_SCREEN: 3.2 says 100 mA average; full overdrive gives 0.12-0.18 A (HV supplies, interfaces.md 3.1 / 3.2).
- V_ANODE: 0.6 A continuous, about 0.7 A average for minutes in square-wave overdrive with KT88 (HV supplies thermal check).
- Hammond: primary insulation for 1.25 kV peak to ground with the clamps.
- W24: no change to the assignment proposed.

---

## Second pass (2026-11-23)

Against interfaces.md **IF-1.2** (IF-2 on W17, which this board doesn't use), the bias decisions of
2026-11-22 and review 7.1. What changed and why: [README.md](README.md) "Second pass". ERC 0 errors /
1 explained warning; 326 parts; footprints on every part; BOM `bom/tube_power_amp_revb_bom.csv`.

### S1. Interface check against IF-1.2

| # | Item (interfaces.md section) | Verdict | Notes |
|---|---|---|---|
| 1 | W04-b J101 V_ANODE + GND_PWR, 4.8 mm tabs (2.1, 4.3) | OK | One ground entry, the AGND star |
| 2 | W05-b J102 V_SCREEN (2.1) | OK | |
| 3 | W06-b J103 heaters 6.3 mm, 6.0-6.4 A, 6.3 V ±5 % at the sockets (3.1) | question | Unchanged from the first pass: 0.1-0.2 V lost in leads and tabs at 6.4 A; who holds the socket voltage (PSU set point, sense)? |
| 4 | Heaters float, EL34 Vhk with the +90 V option (5) | OK | 10 V margin to 100 V |
| 5 | W09-b J201 -80 V + BIAS_RTN on DGND (2.1, 5) | OK | |
| 6 | -80 V: 25 mA requested (3.1-3.3) | OK | Board needs 5.4 / 14.2 / 21.3 mA (cold / typical / hot end), about 22.7 mA worst case with the monitor and ADC dividers (+0.7 mA over the [BIAS] figures). The PSU's allocation is still the PSU owner's answer |
| 7 | -80 V ±2 V (3.1) | OK | 72 V string in regulation down to -78 V (with the zener self-heating counted); rail monitor release worst -76.57 V, 1.2 V clear of -77.8 V |
| 8 | 10 Ω fusible resistor at the input (2.1, 3.1) | question | Drawn (1 W fusible wirewound). The 100 µF behind it takes 8 A peak / 0.32 J if the -80 V appears as a step (hot-plug); the CRF datasheet's energy curve allows it (0.9 W·s) but no peak-current time base is given: a bench test, or a slow-rising -80 V from the PSU (its ramp time is a PSU question) |
| 9 | No hold-up required (3.1) | OK | BIAS_OK low 28-65 ms after the source goes, bias drift 0.02 V (drawn monitors) |
| 10 | Sequencing: BIAS_OK before the HV (3.1, 3.4) | OK | BIAS_OK 84-88 ms after the rails are good; never early in six rail orders |
| 11 | W11-a J104 OT_A / OT_B / OT_CT (2.1) | OK | |
| 12 | W24-b J105 Lock-3.96 header, ≥ 390 V between adjacent pins (2.3, 10) | **problem** | KK-396 headers (Molex 26-60-4050, series 41791) are rated **250 V**, JST VH 250 V. TE MTA-156 (3.96 mm) 600 V AC, Molex Mini-Fit Jr (4.20 mm) 600 V AC/DC. Proposal P1 |
| 13 | W24 DC 280 V, 390 V PI cold; caps ≥ 450 V (10) | OK | 630 V MKP, 15 mm footprint |
| 14 | Coupling cap / grid leak OPEN; max fixed-bias grid resistance (10, 14) | question | Datasheet limits: 6550 50 kΩ, 6L6GC 100 kΩ, KT88 100 kΩ (GEC), EL34 500 kΩ; 100k drawn = 107 kΩ in circuit. Proposal P2, user decision |
| 15 | W24 grounds solid at this end (5) | OK | |
| 16 | W14-b J501 template 2x7 (6.1) | OK | MUTE_ALL_N 100k pull-down, RESET_N 10k pull-up |
| 17 | Expander required (6.3, 7.3) | OK | U501 MCP23S17-E/SS, address 000 |
| 18 | Map 7.3: GPA0 OC_CLR, GPA1 HV_PERMIT_REQ, GPA2-5 reserved | OK | 100k pull-downs |
| 19 | W15-b J502 2x5 pinout (6.3) | OK | |
| 20 | I2C 5 V, 100 kHz, 4.7k pull-ups here (6.3) | OK | |
| 21 | I2C addresses (6.3 says OPEN; review section 10 accepted) | OK | DAC 0x48, ADC 0x4B: record in 6.3 (P6) |
| 22 | BIAS_EN 5 V 10 kHz ±50 %, 74AHCT + 100 Ω on the card, ≥ 470 Ω here (6.2, 6.3; review X10) | OK | 1k + 56k hold: 3.8 mA peak, release 1.2-4.5 ms, cold 76-131 ms, 5-15 kHz, static high or low = cold |
| 23 | BIAS_OK = VNC good, -80 V rail present, +15 V present; independent of BIAS_EN (6.3, 8) | OK | Drawn as three comparators; "+15 V present" = above 13.0 V (release 13.25 V): P4 |
| 24 | BIAS_OK thresholds -63.0 / -64.5 V and -75.0 / -75.5 V, 0.1 % dividers (8) | OK | Real circuit, 0-85 °C worst case: within the [BIAS] ranges (README) |
| 25 | OC_TRIP_N latched; card pull-down (6.3) | question | The accepted X9 wording ("powers up tripped; the firmware pulses OC_CLR after reading the currents") is not yet in 6.3 / 8: P3 |
| 26 | Over-current 220 mA ±5 %, two-pole filter (8) | OK | ±3.4 % worst case with the drawn parts |
| 27 | HV_PERMIT_MON (6.3) | question | 6.3 says "high = the power amp is driving HV_PERMIT"; the circuit senses loop current (an opto in the loop). Accepted X9 wording "loop current flowing" not yet applied: P3 |
| 28 | HV_PERMIT current loop 5-10 mA; HV side TLP293 with 680 Ω across its LED (8; X33) | OK | 9.1-9.5 mA from 14.45-15 V; 1.8 mA bypasses the 680 Ω, 7.3-7.7 mA in the HV LED (turn-on 3.5-4 mA) |
| 29 | HV_PERMIT = BIAS_OK AND NOT OC_TRIP AND WARM_OK AND HV_PERMIT_REQ (8) | OK | Plus OC_OK alone on the low-side switch |
| 30 | Hardware warm-up timer (8) | OK | Kept, 31 s |
| 31 | 5 V CMOS logic, no 3.3 V parts (6.2) | OK | |
| 32 | Fail-safe: card absent / unconfigured / ribbon out (6.2, 8) | OK | |
| 33 | Fail-safe: -15 V missing (6.2) | OK | |
| 34 | -80 V lost with the HV on (8) | OK | Rail monitor trips before the bias moves; the HV's own discharge stays the HV supplies' item (K12) |
| 35 | Grounding (5, grounding.md 4) | OK | |
| 36 | OT secondary COM not here (5) | OK | |
| 37 | V_ANODE 0.5 A peak budget (3.1, 3.2) | question | Board passes about 0.57 A average (KT88 set, full sine); copper sized for the 1.0 A trip. P5 |
| 38 | Envelope, outline as built (12.1, 12.3) | question | The rear I/O box overlaps the rear edge by 42 x 4 mm at x 280-322 (still open on the rear I/O side): keep that strip of this board free of tall parts below the board (≤ about 8 mm) until it is resolved |
| 39 | Connector positions (12.3) | OK | |
| 40 | Rail row 3.2: +15 / -15 / +5 V | OK | +15 V 41 / 50 mA (row says about 40), -15 V 9 / 10 mA (says 25), +5 V 6 / 9 mA (says 15) |
| 41 | 70 °C under the plate (SPEC ENV-2, parts ≥ 85 °C) | question | LM4040-10 exists only in I grade (85 °C) and the ADS7828 is an 85 °C part: placed at the cool rear end, assumed 85 °C local, no margin; to confirm by M39 or replace (an 85 °C part list is in the BOM notes) |
| 42 | Relay family (3.1) | OK | No relay on this board |

**42 rows: 33 OK, 1 problem (12), 8 questions (3, 8, 14, 25, 27, 37, 38, 41).**

### S2. Interface changes proposed (to the coordinating session)

| # | What | Why | Boards | interfaces.md |
|---|---|---|---|---|
| P1 | W24 connector family: a 3.96 mm header rated ≥ 450 V DC between adjacent pins — **TE MTA-156** (600 V AC; DC rating to confirm with TE) or **Molex Mini-Fit Jr** (600 V AC/DC, 4.20 mm), instead of KK-396 (250 V). Pinout unchanged. (Alternative without a family change: a 1x9 KK-396 with pins 2, 4, 6, 8 removed, but 250 V is a per-pin rating, so this is not a real fix) | Measured line voltage up to 390 V | PI + FX, power amp | 2 (families), 2.3, 10 |
| P2 | Record the fixed-bias grid-circuit limits in 10: 6550 50 kΩ, 6L6GC 100 kΩ, KT88 100 kΩ (GEC; 220 kΩ below 35 W, Gold Lion), EL34 500 kΩ. The coupling-cap / grid-leak choice then has three options: ≤ 100k (above the 6550 rating, at the 6L6GC / KT88 limit), 220k (above three of four), or 39k + 270n (meets all, costs drive) | Asked by the review (K3); none of the options in 10 meets the 6550 | power amp, PI + FX | 10, 14 |
| P3 | Apply X9's accepted wording: 6.3 OC_TRIP_N "the latch powers up tripped; the firmware clears it with OC_CLR after reading the four currents, before HV_PERMIT_REQ"; HV_PERMIT_MON "high = loop current flowing (opto in the loop)" | Accepted 2026-11-21, not in IF-1.2 | power amp, control board | 6.3, 8, 3.4 |
| P4 | BIAS_OK's "+15 V present" = +15 V above 13.0 V (back at 13.25 V) | Below about 11.5 V the 10 V reference drops out and the monitors' thresholds move toward 0 V (permissive); 13.0 V keeps them valid | power amp | 6.3, 8 |
| P5 | V_ANODE row: 0.6 A average (KT88 set, full sine overdrive), sized for the 1.0 A trip | X35, accepted with change | HV supplies, power amp | 3.1, 3.2 |
| P6 | 6.3: I2C addresses DAC 0x48, ADC 0x4B (OPEN there, accepted in review 10) | Close the item | — | 6.3, 14 |
| P7 | bias_supply.md watchdog: with the 5 V BIAS_EN (6.3) the pump needs 56k (not 100k) across its 1 µF to keep the cold time at about 130 ms; plus the 1k series resistor | Master simulated a 3.3 V drive | power amp (master doc only) | 6.3 note; bias_supply.md |

### S3. Rail currents (interfaces.md 3.2)

| Rail | Typical | Max | Notes |
|---|---|---|---|
| -80 V | 14.2 mA | 21.3 mA (typical board), ~22.7 mA worst | 5.4 mA all cold; monitors.md section 4 |
| +15 V | 41 mA | 50 mA | bias circuit + monitors 21 / 30 mA (sim), 2x OPA4197 8 mA, 2x LM2901B 1.6 mA, HV_PERMIT loop 9.4 + 1.5 mA |
| -15 V | 9 mA | 10 mA | the two OPA4197 |
| +5 V | 6 mA | 9 mA | DAC, ADR4525, ADC, expander, logic, pull-ups |
| Heaters | 6.0 A (EL34) | 6.4 A (KT88) | + 4 mA warm-up sense |
| V_ANODE / V_SCREEN | — | 0.6 A average (KT88 full sine) / 0.25 A peak | passes through the board |

### S4. Still open

- **User:** coupling cap / grid leak with the grid-resistance limits (P2); W24 connector family (P1);
  fit the anode flyback clamps (SAFE-5, drawn as an option); keep the warm-up timer (kept).
- **PSU owner:** 25 mA on -80 V; the -80 V rise time (inrush through the fusible resistor).
- **HV supplies:** HV discharge after an inhibit (K12); confirm TLP293 drop at 7-8 mA.
- **Rear I/O:** the 42 x 4 mm overlap at this board's rear edge.
- Datasheet checks left: DAC7578 power-on state and ~CLR, ADS7828 external reference (firmware PD1 = 0),
  MMBTA92 / A42 / BSP92P leakage at 90 °C, PC817 CTR at 4 and 9 mA, LM2901B orderable suffix,
  the 1 W fusible part's inrush rating, a ≥ 450 V DC W24 header.
- Two 85 °C parts at an 85 °C assumption (LM4040-10, ADS7828E): no margin until measured.

### S5. Missing simulations

| # | Simulate | Why |
|---|---|---|
| S1 | Bias channel with vendor models (OPA4197, MMBTA92 / A42, BSP92P), at 90 °C | Loop stability, noise, leakage at temperature |
| S9 | Zener filter with the ceramic capacitors (about 6 µF effective at 72 V instead of 10 µF) | Noise and -80 V rejection; corner 0.16 → about 0.3 Hz |
| S10 | Comparator vendor model (LM2901B) in the monitor block | Confirms the behavioural model's start-up behaviour below 2 V supply |
| S11 | C201 inrush through R201 with the PSU's real -80 V ramp | Fusible resistor survival |
| S4 | Over-current threshold on measured tubes with a guitar signal | ±5 % margin (bias_supply.md open item 3) |
| S6 / S7 / S8 | HV discharge after inhibit; tube arc through the sense chain; board thermal (M28, M20, M39) | as first pass |

Done this pass: monitors as real circuits (tolerance 0-85 °C, hysteresis, start-up in six rail
orders, -80 V lost), -80 V / +15 V current with the dividers, the BIAS_EN pump with the card's driver.
Not re-run: the sense filter (the drawn circuit is the master's `two_real_220` variant) and the
zener corner run (datasheet TC equals the figures used; self-heating estimated in README).

### S6. Next steps

1. Decisions P1 / P2; then the coupling parts' values.
2. Placement study in 239 x 60 mm with the temperature zones of the README; a ≥ 450 V W24 header
   footprint; blade-tab part and spacing (replace the placeholders).
3. S1, S9, S11; vendor-model check of the monitors (S10).
4. Tidy schematic pass (the drawing is still netlist-first).

---

## First pass (2026-11-21)

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
