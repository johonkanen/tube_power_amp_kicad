#!/usr/bin/env bash
# Builds the rev C board from the schematic, rerunnable: placement -> heater copper -> (next steps).
#   rev_c/tools/layout/build.sh
set -euo pipefail
R="$(cd "$(dirname "$0")/../../.." && pwd)"
KIPY="$R/tools/p2k/bin/kipy"; L="$R/rev_c/tools/layout"
B="$R/rev_c/kicad/tube_power_amp_revc.kicad_pcb"
"$KIPY" "$L/make_pcb.py" "$B" 2>&1 | grep -v "memory leak" | tail -1
"$KIPY" "$L/heater_copper.py" "$B" "$B" 2>&1 | grep -v "memory leak" | tail -1
