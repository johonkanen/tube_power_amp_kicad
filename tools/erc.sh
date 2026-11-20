#!/usr/bin/env bash
# ERC of the project schematic; fails on ERC errors (warnings are listed only), and on the
# warning no_connect_connected (a pin with a no-connect flag, or of the no_connect type, that is
# wired: KiCad's default severity is "warning", but for this conversion it is a netlist error).
# Full report: reports/erc.rpt
set -u
cd "$(dirname "$0")/.."
mkdir -p reports
tools/p2k/bin/kicad-cli sch erc --severity-all -o reports/erc.rpt kicad/tube_power_amp.kicad_sch >/dev/null || exit 1
errs=$(grep -c '; error' reports/erc.rpt)
warns=$(grep -c '; warning' reports/erc.rpt)
echo "erc: $errs errors, $warns warnings (reports/erc.rpt)"
ncc=$(grep -c '^\[no_connect_connected\]' reports/erc.rpt)
[ "$ncc" -eq 0 ] || { echo "erc: $ncc no_connect_connected (a no-connect pin is wired):"; grep -A3 '^\[no_connect_connected\]' reports/erc.rpt; }
[ "$errs" -eq 0 ] && [ "$ncc" -eq 0 ]
