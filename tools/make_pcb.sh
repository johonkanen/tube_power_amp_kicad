#!/usr/bin/env bash
# Phase 3: rebuild kicad/tube_power_amp.kicad_pcb from the schematic and the Proteus gerbers
# (shared tools in tools/p2k, board values in p2k_config.py). Re-runnable; two runs give a
# byte-identical board (UUIDs seeded per step). As ~/dev/tube_psu_kicad/tools/make_pcb.sh, minus
# the pour steps (this board has no pours) and the Phase 5 steps:
#   1 build_pcb         footprints with nets at the Proteus positions, rules, outline, holes H1-H4
#   2 gerber_to_tracks  copper gerbers -> tracks (no vias, no pours on this board)
#   3 assign_nets       nets of the tracks by copper connectivity (shorts / orphans / opens)
# Board-only footprints (holes) and the footprint fit come from tools/gen_footprints.py and
# p2k.check_footprints (reports/footprint_fit.csv) - run those first after footprint changes.
#
#   tools/make_pcb.sh           rebuild the board in place
#   tools/make_pcb.sh --check   rebuild into build/tmp/make_pcb_check and fail unless the board and
#                               reports/pour_nets.json equal the committed ones byte for byte
#                               (and reports/assign_nets.txt stages A/B)
set -eu
cd "$(dirname "$0")/.."
K=tools/p2k/bin/kipy
PCB=kicad/tube_power_amp.kicad_pcb
run() {
    $K -m p2k.build_pcb
    $K -m p2k.gerber_to_tracks
    $K -m p2k.assign_nets
}
if [ "${1:-}" = "--check" ]; then
    tmp="$PWD/build/tmp/make_pcb_check"
    rm -rf "$tmp"; mkdir -p "$tmp/reports"; trap 'rm -rf "$tmp"' EXIT
    cp reports/footprint_fit.csv "$tmp/reports/"
    cp kicad/tube_power_amp.kicad_pro "$tmp/"   # pcbnew loads the project next to the board (affects the UUID sequence)
    export P2K_PCB="$tmp/tube_power_amp.kicad_pcb" P2K_REPORTS="$tmp/reports"
    run >"$tmp/log" 2>&1 || { cat "$tmp/log"; echo "make_pcb: FAILED"; exit 1; }
    ok=1
    cmp -s "$P2K_PCB" "$PCB" || { echo "make_pcb: $PCB is not up to date (run tools/make_pcb.sh)"; ok=0; }
    # assign_nets --check (check_all.sh) appends its own section to the report: compare stages A/B only
    stages() { sed '/^== after zone fill/,$d' "$1"; }
    [ "$(stages "$tmp/reports/assign_nets.txt")" = "$(stages reports/assign_nets.txt)" ] || { echo "make_pcb: reports/assign_nets.txt is not up to date"; ok=0; }
    cmp -s "$tmp/reports/pour_nets.json" reports/pour_nets.json || { echo "make_pcb: reports/pour_nets.json is not up to date"; ok=0; }
    grep -E "^(build_pcb|gerber_to_tracks: [0-9]|assign_nets: stage)" "$tmp/log" | sed "/^build_pcb/s/ -> .*//"
    [ $ok -eq 1 ] && echo "make_pcb: board rebuilt from scratch, byte-identical" || exit 1
else
    run
fi
