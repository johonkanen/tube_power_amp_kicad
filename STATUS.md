# Status: Power amp (`OUTPUT`)

Plan: [PLAN.md](PLAN.md). Playbook: `tools/p2k/CONVERSION_PLAYBOOK.md`.

| Phase | State |
|---|---|
| 0 Skeleton and inventory | **done** 2026-11-20 (Opus 5.5) |
| 1 Schematic | not started (next: preparation session, see next_prompt.md) |
| 2 Footprints | not started |
| 3 PCB | not started |
| 4 Verification | not started |
| 5 Clean-up | not started |

## Phase 0 – done (Opus 5.5, 2026-11-20)

- **Inventory measured** (PLAN.md section 1 corrected): 43 nets, 146 IPC records (142 THT
  component pads + 4 plated 3.0 mm mounting holes), 0 SMD, 0 N/C, 0 vias, 0 free pads, no pours
  (no `G36`/`%LPC%`), no arcs, 2 copper layers, outline 238.76 x 60.325 mm. 72 parts: the
  pre-check's 71 counted the IPC refdes field, where `BIASPO` is two parts.
  Corrections to the pre-check: the octal sockets are **U6-U9** (not U1-U4); there are **29**
  single-pad terminals (not 28: `BIASPOTX` and `BIASPOTO`); the terminal `HT +6` of the
  pre-check list is the net name, the terminal is `HT+6`; `VS'` is a terminal on its own net;
  the mounting holes have a 6.35 mm pad on both layers.
- **PDF:** 3 pages, rendered with `pdftoppm -r 200 -png source/schematic_pdf/OUTPUT.PDF
  build/tmp/pdf/hi` (`hi-1..3.png`, git-ignored; re-render in later sessions). The 2010 pages
  have **no title block**, and neither ROOT.DSN nor PROJECT.XML carries sheet names, so the
  SHEETS names describe the content: 1 **Output stage** (U6-U9, R1-R16, C1-C4, OT),
  2 **Bias regulator** (Q1-Q3, R17-R23), 3 **Bias supply** (D1-D5, R24/R25, C5/C6). Rename in
  `p2k_config.py` before `make_skeleton` if the user prefers other names.
- **`p2k_config.py`** complete for Phase 0: SHEETS, `TRUNCATED_REFDES` (+ `TRUNCATED_NETS`),
  `KICAD_REFDES`, `NET_ALIASES` (empty), blank-refdes drills, `EXPECTED_IPC`, `COPPER`, drills,
  outline. Tables:

  | IPC field | Full Proteus refdes | Net (check) |
  |---|---|---|
  | `STANDB` | STANDBY | `VS'` |
  | `BIASPO` @ (-27.305, -13.970) | BIASPOTX | `#00035` (R22-2, Q1-2) |
  | `BIASPO` @ (3.175, -6.985) | BIASPOTO | `#00044` (R23-2) |
  | `BIASGN` | BIASGND | `OTGND` |
  | `P.I.GN` | P.I.GND | `#00023` |

  `VA GND` and `REFGND` are exactly 6 characters and complete (PDF and ROOT.DSN agree).

  | Proteus refdes | KiCad refdes |
  |---|---|
  | `+6` / `-6` | `P6` / `N6` |
  | `HT+6` / `HT -6` / `HT-0` | `HT_P6` / `HT_N6` / `HT_0` |
  | `VA GND` / `P.I.GND` | `VA_GND` / `PI_GND` |
  | `VS'` | `VS_PRIME` |
  | `IN6+7` / `IN8+9` | `IN6_7` / `IN8_9` |

  No single-letter refdes on this board. Refdes without a trailing number (VCC, VREF, STANDBY,
  BIASGND, ...) stay as they are (tube_psu has `SEC_GND`, accepted by ERC/DRC).
  Net names: no `=POWER` nets; the named nets `HT +6`, `VS'`, `B-`, `OTGND` keep the IPC spelling
  (labels with spaces work in KiCad: tube_psu `-100V BIAS`), the rest are Proteus auto-names.
- **`p2k ipc356`** wrote `reference/` (`ipc356_pads.{json,csv}`, `pin_nets_by_component.md`,
  `pins_by_net.md`); `--check` passes. **`p2k check_sources`** passes: 142 ComponentPad + 4
  OtherPad flashes per copper layer and 146 plated drill flashes match the IPC 1:1, one
  SameCoordinates id, outline. Both negative-tested (hole count 5, holes unplated, outline
  height 60.0: all fail; restored: pass).
