#!/usr/bin/env bash
# Run every verification step. Exit status is non-zero if any step fails.
# Each phase adds its steps here (playbook principle 5, PLAN.md section 3).
# The tools are the proteus2kicad submodule in tools/p2k; board values in p2k_config.py.
set -u
cd "$(dirname "$0")/.."
[ -x tools/p2k/bin/p2k ] || { echo "tools/p2k missing: git submodule update --init"; exit 1; }
fail=0
mkdir -p build/tmp
log=build/tmp/check_all.log; : > "$log"
step() {
    echo "== $1" | tee -a "$log"; shift
    "$@" 2>&1 | tee -a "$log"
    [ "${PIPESTATUS[0]}" -eq 0 ] || { echo "!! FAILED: $*" | tee -a "$log"; fail=1; }
}

step "KiCad environment" tools/p2k/bin/kipy -c "import pcbnew; v = pcbnew.GetBuildVersion(); print('pcbnew', v); assert v.startswith('10.0.7'), v"
step "IPC-D-356A parser self-check" tools/p2k/bin/p2k ipc356 --check
step "Gerber X2 export vs IPC (pads, holes, drills, outline)" tools/p2k/bin/p2k check_sources
# Phase 1: schematic
step "Part map up to date" python3 tools/make_part_map.py --check
step "Symbol library up to date" python3 tools/gen_symbols.py --check
step "Symbol pin sets vs IPC" tools/p2k/bin/p2k check_symbols
step "ERC" tools/erc.sh
# all 3 sheets are drawn: every part must be present (no --allow-missing)
step "Netlist comparison vs IPC" tools/p2k/bin/p2k compare_netlists
# Phase 2: footprints
step "Footprint library, map and fp-lib-table up to date" python3 tools/gen_footprints.py --check
step "Footprints vs IPC pad geometry" tools/p2k/bin/kipy -m p2k.check_footprints --pcbnew
step "Pin order vs unmoved KiCad base footprints" tools/p2k/bin/kipy tools/check_pin_order.py
# Phase 3: PCB (build_pcb, gerber_to_tracks, assign_nets; no pours, no vias on this board)
step "PCB rebuilt from schematic + gerbers, up to date" tools/make_pcb.sh --check
step "Board pads, holes vs IPC (position, size, nets 1:1)" tools/p2k/bin/kipy -m p2k.check_board
step "Board copper connectivity (KiCad geometry)" tools/p2k/bin/kipy -m p2k.assign_nets --check
step "DRC with schematic parity" tools/p2k/bin/p2k drc
# Phase 4: independent verification (KiCad's own exports vs the Proteus files). Both tools run
# through tools/phase4_checks.py while the C1-C6 drill question is open (STATUS.md "Decisions"):
# it passes only if the 12 C1-C6 drill errors are the tool's only errors.
step "2010 Excellon drill file converted to metric, up to date" python3 tools/excellon_metric.py --check
step "IPC-D-356 from the board vs Proteus (pads, holes, nets)" python3 tools/phase4_checks.py ipc356_diff
step "Gerber round trip vs Proteus (copper XOR, coverage, drills, 2010 Excellon)" python3 tools/phase4_checks.py gerber_roundtrip

echo
pending=$(grep -c "PENDING USER DECISION" "$log")
if [ $fail -ne 0 ]; then echo "SOME CHECKS FAILED"
elif [ "$pending" -ne 0 ]; then echo "ALL CHECKS PASSED, EXCEPT $pending PENDING USER DECISION(S):"; grep "PENDING USER DECISION" "$log" | sed 's/^/  /'
else echo "ALL CHECKS PASSED"; fi
exit $fail
