#!/usr/bin/env python3
"""Power amp rev B layout: ground pours (grounding.md 4).
    tools/p2k/bin/kipy rev_b/tools/layout/pours.py IN.kicad_pcb OUT.kicad_pcb

- GND (AGND, whose star is J101-2 GND_PWR) on all four layers over the whole board; In1 is the plane.
- GNDD (the DGND island: the ribbon headers J501 / J502, the expander U501, W09's BIAS_RTN tab) on all four
  layers inside the island polygon, higher priority; it meets GND only through the soft tie R503 || C501.
- The HV keep-outs come from the rules (net classes and the custom rules: 6.3 / 2.5 mm outer, 3.2 / 0.5 mm
  inner) and from the OT keep-out areas drawn by hv_copper.py.
"""
import os
import sys

import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
import layout_frame as LF  # noqa: E402

LAYERS = (pcbnew.F_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu, pcbnew.B_Cu)
DGND = [(478.0, 127.05), (519.09, 127.05), (519.09, 153.0), (505.0, 153.0), (505.0, 158.5), (480.0, 158.5),
        (480.0, 147.5), (478.0, 147.5)]


def mm(v):
    return pcbnew.FromMM(v)


def kpt(X, Y):
    return pcbnew.VECTOR2I(mm(620.0 - X), mm(250.0 - Y))


def zone(board, net, layer, poly, prio):
    z = pcbnew.ZONE(board)
    z.SetLayer(layer)
    z.SetNet(net)
    z.SetAssignedPriority(prio)
    z.SetMinThickness(mm(0.25))
    z.SetLocalClearance(mm(0.3))
    z.SetThermalReliefGap(mm(0.35))
    z.SetThermalReliefSpokeWidth(mm(0.5))
    z.SetPadConnection(pcbnew.ZONE_CONNECTION_THT_THERMAL)   # SMD pads solid, through-hole pads with reliefs
    z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
    o = z.Outline()
    o.NewOutline()
    for X, Y in poly:
        p = kpt(X, Y)
        o.Append(p.x, p.y)
    board.Add(z)


def main():
    src, dst = sys.argv[1], sys.argv[2]
    b = pcbnew.LoadBoard(src)
    for z in list(b.Zones()):                    # the router-only fences round the 1.25 kV pads
        if z.GetIsRuleArea() and z.GetZoneName().startswith("HV pad fence"):
            b.Delete(z)
    nets = {}
    for name, ni in b.GetNetsByName().items():
        nets.setdefault(str(name).rsplit("/", 1)[-1], ni)
    x0, y0, x1, y1 = LF.OUTLINE
    whole = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    for layer in LAYERS:
        zone(b, nets["GND"], layer, whole, 0)
        zone(b, nets["GNDD"], layer, DGND, 1)
    zones = b.Zones()
    pcbnew.ZONE_FILLER(b).Fill(zones)
    pcbnew.SaveBoard(dst, b)
    print(f"{dst}: GND / GNDD pours on 4 layers, filled")


if __name__ == "__main__":
    main()