- **`tools/check_all.sh`**: KiCad environment, IPC self-check, X2 vs IPC.
- Notes for the later phases:
  - Phase 1: OT (1650TA) and VA' are drawn in the PDF but have no pads → `OFF_BOARD_PARTS`
    (Phase 2) and excluded from the board in the part map. `VS'` on sheet 1 is a net terminal
    (label), `VS'` on sheet 2 is the part. Sheet 3 writes `otgnd`, sheet 2 `OTGND` (Proteus net
    names are case-insensitive; KiCad's are not): label it `OTGND` everywhere. The sheet 1 and
    2 labels `HT +6` are the net of the terminals `HT+6`, `+6` and `VCC`.
  - `p2k.pdsprj` works with the full refdes set (`refdes_proteus` of ipc356_pads.json plus OT
    and VA'): `dsn_values` 74 values, `lyt_parts` 71 records; C5 fails in both (see p2k candidates).
    A subset of refs makes `lyt_parts` raise "two layout records for -6" (it searches back for
    any known refdes): always pass the full set.
  - Pad / drill families: Q2/Q3 1.524/0.762, small R 1.778/0.762, Q1 2.032 square/1.016,
    D + R24/R25 2.286/1.016, C + R13-R16 2.54/1.143, terminals 3.048/1.524, octal 3.81/1.6.
  - Phase 4: the 2010 Excellon `source/fab_2010/OUTPUT - CADCAM Drill.TXT` (inch, 146 hits,
    same frame) can serve as `DRILL_EXCELLON`.

## Last check output

`tools/check_all.sh` (2026-11-20, end of Phase 0):

```
== KiCad environment
pcbnew 10.0.7
== IPC-D-356A parser self-check
ipc356: nets=43, records=146, refdes_raw=72, tht_records=146, smd_records=0, smd_top=0, smd_bottom=0, nc_pads=0, vias=0, free_pads=0, holes=4, parts=72
ipc356: OK
== Gerber X2 export vs IPC (pads, holes, drills, outline)
  8 gerbers, one SameCoordinates id
  Top Copper: Draw:Conductor 158, Draw:Profile 4, Flash:ComponentPad 142, Flash:OtherPad,Unknown 4
  Bottom Copper: Draw:Conductor 96, Draw:Profile 4, Flash:ComponentPad 142, Flash:OtherPad,Unknown 4
  drills: 146 plated, 0 non-plated
  outline 238.8 x 60.3 mm at (-104.14, -25.40)
check_sources: OK

ALL CHECKS PASSED
```

## Findings about the original design

(Report here; don't fix.)

1. **The `VS'` terminal is not on the `VS'` net.** The bias regulator's divider input (sheet 2,
   terminal `VS'` → R19) is net `#00043`; the net named `VS'` (sheet 1 label: STANDBY, R13-R16
   screen resistors) is a different net. Proteus terminal parts do not join nets by their
   refdes, so on the board the two are separate pads (presumably joined by an external wire).
   Reproduced as is; worth confirming against the built amplifier.
2. **OT and VA' are not on the PCB**: the output transformer (1650TA) and the VA' terminal are
   drawn on sheet 1 but have no layout part; OT1/OT2 are the board's OT connections.
3. **`VCC` is the heater rail**: the terminal `VCC` and R17 (bias regulator supply) are on net
   `HT +6` together with `+6`, `HT+6` and U8/U9 pin 2.
4. Export quirks (no effect on the conversion): Mechanical 1's X2 FileFunction is
   `NonPlated,1,2,NPTH` although it holds only the profile; the solder resist files are negative
   polarity.

## p2k candidates

(Shared-tool limitations met on this board, with the board-local workaround used.)

1. **`p2k.pdsprj` drops non-ASCII values.** C5's value is `10µ/400V` with a Latin-1 `µ` (0xB5)
   in ROOT.DSN and ROOT.LYT. `dsn_values` returns `None` for it (its string test accepts bytes
   32-126 only) and `lyt_parts` misses the C5 record (`_strings` splits the run at 0xB5).
   Workaround (Phase 1): give C5's value in the board's part-map script from the PDF.
   The shared tool would need: decode Latin-1 strings (0xA0-0xFF) in `pstr` and `_strings`.
2. `p2k ipc356` prints "Net aliases: ." in `pin_nets_by_component.md` when `NET_ALIASES` is
   empty (cosmetic), and its index groups `HT_0` under `HT_`.

## Decisions

- Sheet names (no title blocks in the PDF): Output stage / Bias regulator / Bias supply, chosen
  by the agent from the content; the user can rename them (only `p2k_config.py`, before
  `make_skeleton`).
- KiCad refdes for the terminals with signs/spaces/dots/quote: table above (agent's choice, same
  convention as tube_psu).
