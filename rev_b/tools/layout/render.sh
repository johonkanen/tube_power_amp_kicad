#!/usr/bin/env bash
# Renders of the power amp rev B board (STATUS "Layout, first pass").
#   rev_b/tools/layout/render.sh BOARD.kicad_pcb OUTDIR [DPI] [NAMES]
# 2D plots are KiCad F views (= the chassis plan mirrored left-right: east end on the left), cropped to the
# board (KiCad x 98-343, y 58-127 on the A3 sheet). NAMES: any of placement top bottom in1 in2 3d (default all).
set -euo pipefail
B="$1"; O="$2"; DPI="${3:-300}"; NAMES="${4:-placement top bottom in1 in2 3d}"
R="$(cd "$(dirname "$0")/../../.." && pwd)"
CLI="$R/tools/p2k/bin/kicad-cli"
mkdir -p "$O"
px() { python3 -c "print(int(round(($1) / 25.4 * $DPI)))"; }
CX=$(px 98); CY=$(px 58); CW=$(px 245); CH=$(px 69)
plot() {   # name layers [extra]
    "$CLI" pcb export pdf --layers "$2" --mode-single --drill-shape-opt 2 ${3:-} -o "$O/$1.pdf" "$B" > /dev/null
    pdftoppm -r "$DPI" -x "$CX" -y "$CY" -W "$CW" -H "$CH" -png -singlefile "$O/$1.pdf" "$O/$1"
    rm -f "$O/$1.pdf"; echo "$O/$1.png"
}
for n in $NAMES; do
  case $n in
    placement) plot placement "F.Fab,F.Courtyard,B.Courtyard,Edge.Cuts,Dwgs.User,Cmts.User,F.Cu,B.Fab" ;;
    top) plot top "F.Cu,F.Silkscreen,Edge.Cuts" ;;
    bottom) plot bottom "B.Cu,B.Silkscreen,Edge.Cuts" ;;
    in1) plot in1 "In1.Cu,Edge.Cuts" ;;
    in2) plot in2 "In2.Cu,Edge.Cuts" ;;
    3d)
      "$CLI" pcb render --side bottom --quality high --width 3200 --height 1100 --zoom 1.0 -o "$O/3d_bottom.png" "$B" > /dev/null && echo "$O/3d_bottom.png"
      "$CLI" pcb render --side top --quality high --width 3200 --height 1100 --zoom 1.0 -o "$O/3d_top.png" "$B" > /dev/null && echo "$O/3d_top.png"
      "$CLI" pcb render --rotate "-60,0,20" --perspective --quality high --width 3000 --height 1600 --zoom 0.9 -o "$O/3d_iso.png" "$B" > /dev/null && echo "$O/3d_iso.png" ;;
  esac
done
