# Next prompt

Ready-to-paste prompt for the next agent session. Replaced at the end of every session.

```
The Proteus -> KiCad 10 conversion in /home/jari/dev/tube_power_amp_kicad is COMPLETE (Phases 0-5)
and migrated to the shared proteus2kicad tools (p2k a9a286c, STATUS.md "Shared-tool migration
2026-11-20"): the board scripts are data for p2k (make_part_map.py, gen_symbols.py, gen_footprints.py,
the sheet scripts; tools/make_pcb.sh = exec tools/p2k/bin/p2k make_pcb "$@"); ERC, pin order and the
Phase 4 checks are p2k tools driven by p2k_config.py (ERC_FATAL_WARNINGS, PIN_ORDER,
PIN_ORDER_BOTTOM, BOTTOM_THT, DRILL_SMALLER pad set, DRILL_EXCELLON = the 2010 inch file). No strict
opt-outs. tools/check_all.sh: ALL CHECKS PASSED; ~/dev/proteus2kicad/tools/regress.sh a9a286c
tube_power_amp_kicad: PASS.

Read PLAN.md, STATUS.md ("Shared-tool migration", "Phase 5", "Findings", "Decisions") and
tools/p2k/CONVERSION_PLAYBOOK.md. Run tools/check_all.sh first and compare with STATUS.md "Last check
output".

What remains is for the user (ask, don't decide):
1. Stop generating the board from Proteus (playbook: the first manual layout change in KiCad). When
   the user starts editing the board by hand: remove the `make_pcb.sh --check` step from
   tools/check_all.sh, say so in STATUS.md, record intended differences as deviations
   (check_board / assign_nets / DRC / ipc356_diff / gerber_roundtrip keep working on the edited
   board), and consider DRC_EXPECTED_WARNINGS for the silk counts (STATUS.md p2k candidate 25).
2. Findings 1: the `VS'` terminal (sheet 2, R19) is on net #00043, not on the net VS' (STANDBY,
   R13-R16): confirm against the amplifier wiring (report only; the conversion reproduces Proteus).
The meta repo tube_amplifier_kicad bumps its submodule (from the meta repo, not here).

Rules (PLAN.md section 5): don't change tools/p2k or its pin; don't touch other repos; report design
findings, don't fix them; generate, don't hand-edit while the board is generated; temporary files in
build/tmp; never run the KiCad AppImage with --version. At the end: STATUS.md, README.md status line,
next_prompt.md replaced, commit and push (git push origin main).
```
