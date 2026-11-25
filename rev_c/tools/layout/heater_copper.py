#!/usr/bin/env python3
"""Power amp rev C: the heater copper (HTR1 / HTR2, floating, up to 1.6 A per tube, 6.4 A in all).

    tools/p2k/bin/kipy rev_c/tools/layout/heater_copper.py IN.kicad_pcb OUT.kicad_pcb

J103 (6.3 mm tabs, between V2 and V3) feeds both halves, so each side carries 3.2 A as far as its first
socket and 1.6 A after it. Pins: 2 = HTR1 at the front of each pin circle, 7 = HTR2 at the rear-west.

- HTR2: a pour on B along the rear band (y 179.5 to the edge), behind the sockets. Pins 7 sit in it, and a
  finger runs down to J103's HTR2 tab. The narrowest part is behind pin 6: about 4 mm of 1 oz outer copper,
  where 3.2 A needs about 1.5 mm for 10 K (IPC-2221).
- HTR1: the same pour on In1 AND In2 (in parallel, stacked under HTR2: a tight pair), with a finger to J103's
  HTR1 tab. Each pin 2 is reached by an inner spur on both layers, through the middle of its own pin circle
  and out at the rear between pins 5 and 6. Narrowest part 4 mm of 2 x inner copper (2 x 0.5 oz = 1 oz,
  internal: about 4 mm for 3.2 A at 10 K); spurs 1.8 mm on two layers for 1.6 A. Order the board with 1 oz
  inner copper for margin.
- Nothing heater-related goes in front of the sockets. Every front-band signal has to cross the plate
  lanes' via-free band there, on F.
- The pours connect solid to the heater pins (1.6 A per pin), and they have priority over the later
  GND pours.
"""
import math
import os
import sys

import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import layout_frame as LF  # noqa: E402

F, B, IN1, IN2 = pcbnew.F_Cu, pcbnew.B_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu
REAR_Y0, REAR_Y1 = 179.5, LF.OUTLINE[3]            # rear band (chassis y)
X0, X1 = 284.0, 500.0
SPUR_W = 1.8


def mm(v):
    return pcbnew.FromMM(v)


def kpt(X, Y):
    return pcbnew.VECTOR2I(mm(620.0 - X), mm(250.0 - Y))


def pad_xy(board, ref, num):
    f = board.FindFootprintByReference(ref)
    for p in f.Pads():
        if p.GetNumber() == num:
            return 620.0 - pcbnew.ToMM(p.GetPosition().x), 250.0 - pcbnew.ToMM(p.GetPosition().y)
    raise KeyError(f"{ref} pad {num}")


def net_of(board, short):
    """HTR1 / HTR2 are local to sheet 01, so their full names carry the sheet path."""
    for name, ni in board.GetNetsByName().items():
        if str(name) == short or str(name).endswith("/" + short):
            return ni
    raise KeyError(short)


def zone(board, net, layer, pts, prio, name):
    z = pcbnew.ZONE(board)
    z.SetLayer(layer)
    z.SetNet(net_of(board, net))
    z.SetZoneName(name)
    z.SetAssignedPriority(prio)
    z.SetLocalClearance(mm(0.25))
    z.SetMinThickness(mm(0.4))
    z.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL)
    z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
    o = z.Outline()
    o.NewOutline()
    for X, Y in pts:
        p = kpt(X, Y)
        o.Append(p.x, p.y)
    board.Add(z)
    return z


def track(board, net, layer, w, pts):
    n = net_of(board, net)
    for a, b in zip(pts, pts[1:]):
        t = pcbnew.PCB_TRACK(board)
        t.SetStart(kpt(*a))
        t.SetEnd(kpt(*b))
        t.SetLayer(layer)
        t.SetWidth(mm(w))
        t.SetNet(n)
        board.Add(t)


def clear_old(board):
    for t in list(board.GetTracks()):
        if t.GetNetname().rsplit("/", 1)[-1] in ("HTR1", "HTR2"):
            board.Remove(t)
    for z in list(board.Zones()):
        if z.GetZoneName().startswith(("HTR1 ", "HTR2 ")):
            board.Remove(z)


def main():
    src, out = sys.argv[1], sys.argv[2]
    board = pcbnew.LoadBoard(src)
    clear_old(board)
    h1 = pad_xy(board, "J103", "1")      # HTR1 tab (one of its two legs)
    h2 = pad_xy(board, "J103", "2")
    # J103's legs: HTR1 at x 380.5 / 385.5, HTR2 at 392.0 / 397.0 (y 166.5). Each finger covers both legs of its
    # tab; the fill keeps the HTR2 finger 2.5 mm from C102's DRV_A pad (399.0, 178.5).

    def with_finger(cx, w):
        return [(X0, REAR_Y0), (cx - w / 2, REAR_Y0), (cx - w / 2, h1[1] - 1.5), (cx + w / 2, h1[1] - 1.5),
                (cx + w / 2, REAR_Y0), (X1, REAR_Y0), (X1, REAR_Y1), (X0, REAR_Y1)]

    zone(board, "HTR2", B, with_finger(394.5, 7.0), 10, "HTR2 rear B")          # both legs (392.0 / 397.0)
    for lay, nm in ((IN1, "In1"), (IN2, "In2")):
        zone(board, "HTR1", lay, with_finger(383.0, 7.0), 10, f"HTR1 rear {nm}")  # both legs (380.5 / 385.5)
    # HTR1 spurs: pin 2 -> pin-circle centre -> between pins 5 and 6 -> into the rear pour, on In1 and In2
    for v, (cx, cy) in LF.SOCKETS.items():
        p2 = pad_xy(board, v, "2")
        p5 = pad_xy(board, v, "5")
        p6 = pad_xy(board, v, "6")
        gap = ((p5[0] + p6[0]) / 2, (p5[1] + p6[1]) / 2)
        # leave the 5-6 gap angled away from pin 6 (straight back it would pass pin 6 at 0.245 mm)
        pts = [p2, (cx, cy), gap, (gap[0] + 1.2, REAR_Y0 + 3.0)]
        for lay in (IN1, IN2):
            track(board, "HTR1", lay, SPUR_W, pts)
    filler = pcbnew.ZONE_FILLER(board)
    filler.Fill(board.Zones())
    pcbnew.SaveBoard(out, board)
    print(f"{out}: heater pours (B HTR2, In1 / In2 HTR1) and 4 HTR1 spurs; J103 HTR1 {h1}, HTR2 {h2}")


if __name__ == "__main__":
    main()
