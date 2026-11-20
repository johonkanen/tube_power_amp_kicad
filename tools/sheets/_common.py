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
    """Proteus TERMINAL / PIN part as sheetkit.terminal does it (connection point (x, y), circle
    pointing in `direction`, texts horizontal), but with the symbol and value of the part map:
    PIN or PIN_OFFBOARD (VA'), value TERMINAL or PIN. sheetkit.terminal always places PIN / "PIN"."""
    rot = {"up": 0, "left": 90, "down": 180, "right": 270}[direction]
    kw = {}
    if direction == "right":     # KiCad mirrors justification for rot 270
        kw = dict(ref_at=(x + 5.08, y - 1.27, 90, "left"), value_at=(x + 5.08, y + 1.27, 90, "left"))
    elif direction == "left":
        kw = dict(ref_at=(x - 5.08, y - 1.27, 270, "right"), value_at=(x - 5.08, y + 1.27, 270, "right"))
    return sh.place(sym(ref), ref, x, y, rot, value=sh_value(ref), **kw)


# --- PDF coordinates ---------------------------------------------------------------------------------
# The Proteus PDF pages rendered at 200 dpi (build/tmp/pdf/hi-N.png) have 0.127 mm pixels, so
# 10 px = one 1.27 mm grid unit. P(px/10, py/10) puts a point of the render on the A3 KiCad sheet
# (same scale, shifted by OX/OY grid units), which keeps the layout close to the PDF.
OX, OY = 40, 30


def P(x, y):
    """Sheet point (mm, on the 1.27 mm grid) of PDF render position (x, y) in units of 10 px."""
    return (g(x + OX), g(y + OY))


# --- mirrored symbols --------------------------------------------------------------------------------
def place_mirrored(sh, name, ref, x, y, axis="x", **kw):
    """sh.place() at rotation 0 with the symbol mirrored: axis 'x' = about the X axis (top and
    bottom swapped), 'y' = about the Y axis (left and right swapped). p2k.sch_builder.Sheet.place has
    no mirror option (p2k candidate), so the node it wrote gets a (mirror ...) entry here and the
    returned pin points are mirrored about the symbol origin. Pass ref_at / value_at for the texts
    (KiCad keeps field positions absolute)."""
    from p2k.sexpr import Sym, find
    p = sh.place(name, ref, x, y, 0, **kw)
    unit = kw.get("unit", 1)
    for node in sh.tree:
        if (isinstance(node, list) and node and str(node[0]) == "symbol" and find(node, "unit")[1] == unit
                and any(c[1:3] == ["Reference", ref] for c in node if isinstance(c, list) and str(c[0]) == "property")):
            node.insert(next(i for i, c in enumerate(node) if isinstance(c, list) and str(c[0]) == "at") + 1,
                        [Sym("mirror"), Sym(axis)])
            break
    else:
        raise KeyError(ref)
    for num, (px, py) in list(p.pins.items()):
        p.pins[num] = (px, round(2 * y - py, 4)) if axis == "x" else (round(2 * x - px, 4), py)
    return p
