# Conversion plan: Power amp (`OUTPUT`)

Goal: redraw the Proteus schematic in KiCad 10 and rebuild the PCB from the Proteus Gerber X2
export, so that every pad, track, via and pour carries a net from the new schematic, and **prove
with scripted checks** that the KiCad design is electrically identical to the Proteus one. The
result is **rev A, the as-built baseline** for the redesign (see README.md).

This plan follows the generic playbook **`tools/p2k/CONVERSION_PLAYBOOK.md`** (read it first) and
lists only what is specific to this board. The finished reference is `~/dev/tube_psu_kicad`
(same proteus2kicad version, Phases 0-5 done): look at its `tools/`, `p2k_config.py`, PLAN.md and
STATUS.md for how each step was done.

**Order:** **Pilot.** Smallest of the three 2010 boards: run it first. Its findings about the 2010 / Proteus 7 exports (fly-lead pads, refdes maps, THT pad sizes, octal sockets) are what the preamp and PI/FX conversions reuse.

## 1. Inventory (measured in Phase 0, 2026-11-20)

| Item | Value |
|---|---|
| Proteus project | `source/OUTPUT.pdsprj` (values, devices, packages, pin names via `p2k.pdsprj`) |
| Schematic PDF | `source/schematic_pdf/OUTPUT.PDF`, 3 pages, **no title blocks** (sheet names chosen from the content, `p2k_config.py` SHEETS): 1 Output stage, 2 Bias regulator, 3 Bias supply |
| CADCAM export | `source/cadcam/` (Gerber X2, `FSLAX45Y45`, metric, one `SameCoordinates` id, no arcs): Top/Bottom Copper, Top Silk, Top/Bottom Solder Resist (negative), Top Assembly, Mechanical 1 (outline only; its X2 FileFunction says `NonPlated,1,2,NPTH`), Drill TOP-BOT Plated; no NonPlated drill file |
| IPC netlist (the reference) | `source/cadcam/tube_output - CADCAM Netlist.IPC`: 43 nets, 146 records (all THT `317`), 0 N/C, 4 pads without a net (pin 6 of U6-U9) |
| Copper layers | 2 (Top, Bottom); conductor draws: Top 158 (0.508 / 0.762 / 1.016 / 1.27 / 2.54 mm), Bottom 96 (0.508 / 0.762 mm) |
| Pours | none (no `G36` regions, no `%LPC%`) |
| Vias / free pads | none |
| Outline | 238.76 x 60.325 mm, lower-left (-104.14, -25.40) (Mechanical 1, 4 `Profile` draws) |
| Parts | 72 after the truncation fix-up (71 distinct IPC refdes: `BIASPO` is BIASPOTX and BIASPOTO): U6-U9 (EL34, octal), Q1-Q3, R1-R25, C1-C6, D1-D5, 29 single-pad terminals. Not on the board (in the PDF only): OT (1650TA output transformer), VA' (terminal) |
| Drills | all plated: 0.762 (44), 1.016 (17), 1.143 (20), 1.524 (29), 1.6 (32; 1.6002 in the gerber), 3.0 (4 holes) = 146; the 2010 Excellon `source/fab_2010/OUTPUT - CADCAM Drill.TXT` also has 146 hits (Phase 4 `DRILL_EXCELLON` cross-check) |
| Technology | through-hole only |
| Mounting holes | 4, 3.0 mm **plated** with a 6.35 mm pad on both layers, in the plated drill file (`OtherDrill`); positions in README.md "Mechanical baseline" |

## 2. Board-specific notes and expected pitfalls

- Built about 2010; the export in `source/cadcam/` matches the June 2010 fab Gerbers (`source/fab_2010/`) exactly. Proteus 7 design (`.DSN/.LYT`) opened and saved in Proteus 8.12.
- 4 octal sockets **U6-U9** (EL34, package `8-PIN BELTON OCTAL`, 3.81 mm pads, 1.6 mm drill). Pin 1 = pin 8 (g3 to cathode), pin 6 has no net. The pin ids follow the Proteus package; check them against the octal pinout during the footprint fit.
- 29 single-pad parts (terminals, package `C-120-60`, 3.048 mm pad, 1.524 mm drill): heaters (`+6`, `-6`, `HT+6`, `HT -6`, `HT-0`), `VA GND`, `P.I.GND`, `VS'`, `STANDBY`, per-tube bias in (`BIAS6`-`BIAS9`) and sense (`VB6`-`VB9`), inputs (`IN6+7`, `IN8+9`), OT (`OT1`, `OT2`), `AC5`/`AC6`, `BIASPOTX`, `BIASPOTO`, `BIASGND`, `REFGND`, `VREF`, `VCC`. Truncated in the IPC: `STANDB`, `BIASPO` (two parts, keyed by coordinate), `BIASGN`, `P.I.GN` (`TRUNCATED_REFDES`). Names with spaces, signs, dots or `'` get a KiCad refdes (`KICAD_REFDES`, e.g. `+6` -> `P6`, `VS'` -> `VS_PRIME`). Draw them as single-pin connector symbols.
- Terminal refdes are not net names: the `VS'` terminal (sheet 2, R19) is on net `#00043`, not on net `VS'` (STANDBY, R13-R16); `VCC` is on net `HT +6`; `HT+6` (refdes) vs `HT +6` (net).
- Proteus net names are case-insensitive: sheet 3 labels `otgnd`, sheet 2 `OTGND` (one IPC net `OTGND`): use the IPC spelling.
- No pours, no vias: Phase 3 is tracks and footprints only.

