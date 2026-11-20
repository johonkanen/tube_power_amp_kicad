#!/usr/bin/env bash
# FROZEN HISTORY (generation stopped 2026-11-20, STATUS.md "Generation stopped 2026-11-20").
# Rebuilt kicad/tube_power_amp.kicad_pcb from the schematic + Proteus gerbers (p2k make_pcb,
# default PCB_STEPS; --check = byte compare). The committed board is now the source and is edited
# in KiCad: rebuilding it would throw those edits away. Refuses to run without --force-regenerate
# (use that only in a scratch clone, e.g. to reproduce the board at commit 785d209).
cd "$(dirname "$0")/../.."
force=0; args=()
for a in "$@"; do
    if [ "$a" = "--force-regenerate" ]; then force=1; else args+=("$a"); fi
done
if [ $force -ne 1 ]; then
    echo "make_pcb.sh: FROZEN - the board is edited in KiCad now; regenerating would overwrite it." >&2
    echo "  Pass --force-regenerate only in a scratch clone (STATUS.md 'Generation stopped 2026-11-20')." >&2
    exit 2
fi
exec tools/p2k/bin/p2k make_pcb "${args[@]}"
