# Next prompt

Ready-to-paste prompt for the next agent session. Replaced at the end of every session.

```
Convert the Proteus board in /home/jari/dev/tube_power_amp_kicad to KiCad 10: Phase 1 preparation
(part map, symbols, skeleton, checks). Do not transcribe sheets yet.

Read, in this order: PLAN.md, STATUS.md (Phase 0 result, its notes for Phase 1, p2k candidates),
tools/p2k/CONVERSION_PLAYBOOK.md (sections 1, 3 "Phase 1", 4 and 5), tools/p2k/README.md
(lib/part_map.csv format, symgen, sheetkit, make_skeleton, check_symbols, compare_netlists).
Run tools/check_all.sh first and compare with STATUS.md "Last check output". The finished
reference is ~/dev/tube_psu_kicad (same tools): read its tools/make_part_map.py,
tools/gen_symbols.py, tools/erc.sh, tools/check_all.sh and STATUS.md "Phase 1" (preparation,
transcription rules). Read it only; don't change it.

Re-render the PDF pages first (pdftoppm -r 200 -png source/schematic_pdf/OUTPUT.PDF
build/tmp/pdf/hi) and read them.

Do the Phase 1 preparation as the playbook describes:
- tools/make_part_map.py -> lib/part_map.csv (KiCad refdes from reference/ipc356_pads.json, sheet,
  lib_id, value; values from p2k.pdsprj.dsn_values with the FULL refdes set incl. OT and VA';
  C5 = 10µ/400V from the PDF because pdsprj drops the Latin-1 µ (STATUS.md p2k candidate 1);
  OT and VA' are drawn in the PDF but not on the board: mark them, they need OFF_BOARD_PARTS in
  Phase 2); --check;
- tools/gen_symbols.py -> lib/tube_power_amp.kicad_sym (KiCad std symbols renumbered to the IPC
  pin ids: EL34 octal 1-8 with pin 6 unconnected, Q1 TIPL760 1=B 2=C 3=E, Q2/Q3 MPSA92 1=E 2=B
  3=C (confirm against the Proteus pinouts, p2k.pdsprj.dsn_pinouts), diodes A/K, C5/C6 +/-;
  single-pin connector symbol for the 29 terminals); --check;
- tools/p2k/bin/p2k make_skeleton (sheet names from p2k_config.py SHEETS), tools/erc.sh;
- add part map, symbols, check_symbols, ERC and compare_netlists --allow-missing to
  tools/check_all.sh and make it pass;
- write the transcription rules into STATUS.md (IPC net spelling incl. 'HT +6', "VS'", 'B-',
  'OTGND' (sheet 3 'otgnd' is the same net), terminal refdes vs net names (STATUS.md Phase 0
  notes), the no-net pin 6 of U6-U9, global labels for nets on several sheets, grid 1.27 mm).

Rules (PLAN.md section 5): don't change tools/p2k or its pin (board-local workarounds, noted in
STATUS.md "p2k candidates"); don't touch other repos; report design findings, don't fix them;
temporary files in build/tmp; never run the KiCad AppImage with --version (use tools/p2k/bin/kipy
and tools/p2k/bin/kicad-cli). At the end: STATUS.md updated (result, check output, findings),
next_prompt.md replaced with the prompt for the transcription session, commit and push
(git push origin main).
```
