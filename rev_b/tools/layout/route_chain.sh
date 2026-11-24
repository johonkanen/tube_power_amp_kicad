#!/usr/bin/env bash
# Routing chain of the power amp rev B: placed board -> rev_b/kicad/tube_power_amp_revb.kicad_pcb, rerunnable.
#   rev_b/tools/layout/route_chain.sh [LAST_STEP]
# Steps (STATUS "Layout, first pass"): placement (make_pcb.py) -> scripted HV / heater / grid copper
# (hv_copper.py), locked -> KiCadRoutingTools steps by net group, each locked when done -> pours (pours.py)
# -> ground / supply stubs -> refill -> unlock -> fab fixes. Work files: build/layout/NN_step.kicad_pcb.
# Needs ~/dev/KiCadRoutingTools (with its .venv) and the kicad-agentic-routing skill's scripts.
set -euo pipefail
R="$(cd "$(dirname "$0")/../../.." && pwd)"
SK="${ROUTING_SKILL:-$HOME/.claude/skills/kicad-agentic-routing/scripts}"
source "$R/tools/p2k/bin/kicad_env.sh" > /dev/null
export KICAD_PYTHON="$KICAD_MOUNT/bin/python3.11" KICAD_CLI="$R/tools/p2k/bin/kicad-cli"
source "$SK/kenv.sh"
export ROUTING_CONFIG="$R/rev_b/routing.json"
LAST="${1:-}"
W="$R/build/layout"; mkdir -p "$W"
OUT="$R/rev_b/kicad/tube_power_amp_revb.kicad_pcb"
KIPY="$R/tools/p2k/bin/kipy"
L="$R/rev_b/tools/layout"
proj() { for x in kicad_pro kicad_dru; do cp "$R/rev_b/kicad/tube_power_amp_revb.$x" "${1%.kicad_pcb}.$x"; done; }

"$KIPY" "$L/make_pcb.py" "$W/00_placed.kicad_pcb" 2>&1 | grep -v "memory leak" | tail -1
"$KIPY" "$L/hv_copper.py" "$W/00_placed.kicad_pcb" "$W/01_hv.kicad_pcb" 2>&1 | grep -v "memory leak" | tail -1
proj "$W/01_hv.kicad_pcb"
kpy "$SK/lock_tracks.py" "$W/01_hv.kicad_pcb" lock-all | tail -1
[ "$LAST" = "hv" ] && exit 0
N=1; CUR="$W/01_hv.kicad_pcb"
step() {    # step NAME GROUPS [route.py options]
    N=$((N + 1)); local out="$W/$(printf %02d "$N")_$1.kicad_pcb"
    echo "== $1"
    python3 -I "$SK/route_step.py" "$CUR" "$out" "${@:2}" 2>&1 | cut -c1-600
    CUR="$out"
    kpy "$SK/lock_tracks.py" "$CUR" lock-all | tail -1
    if [ "$LAST" = "$1" ]; then echo "stopped after $1: $CUR"; exit 0; fi
}
step supply supply --power-nets '+5V' '+15V' '-15V' --power-nets-widths 0.4 0.4 0.4
step kelvin kelvin --track-width 0.3
step sense sense
step bias bias
step ref ref
step digital digital
python3 "$L/rest_group.py" "$CUR" "$ROUTING_CONFIG"
step rest rest --layers F.Cu In2.Cu B.Cu In1.Cu --layer-costs 1 1 2 6
# pours (GND / GNDD on all layers, the DGND island), fill, then ground stubs for the pads the pours missed
N=$((N + 1)); P="$W/$(printf %02d "$N")_pour.kicad_pcb"
"$KIPY" "$L/pours.py" "$CUR" "$P" 2>&1 | grep -v "memory leak" | tail -1; CUR="$P"; proj "$CUR"
[ "$LAST" = "pour" ] && { echo "stopped after pour: $CUR"; exit 0; }
step grounds grounds --power-nets 'GND' 'GNDD' --power-nets-widths 0.4 0.4 --layer-costs 1 1 1
N=$((N + 1)); P="$W/$(printf %02d "$N")_refill.kicad_pcb"
kpy "$SK/fill_zones.py" "$CUR" "$P" | tail -1; CUR="$P"; proj "$CUR"
kpy "$SK/lock_tracks.py" "$CUR" unlock | tail -1
kpy "$SK/fab_fixes.py" "$CUR" "$OUT" --no-fiducials | tail -3
python3 - "$OUT" <<'EOF'
import sys
p = sys.argv[1]; t = open(p).read()
open(p, "w").write(t.replace('(paper "A4")', '(paper "A3")', 1))
EOF
echo "wrote $OUT"