## 3. Phases

As in the playbook, section 3. Board-specific done criteria:

| Phase | Done when |
|---|---|
| 0 Skeleton and inventory | `p2k_config.py` complete (sheet names from the PDF title blocks, truncated-refdes table, KiCad refdes map, net aliases, expected IPC counts, layers, drills, outline); `p2k ipc356 --check` and `p2k check_sources` pass; `reference/` cheat sheets written; `tools/check_all.sh` runs; PLAN.md section 1 corrected with the measured inventory |
| 1 Schematic | all 72 parts drawn (OT and VA' off the board); `compare_netlists` 0 wrong-net pins, every IPC net complete; ERC 0 errors (warnings explained) |
| 2 Footprints | every part fits the IPC pads within 0.05 mm (`check_footprints`); pin-order oddities reported |
| 3 PCB | copper 0 shorts / 0 orphans / 0 opens after zone fill; DRC 0 shorts, 0 unconnected, 0 parity; remaining DRC items listed and justified; `make_pcb.sh --check` reproducible |
| 4 Verification | `gerber_roundtrip --check` and `ipc356_diff` pass and are in `check_all.sh`; every new check negative-tested; preferably a different session/model |
| 5 Clean-up | only the user's choices (pad sizes, silk, refdes positions) |

When all phases are done: STATUS.md says so, and the amplifier master repo can add this repo as a
submodule (that step is done from the master repo, not here).

## 4. Effort

The playbook's estimates are for a ~270-part, 4-layer, 11-sheet board. This board has
72 parts on 3 sheets and 2 copper layers: scale accordingly.

## 5. Rules for this conversion

Several board conversions run **in parallel**, each in its own repo and session. To keep them
independent:

1. **Don't change the shared tools** in `tools/p2k` (proteus2kicad), and don't move the submodule
   pin (c5682dd). If a tool can't handle something on this board, write a board-local script in
   `tools/` (or a config key the tool already has) and record it in STATUS.md under
   "p2k candidates", with what the shared tool would need. The tool changes are made later, in one
   place, with the ac_psu regression.
2. **Don't touch other repositories.** In particular not `~/dev/tube_amplifier_kicad` (the
   amplifier master repo: it adds this repo as a submodule once the conversion is verified) and not
   `~/dev/ac_psu_kicad` (another session's work in progress). `~/dev/tube_psu_kicad` is the
   finished reference: read it, don't change it.
3. **Reproduce Proteus.** Problems in the original design are reported in STATUS.md
   ("Findings"), not fixed. The redesign happens later, from this baseline.
4. **Generate, don't hand-edit** (playbook section 1): every file in `kicad/`, `lib/` and
   `reference/` is written by a script and is reproducible.
5. **Temporary files in `build/tmp/`** (git-ignored). Never run the KiCad AppImage with
   `--version` (it starts the GUI and hangs); use `tools/p2k/bin/kipy` and `tools/p2k/bin/kicad-cli`.
6. **Commit and push at the end of every phase** (and at the end of a session), with
   STATUS.md and next_prompt.md updated in the same commit.
7. **Ask the user** where the playbook says to (pad sizes when DRC forces them, Phase 5 choices,
   anything that changes the design).

## 6. Session protocol

- Start every session by reading PLAN.md, STATUS.md and `tools/p2k/CONVERSION_PLAYBOOK.md`, then
  run `tools/check_all.sh` (from Phase 0 on) and compare with the last result in STATUS.md.
- One session per phase (Phase 1 transcription may take several, a few sheets each).
- End every session with: `tools/check_all.sh` passing for everything done so far, STATUS.md
  updated (phase state, last check output, findings, p2k candidates, decisions), next_prompt.md
  replaced with the prompt for the next session, commit and push.
