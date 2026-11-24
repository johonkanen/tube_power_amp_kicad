#!/usr/bin/env bash
# DRC (zones refilled, all severities) + schematic parity of a board, run as the project's board
# (rev_b/kicad, so the .kicad_pro net classes and the .kicad_dru rules apply). JSON + summary.
#   rev_b/tools/layout/check.sh BOARD.kicad_pcb [OUTDIR]
set -euo pipefail
R="$(cd "$(dirname "$0")/../../.." && pwd)"
B="$(realpath "$1")"; O="${2:-$R/build/check}"; mkdir -p "$O"
K="$R/rev_b/kicad"; T="$K/tube_power_amp_revb.kicad_pcb"
[ "$B" = "$T" ] || cp "$B" "$T"
"$R/tools/p2k/bin/kicad-cli" pcb drc --refill-zones --severity-all --schematic-parity --format json \
    -o "$O/drc.json" "$T" > "$O/drc.log" 2>&1 || true
python3 - "$O/drc.json" <<'P'
import json, sys, collections
d = json.load(open(sys.argv[1]))
for key in ("violations", "unconnected_items", "schematic_parity"):
    items = d.get(key, [])
    c = collections.Counter((i.get("severity"), i.get("type")) for i in items)
    print(f"{key}: {len(items)}", dict(c) if c else "")
P
