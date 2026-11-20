# Next prompt

Ready-to-paste prompt for the next agent session. Replaced at the end of every session.

```
The Proteus -> KiCad 10 conversion in /home/jari/dev/tube_power_amp_kicad is COMPLETE (Phases 0-5,
shared-tool migration p2k a9a286c) and GENERATION HAS STOPPED (user decision 2026-11-20, last
generated state commit 785d209; STATUS.md "Generation stopped 2026-11-20"). The committed KiCad files
(kicad/*.kicad_sch, kicad/tube_power_amp.kicad_pcb, lib/, kicad/fp-lib-table) are the source and are
edited in KiCad. The generators are frozen history in tools/generate/ and refuse to run without
--force-regenerate - never run them on this repo (they would overwrite KiCad edits).
tools/check_all.sh checks the committed files against the Proteus truth and KiCad's rules
(check_symbols, ERC, compare_netlists, check_footprints, check_pin_order, check_board,
assign_nets --check, DRC, ipc356_diff, gerber_roundtrip): ALL CHECKS PASSED.

Read PLAN.md, STATUS.md ("Generation stopped 2026-11-20", "Findings", "Decisions") and
tools/p2k/CONVERSION_PLAYBOOK.md. Run tools/check_all.sh first and compare with STATUS.md "Last check
output".

What remains:
1. Report-only findings (STATUS.md "Findings about the original design"): documentation notes, no
   copper change unless the user asks (Finding 1, the VS' terminal on #00043, was decided "left as
   built" 2026-11-20).
2. The redesign (rev B: ribbon cables, PCB-mount pots, the new power section; the amplifier project
   tube_amplifier_kicad holds the spec). Work in KiCad on the committed files. Every deliberate
   deviation from the Proteus original will make a check fail: record it in p2k_config.py (PENDING /
   accepted items with a reason) and in STATUS.md, never drop a check to hide it. When the design has
   diverged enough that a Proteus comparison is meaningless, decide with the user which checks to
   retire (and record that), keeping ERC, DRC with parity and assign_nets.
3. Optional: DRC_EXPECTED_WARNINGS for the silk warning counts (p2k candidate 25) if the user wants
   cosmetic changes guarded.
Note for proteus2kicad regression runs: use tube_power_amp_kicad@785d209 (HEAD has no generators at
the paths regress.sh expects).
The meta repo tube_amplifier_kicad bumps its submodule (from the meta repo, not here).

Rules (PLAN.md section 5): don't change tools/p2k or its pin; don't touch other repos; never run
the generators or `p2k make_pcb` / `p2k sheets` here; temporary files in build/tmp; never run the
KiCad AppImage with --version. At the end: STATUS.md, README.md status, next_prompt.md replaced,
commit and push (git push origin main).
```
