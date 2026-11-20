#!/usr/bin/env bash
# Run every verification step. Exit status is non-zero if any step fails.
# The tools are the proteus2kicad submodule in tools/p2k; board values in p2k_config.py.
# Generation stopped 2026-11-20 (STATUS.md): the committed kicad/*.kicad_sch, kicad/*.kicad_pcb
# and lib/ are the source, edited in KiCad. No step regenerates or byte-compares them; every step
# checks the committed files against the Proteus truth (source/, reference/) and KiCad's rules.
# A deliberate deviation from Proteus is recorded in p2k_config.py (PENDING / accepted items with
# a reason), never hidden by dropping a check.
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
# reference/ is derived from the Proteus IPC file only (the truth, not the edited design)
step "IPC-D-356A parser self-check" tools/p2k/bin/p2k ipc356 --check
step "Gerber X2 export vs IPC (pads, holes, drills, outline)" tools/p2k/bin/p2k check_sources
# Phase 1: schematic
step "Symbol pin sets vs IPC" tools/p2k/bin/p2k check_symbols
step "ERC" tools/p2k/bin/p2k erc
# all 3 sheets are drawn: every part must be present (no --allow-missing)
step "Netlist comparison vs IPC" tools/p2k/bin/p2k compare_netlists
# Phase 2: footprints
step "Footprints vs IPC pad geometry" tools/p2k/bin/kipy -m p2k.check_footprints --pcbnew
step "Pin order vs unmoved KiCad base footprints" tools/p2k/bin/kipy -m p2k.check_pin_order
# Phase 3: PCB (the committed board; no pours, no vias on this board)
step "Board pads, holes vs IPC (position, size, nets 1:1)" tools/p2k/bin/kipy -m p2k.check_board
step "Board copper connectivity (KiCad geometry)" tools/p2k/bin/kipy -m p2k.assign_nets --check
step "DRC with schematic parity" tools/p2k/bin/p2k drc
# Phase 4: independent verification (KiCad's own exports vs the Proteus files; C1-C6 smaller
# drills accepted per pad set in DRILL_SMALLER, the 2010 inch Excellon file read natively)
step "IPC-D-356 from the board vs Proteus (pads, holes, nets)" tools/p2k/bin/p2k ipc356_diff
step "Gerber round trip vs Proteus (copper XOR, coverage, drills, 2010 Excellon)" tools/p2k/bin/p2k gerber_roundtrip --check

echo
pending=$(grep -c "PENDING USER DECISION" "$log")
if [ $fail -ne 0 ]; then echo "SOME CHECKS FAILED"
elif [ "$pending" -ne 0 ]; then echo "ALL CHECKS PASSED, EXCEPT $pending PENDING USER DECISION(S):"; grep "PENDING USER DECISION" "$log" | sed 's/^/  /'
else echo "ALL CHECKS PASSED"; fi
exit $fail
