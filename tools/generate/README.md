# tools/generate: frozen generators (do not run)

Generation of this board from the Proteus data stopped on 2026-11-20 (user decision, STATUS.md
"Decisions" and "Generation stopped 2026-11-20"; last generated state = commit 785d209). Since then
the committed KiCad files (`kicad/*.kicad_sch`, `kicad/*.kicad_pcb`, `lib/`) are the source and are
edited in KiCad.

These scripts produced those files and are kept as history only:

| Script | Wrote |
|---|---|
| `make_part_map.py` | `lib/part_map.csv` |
| `gen_symbols.py` | `lib/tube_power_amp.kicad_sym` |
| `sheets/sheet0N.py` (+ `_common.py`) | `kicad/*.kicad_sch` (the three sheets) |
| `gen_footprints.py` | `lib/tube_power_amp.pretty/`, `lib/footprint_map.csv`, `kicad/fp-lib-table` |
| `make_pcb.sh` | `kicad/tube_power_amp.kicad_pcb` |

**Running any of them overwrites KiCad edits.** Each refuses to run unless given
`--force-regenerate`; use that only in a scratch clone (e.g. to reproduce the 785d209 output).
Note that `tools/p2k/bin/p2k make_pcb` / `p2k sheets` called directly are not guarded - don't.

`gen_footprints.py` stays importable: `p2k check_pin_order` reads its `RULES` / `PROJECT`
(`FOOTPRINT_SCRIPT` in `p2k_config.py`); importing it does not write anything.
