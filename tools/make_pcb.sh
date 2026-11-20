#!/usr/bin/env bash
# Phase 3: rebuild the board (p2k make_pcb, default PCB_STEPS; --check = byte compare). Kept as a
# file because the proteus2kicad regression harness calls tools/make_pcb.sh.
exec tools/p2k/bin/p2k make_pcb "$@"
