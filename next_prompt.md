# Next prompt

Ready-to-paste prompt for the next agent session. Replaced at the end of every session.

```
Convert the Proteus board in /home/jari/dev/tube_power_amp_kicad to KiCad 10: Phase 3 (PCB).
Phases 0-2 are done: 3 sheets, 72/72 parts, netlist identical to the IPC netlist, ERC 0/0;
every footprint fits the IPC pads (worst residual 0.001 mm, reports/footprint_fit.csv).

Read, in this order: PLAN.md, STATUS.md (phase table, "Phase 2" incl. the pad size / drill
differences and the pin-order table, "Findings" 10 (octal socket side, open user question),
"p2k candidates", "Decisions"), tools/p2k/CONVERSION_PLAYBOOK.md (sections 1, 3 "Phase 3", 5),
tools/p2k/README.md (pcb, build_pcb, gerber_to_tracks, assign_nets, check_board, drc; config keys
PCB_RULES, PCB_THICKNESS, HOLE_FOOTPRINT / HOLE_VALUE, DRC_ACCEPTED). Run tools/check_all.sh first
and compare with STATUS.md "Last check output" (ALL CHECKS PASSED).
Example: ~/dev/tube_psu_kicad/tools/make_pcb.sh, tools/measure_gaps.py, its p2k_config.py
(PCB_RULES, DRC_ACCEPTED) and STATUS.md Phase 3 section (read only; don't change that repo).

Board facts (PLAN.md section 1): 2 copper layers (Top 158 / Bottom 96 conductor draws, widths
0.508-2.54 mm), no pours, no vias, no free pads, 4 plated 3.0 mm mounting holes with 6.35 mm pads
(HOLE_FOOTPRINT is set), outline 238.76 x 60.325 mm, all parts THT on top.

Do:
1. Measure the smallest Proteus gaps (track-track, track-pad, pad-pad, to the edge) and fill
   PCB_RULES and PCB_THICKNESS in p2k_config.py (the 2010 board thickness: 1.6 mm unless the
   sources say otherwise).
2. tools/make_pcb.sh (as tube_psu, minus the pour steps: build_pcb, gerber_to_tracks,
   assign_nets; no pours_to_zones) -> kicad/tube_power_amp.kicad_pcb, with --check (rebuild in
   build/tmp, byte compare).
3. assign_nets: 0 shorts / 0 orphans / 0 opens; check_board passes (pads, holes, nets 1:1).
4. DRC with schematic parity (p2k drc): 0 shorts, 0 unconnected, 0 parity. Expect clearance
   items where KiCad pads differ from Proteus: R24/R25 KiCad pads are 0.114 mm larger (2.4 vs
   2.286); everything else is smaller. List the remaining DRC items with reasons
   (DRC_ACCEPTED). If DRC forces Proteus pad sizes or drills on some parts, that is a user
   decision: stop, record the per-refdes conflicts in STATUS.md, commit, push and report.
5. Add the steps to tools/check_all.sh (make_pcb.sh --check, check_board, assign_nets --check,
   drc) and negative-test them (move a track, change a net).

Open user questions (do not decide them): the octal socket side (STATUS.md Findings 10; the
footprint keeps the Proteus ids on the top side); C1-C6 KiCad drills 1.0 vs Proteus 1.143 mm
(Phase 4 DRILL_SMALLER or Proteus drills).

Rules (PLAN.md section 5): don't change tools/p2k or its pin (board-local workarounds, noted in
STATUS.md "p2k candidates"); don't touch other repos; report design findings, don't fix them;
temporary files in build/tmp; never run the KiCad AppImage with --version (use tools/p2k/bin/kipy
and tools/p2k/bin/kicad-cli). At the end: STATUS.md updated (results, last check output,
findings, p2k candidates, decisions), README.md status line, next_prompt.md replaced with the
Phase 4 (verification) prompt, commit and push (git push origin main).
```
