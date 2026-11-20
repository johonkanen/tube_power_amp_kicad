"""Helpers for the per-sheet transcription scripts (tools/sheets/sheetNN.py).

The generic helpers come from p2k.sheetkit (grid g(), sheet(), left/right/up/down,
glabel_*/label_*, power_at, bus_group, flagged_power, vert2, horiz2, terminal); board helpers
below. Each sheet script starts with
    from _common import *  # noqa: F401,F403
"""
import csv
import os
import sys

TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(TOOLS, "p2k"))  # proteus2kicad
from p2k.sch_builder import Sheet  # noqa: E402,F401
from p2k.sheetkit import *  # noqa: E402,F401,F403
from p2k.sheetkit import _two_pin_rot  # noqa: E402

_PART_MAP = None


def part(ref):
    """Row of lib/part_map.csv for a KiCad refdes (keys refdes, sheet, lib_id, value, ...)."""
    global _PART_MAP
    if _PART_MAP is None:
        with open(os.path.join(os.path.dirname(TOOLS), "lib", "part_map.csv"), newline="", encoding="utf-8") as f:
            _PART_MAP = {r["refdes"]: r for r in csv.DictReader(l for l in f if not l.startswith("#"))}
    return _PART_MAP[ref]


def sh_value(ref):
    """Value of a refdes from lib/part_map.csv."""
    return part(ref)["value"]


def sym(ref):
    """Symbol name (lib_id without the library nickname) of a refdes from lib/part_map.csv."""
    return part(ref)["lib_id"].partition(":")[2]


def term(sh, ref, x, y, direction="up"):
    """Proteus TERMINAL / PIN part: sheetkit.terminal with the symbol (PIN or PIN_OFFBOARD) and
    value (TERMINAL or PIN) of the part map, texts beside the circle away from the wire."""
    return terminal(sh, ref, x, y, direction, symbol=sym(ref), value=sh_value(ref), justify="away")


# --- PDF coordinates ---------------------------------------------------------------------------------
# The Proteus PDF pages rendered at 200 dpi (build/tmp/pdf/hi-N.png) have 0.127 mm pixels, so
# 10 px = one 1.27 mm grid unit. P(px/10, py/10) puts a point of the render on the A3 KiCad sheet
# (same scale, shifted by OX/OY grid units), which keeps the layout close to the PDF.
OX, OY = 40, 30


def P(x, y):
    """Sheet point (mm, on the 1.27 mm grid) of PDF render position (x, y) in units of 10 px."""
    return (g(x + OX), g(y + OY))


# --- sheet 1: one output tube channel ----------------------------------------------------------------
def tube_channel(sh, tube, cap, rgrid, rbias, bias, rk, vb, rscreen, cy, by, xj, xjog, xk, xvb, vb_left=False):
    """One of the four EL34 channels of sheet 1, in PDF units (P()): coupling capacitor `cap` on row
    cy, grid-stop resistor `rgrid` to G1 (pin 5), bias resistor `rbias` from the terminal `bias`
    (row by) to the capacitor / grid-stop node at x = xj, the grid wire jogging at x = xjog; the
    tube `tube` (unit 1) at (107, cy + 2); cathode K (pin 8) joined with G3 (pin 1), 1R cathode
    resistor `rk` (centre x = xk) and sense terminal `vb` at x = xvb (below the cathode row, or to
    the left of it with vb_left); screen resistor `rscreen` on G2 (pin 4). Pin 6 (passive,
    no net in Proteus) is returned as 'nc': the sheet script puts a no-connect flag on it (at the
    end of the script, so the UUID sequence of everything else stays as it was). The heater (unit 2) is placed by the sheet script.
    Returns the open ends: 'in' (capacitor pin 1), 'gnd' (cathode resistor pin 2), 'anode'
    (pin 3), 'vs' (screen resistor pin 2), 'nc' (pin 6)."""
    tx, ty = 107, cy + 2
    row = ty + 10                                   # cathode row
    u = sh.place(sym(tube), tube, *P(tx, ty), value=sh_value(tube))
    # input: coupling capacitor, bias feed, grid stop
    cx, ccy = P(26, cy)                             # texts clear of the plates: refdes above, value below
    fa = {0: 0, 90: 270, 180: 0, 270: 90}[_two_pin_rot(sym(cap), 1, "left")]
    _, c1, c2 = horiz2(sh, sym(cap), cap, cx, ccy, sh_value(cap), left=1,
                       ref_at=(cx, ccy - g(3), fa, None), value_at=(cx, ccy + g(3), fa, None))
    _, g1, g2 = horiz2(sh, sym(rgrid), rgrid, *P(xj + 7, cy), sh_value(rgrid), left=1)
    sh.wire(c2, g1)
    term(sh, bias, *P(27, by), "left")
    _, b1, b2 = horiz2(sh, sym(rbias), rbias, *P(34, by), sh_value(rbias), left=1)
    sh.wire(P(27, by), b1)
    sh.wire(b2, P(xj, by), P(xj, cy))
    sh.junction(*P(xj, cy))
    sh.wire(g2, P(xjog, cy), P(xjog, ty + 1), u.pin(5))
    # cathode = G3, cathode resistor, sense terminal
    sh.wire(u.pin(1), P(tx + 9, ty - 3), P(tx + 9, row), P(tx - 2, row))
    sh.wire(u.pin(8), P(tx - 2, row))
    sh.junction(*P(tx - 2, row))
    _, k2, k1 = horiz2(sh, sym(rk), rk, *P(xk, row), sh_value(rk), left=2)
    sh.wire(P(tx - 2, row), k1)
    sh.junction(*P(xvb, row))
    if vb_left:
        term(sh, vb, *P(xvb - 4, row + 6), "left")
        sh.wire(P(xvb - 4, row + 6), P(xvb, row + 6), P(xvb, row))
    else:
        term(sh, vb, *P(xvb, row + 4), "down")
        sh.wire(P(xvb, row), P(xvb, row + 4))
    # screen resistor
    _, s1, s2 = horiz2(sh, sym(rscreen), rscreen, *P(122, ty - 1), sh_value(rscreen), left=1)
    sh.wire(u.pin(4), s1)
    return {"in": c1, "gnd": k2, "anode": u.pin(3), "vs": s2, "nc": u.pin(6)}
