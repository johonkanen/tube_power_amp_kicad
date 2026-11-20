# Next prompt

Ready-to-paste prompt for the next agent session. Replaced at the end of every session.

```
Convert the Proteus board in /home/jari/dev/tube_power_amp_kicad to KiCad 10: Phase 2
(footprints). Phase 1 is done: 3 sheets, 72/72 parts, netlist identical to the IPC netlist,
ERC 0 errors / 0 warnings.

Read, in this order: PLAN.md, STATUS.md (phase table, "Phase 0" notes for the later phases: pad /
drill families, "Phase 1 transcription", "Findings", "p2k candidates", "Decisions"),
tools/p2k/CONVERSION_PLAYBOOK.md (sections 1, 3 "Phase 2", 5), tools/p2k/README.md (footprints,
check_footprints, config keys FOOTPRINT_PAD_SIZES, OFF_BOARD_PARTS, HOLE_FOOTPRINT),
lib/part_map.csv (device / package columns), reference/ipc356_pads.csv. Run tools/check_all.sh
first and compare with STATUS.md "Last check output" (ALL CHECKS PASSED, compare 72/72).
Example: ~/dev/tube_psu_kicad/tools/gen_footprints.py with its lib/footprint_map.csv and
STATUS.md Phase 2 section (read only; don't change that repo).

Do:
1. p2k_config.py: OFF_BOARD_PARTS = {"OT": ..., "VA_PRIME": ...} (drawn in the PDF, no pads).
2. tools/gen_footprints.py (RULES, PROJECT; p2k.footprints.run) -> lib/footprint_map.csv and
   lib/tube_power_amp.pretty, with --check. One rule per family (Proteus package in
   lib/part_map.csv, pad size / drill in STATUS.md Phase 0 notes):
   - R1-R12, R17-R23 (RES40, 1.778 / 0.762): axial resistor, pitch from the IPC pads;
   - R13-R16 (1K/ 5W WIREWOUND, 2.54 / 1.143) and R24/R25 (2W METAL FILM, 2.286 / 1.016);
   - C1-C4 (22N XICON, film), C5 (RAD ELEC R5 D10), C6 (ELEC-RAD20): pads + / - on C5, C6;
   - D1-D5 (DO41, pads A / K);
   - Q1 (TO220, 1=B 2=C 3=E, square pad 1), Q2/Q3 (TO92, 1=E 2=B 3=C);
   - U6-U9 (8-PIN BELTON OCTAL, 3.81 mm pads, 1.6 mm drill, 8 pads; pin 6 has a pad without a
     net): check the pin ids against the octal pinout (pin 1 next to the key, numbering
     clockwise seen from the solder side) with the unmoved KiCad base footprint fit;
   - the 29 terminals (C-120-60, 3.048 mm pad, 1.524 mm drill, one pad): fly-lead pads;
   - the 4 mounting holes (3.0 mm plated, 6.35 mm pad on both layers): board-only footprint
     (HOLE_FOOTPRINT / HOLE_VALUE).
   Default: KiCad pad sizes with the pad centres on the Proteus positions; where KiCad has
   nothing suitable (terminals, octal socket if the pitch circle differs, 5 W resistor) build
   the footprint from the IPC pads. Pad-size choices that change clearances are a user decision.
3. Re-run the sheet scripts so the Footprint fields are filled from the map (sch_builder reads
   lib/footprint_map.csv); compare and ERC must still pass (project fp-lib-table for ERC).
4. tools/p2k/bin/p2k check_footprints (and tools/p2k/bin/kipy -m p2k.check_footprints --pcbnew):
   every part within 0.05 mm, reports/footprint_fit.csv written. Pin-order check for Q1-Q3,
   D1-D5, C5/C6 and U6-U9 against the unmoved KiCad base footprints; report oddities.
5. Add the steps to tools/check_all.sh (gen_footprints --check, check_footprints); negative-test
   them (move a pad, swap two pad numbers).

This board is the pilot for the 2010 boards: record in STATUS.md what the preamp and PI/FX
conversions can reuse (fly-lead terminal footprint, octal socket footprint and pin ids, THT pad
size families, the 2010 package names -> KiCad footprints table).

Rules (PLAN.md section 5): don't change tools/p2k or its pin (board-local workarounds, noted in
STATUS.md "p2k candidates"); don't touch other repos; report design findings, don't fix them;
temporary files in build/tmp; never run the KiCad AppImage with --version (use tools/p2k/bin/kipy
and tools/p2k/bin/kicad-cli). At the end: STATUS.md updated (results, last check output,
findings, p2k candidates, decisions), README.md status line, next_prompt.md replaced with the
Phase 3 (PCB) prompt, commit and push (git push origin main). If something needs a user decision
(pad sizes, a footprint that does not fit), stop, record it in STATUS.md, commit and push, and
report it.
```
