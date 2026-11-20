# Next prompt

Ready-to-paste prompt for the next agent session. Replaced at the end of every session.

```
Convert the Proteus board in /home/jari/dev/tube_power_amp_kicad to KiCad 10: Phase 1
transcription of the 3 schematic sheets (model: Fable per playbook section 6; Opus works too,
the board is small).

Read, in this order: PLAN.md, STATUS.md ("Phase 1 preparation" with its **transcription rules**,
"Findings", "p2k candidates"), tools/p2k/CONVERSION_PLAYBOOK.md (sections 1, 3 "Phase 1", 5),
tools/p2k/README.md (sheetkit, compare_netlists, render_sheet), tools/sheets/_common.py
(board helpers part/sh_value/sym/term), lib/part_map.csv, reference/pin_nets_by_component.md and
reference/pins_by_net.md. Run tools/check_all.sh first and compare with STATUS.md "Last check
output" (all passed, compare 0/72 parts present). Example sheet scripts: ~/dev/tube_psu_kicad/
tools/sheets/sheet11.py, sheet03.py and its _common.py (read only; don't change that repo).

Render the PDF pages first (pdftoppm -r 200 -png source/schematic_pdf/OUTPUT.PDF
build/tmp/pdf/hi; zoom with -r 600 -x/-y/-W/-H where it is dense) and read them.

Transcribe one sheet at a time, in this order: 3 Bias supply (14 parts), 2 Bias regulator (14),
1 Output stage (44 on-board parts + off-board OT and VA'). One script per sheet,
tools/sheets/sheetNN.py (NN = PDF page), rebuilding kicad/NN_*.kicad_sch from scratch, layout
close to the PDF. Key rules (details in STATUS.md):
- symbols/values/refdes exactly from lib/part_map.csv; terminals with _common.term(), never
  sheetkit.terminal; C5 value 10µ/400V;
- IPC net names: global labels 'HT +6' (sheets 1, 2), 'B-' and 'OTGND' (sheets 2, 3; sheet 3's
  'otgnd' is OTGND); local label "VS'" on sheet 1 only; every #000xx net is a plain wire;
- the terminal VS_PRIME (sheet 2, R19) is NOT on net VS' (no label on it); VCC is on 'HT +6';
- EL34 U6-U9: place both units (unit 2 = heater 2/7); pin 6 stays open (no_connect pin type);
- OT (OT_1650TA, P1 top / CT / P2 bottom, no-connect flags on S1-S5) and VA' (term(), symbol
  PIN_OFFBOARD) are off-board: compare ignores them;
- 1.27 mm grid; a helper in _common.py for the four repeated tube channels of sheet 1.
After each sheet: tools/p2k/bin/p2k render_sheet kicad/NN_*.kicad_sch (look at it next to
hi-N.png), tools/p2k/bin/p2k compare_netlists --allow-missing --sheet N, tools/erc.sh, then
tools/check_all.sh. Target per sheet: 0 missing on that sheet, 0 compare errors, 0 ERC errors
(warnings explained in STATUS.md). After sheet 1: drop --allow-missing in tools/check_all.sh;
done = 72/72 parts, every IPC net complete, 0 wrong-net pins, ERC 0 errors.

Rules (PLAN.md section 5): don't change tools/p2k or its pin (board-local workarounds, noted in
STATUS.md "p2k candidates"); don't touch other repos; report design findings, don't fix them;
temporary files in build/tmp; never run the KiCad AppImage with --version (use tools/p2k/bin/kipy
and tools/p2k/bin/kicad-cli). At the end: STATUS.md updated (per-sheet results, last check output,
findings), next_prompt.md replaced with the Phase 2 (footprints) prompt, commit and push
(git push origin main). If something needs a user decision, stop, record it in STATUS.md,
commit and push, and report it.
```
