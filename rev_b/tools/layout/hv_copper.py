#!/usr/bin/env python3
"""Power amp rev B layout: the scripted copper (drawn, not routed), locked so the router never moves it.

    tools/p2k/bin/kipy rev_b/tools/layout/hv_copper.py IN.kicad_pcb OUT.kicad_pcb

What is drawn here (STATUS "Layout, first pass", section "How it is routed"):
- OT_A / OT_B (1.25 kV) on B, 2.0 mm: the lane at y 154.3 in front of the sockets, the rises to the plate
  pins, the branches to the J104 tabs and the clamps; CL_A / CL_B between the TVS pairs.
- V_ANODE: F at the centre tap and the clamps, then In2 along the front edge (y 130.3) and up the east
  strip to J101.
- V_SCREEN: J102 -> F -> via -> In2 "chord" at y 175.2 straight through the four sockets' pin circles
  (between pins 4 / 5 and 7 / 8) with spurs to the four screen resistors and C102.
- G2_1..G2_4 (pin 4 to its screen resistor), DRV_A's run through V2's pin circle (In2, behind the chord),
  the grid leads from the 5.6k stoppers out of the pin circles to the coupling caps.
- The heater pair: HTR1 on F and HTR2 on B stacked along the rear edge (y 185.0, 2.4 mm), the J103 tabs,
  pin 7 (HTR2) stubs on B and the HTR1 leads through each pin circle to pin 2 on F.
- Keep-outs for the router: no tracks / vias / fills on In1 / In2 within 4.2 mm of the OT copper (the
  internal 3.2 mm rule plus the trace), no vias and no B tracks within 7.3 mm of it (6.3 mm + via).
Positions in the chassis frame (layout_frame.py), converted like make_pcb.py.
"""
import math
import os
import sys

import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
import layout_frame as LF  # noqa: E402
import placement as PL  # noqa: E402

F, B, I1, I2 = pcbnew.F_Cu, pcbnew.B_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu


def mm(v):
    return pcbnew.FromMM(v)


def T(v):
    return pcbnew.ToMM(v)


def kpt(X, Y):
    return pcbnew.VECTOR2I(mm(620.0 - X), mm(250.0 - Y))


class Copper:
    def __init__(self, board):
        self.b = board
        self.nets = {}
        for name, ni in board.GetNetsByName().items():
            self.nets.setdefault(str(name).rsplit("/", 1)[-1], ni)
        self.fp = {f.GetReference(): f for f in board.GetFootprints()}
        self.n_tracks = 0
        self.n_vias = 0

    def net(self, name):
        return self.nets[name]

    def pad(self, ref, num, near=None):
        """Chassis position of pad `num` of `ref` (the leg nearest `near` for multi-leg pads)."""
        ps = [p for p in self.fp[ref].Pads() if p.GetNumber() == str(num)]
        pts = [(620.0 - T(p.GetPosition().x), 250.0 - T(p.GetPosition().y)) for p in ps]
        if near:
            pts.sort(key=lambda q: math.hypot(q[0] - near[0], q[1] - near[1]))
        return pts[0]

    def track(self, net, layer, w, pts):
        ni = self.net(net)
        for a, c in zip(pts, pts[1:]):
            t = pcbnew.PCB_TRACK(self.b)
            t.SetStart(kpt(*a))
            t.SetEnd(kpt(*c))
            t.SetLayer(layer)
            t.SetWidth(mm(w))
            t.SetNet(ni)
            t.SetLocked(True)
            self.b.Add(t)
            self.n_tracks += 1

    def via(self, net, X, Y, size=0.8, drill=0.4):
        v = pcbnew.PCB_VIA(self.b)
        v.SetPosition(kpt(X, Y))
        v.SetWidth(mm(size))
        v.SetDrill(mm(drill))
        v.SetNet(self.net(net))
        v.SetLocked(True)
        self.b.Add(v)
        self.n_vias += 1


def keepout(board, pts, layers, name, tracks=True, vias=True, fill=True):
    z = pcbnew.ZONE(board)
    z.SetIsRuleArea(True)
    z.SetDoNotAllowTracks(tracks)
    z.SetDoNotAllowVias(vias)
    z.SetDoNotAllowZoneFills(fill)
    z.SetDoNotAllowPads(False)
    z.SetDoNotAllowFootprints(False)
    z.SetZoneName(name)
    ls = pcbnew.LSET()
    for l in layers:
        ls.AddLayer(l)
    z.SetLayerSet(ls)
    o = z.Outline()
    o.NewOutline()
    for X, Y in pts:
        p = kpt(X, Y)
        o.Append(p.x, p.y)
    board.Add(z)


def band(a, c, r):
    """Rectangle (polygon) round segment a-c, half width r."""
    (x0, y0), (x1, y1) = a, c
    dx, dy = x1 - x0, y1 - y0
    L = math.hypot(dx, dy) or 1.0
    ux, uy = dx / L, dy / L
    nx, ny = -uy * r, ux * r
    return [(x0 - ux * r + nx, y0 - uy * r + ny), (x1 + ux * r + nx, y1 + uy * r + ny),
            (x1 + ux * r - nx, y1 + uy * r - ny), (x0 - ux * r - nx, y0 - uy * r - ny)]


LANE_Y = 154.3          # OT lane (B) in front of the sockets
SOCK = LF.SOCKETS
SY = 172.13


def pin(n, sx):
    a = math.radians(-135 + (n - 1) * 45)           # rev A orientation: pin 1 front-west, CCW in plan
    return sx + 8.6 * math.cos(a), SY + 8.6 * math.sin(a)


def gap(n1, n2, sx, out=3.0, inn=2.0):
    """Points outside / at / inside the gap between pins n1 and n2 (outward normal)."""
    (ax, ay), (bx, by) = pin(n1, sx), pin(n2, sx)
    cx, cy = (ax + bx) / 2, (ay + by) / 2
    r = math.hypot(cx - sx, cy - SY)
    ux, uy = (cx - sx) / r, (cy - SY) / r
    return (cx + ux * out, cy + uy * out), (cx, cy), (cx - ux * inn, cy - uy * inn)


def draw(c):
    sx1, sx2, sx3, sx4 = (SOCK[v][0] for v in ("V1", "V2", "V3", "V4"))
    ot_segs = []

    def ot(net, pts, layer=I2, w=2.0):
        c.track(net, layer, w, pts)
        ot_segs.extend(zip(pts, pts[1:]))

    # ---- OT_A: V1 / V2 plates, lane, branch to the tab and the clamps
    pa1, pa2 = pin(3, sx1), pin(3, sx2)
    ot("OT_A", [pa1, (pa1[0], LANE_Y), (pa2[0], LANE_Y), pa2])
    ja = c.pad("J104", 1, near=(311.7, 139.0))
    d101 = c.pad("D101", 1)
    d102 = c.pad("D102", 1)
    xb = (ja[0] + c.pad("J104", 1, near=(316, 139))[0]) / 2
    ot("OT_A", [(xb, LANE_Y), (xb, d101[1]), (xb, ja[1])])
    ot("OT_A", [d101, d102])
    ot("OT_A", [c.pad("J104", 1, near=(300, 139)), c.pad("J104", 1, near=(320, 139))])
    # ---- OT_B: tab, clamps, lane east of V2, V3 / V4 plates
    jb0, jb1 = c.pad("J104", 2, near=(355, 139)), c.pad("J104", 2, near=(370, 139))
    xbb = (jb0[0] + jb1[0]) / 2
    d105 = c.pad("D105", 1)
    d104 = c.pad("D104", 1)
    ot("OT_B", [jb0, jb1])
    ot("OT_B", [(xbb, jb0[1]), (xbb, d105[1]), d105])
    ot("OT_B", [(xbb, d105[1]), (372.0, d105[1]), (382.0, LANE_Y), (pin(3, sx4)[0], LANE_Y)])
    ot("OT_B", [jb1, d104])
    for sx in (sx3, sx4):
        p3 = pin(3, sx)
        ot("OT_B", [(p3[0], LANE_Y), p3])
    # ---- CL_A / CL_B between the TVS pairs
    c.track("CL_A", I2, 1.5, [c.pad("D102", 2), c.pad("D103", 1)])
    c.track("CL_B", I2, 1.5, [c.pad("D105", 2), c.pad("D106", 1)])

    # ---- V_ANODE: centre tap, clamps, C101 on F; In2 lane to J101
    ct0, ct1 = c.pad("J104", 3, near=(330, 132.5)), c.pad("J104", 3, near=(345, 132.5))
    xm = (ct0[0] + ct1[0]) / 2
    d103, d106 = c.pad("D103", 2), c.pad("D106", 2)
    c.track("V_ANODE", F, 1.5, [ct0, ct1])
    c.track("V_ANODE", F, 1.5, [(xm, ct0[1]), (xm, d103[1])])
    c.track("V_ANODE", F, 1.5, [d103, d106])
    c.track("V_ANODE", F, 1.5, [ct1, c.pad("C101", 1)])
    ja1 = c.pad("J101", 1, near=(514.5, 169.0))
    lane = [ct1, (ct1[0] + 2.2, 130.3), (507.5, 130.3), (507.5, 166.0), (ja1[0] - 2.5, ja1[1]), ja1]
    c.track("V_ANODE", I1, 2.0, lane)        # In1, the plane layer: In2 carries the plate lanes

    # ---- V_SCREEN: J102 -> F -> via -> In2 chord y 175.2 through the pin circles, spurs
    jv = c.pad("J102", 1, near=(514.5, 163.8))
    c102 = c.pad("C102", 1)
    vx, vy = 507.5, 175.2
    c.track("V_SCREEN", F, 1.0, [jv, (510.8, 166.8), (vx, vy), c102])
    c.via("V_SCREEN", vx, vy)
    r103 = c.pad("R103", 1)
    r115 = c.pad("R115", 1)
    r107 = c.pad("R107", 1)
    r111 = c.pad("R111", 1)
    chord = [(vx, vy), (r103[0] + 2.0, vy), r103]
    c.track("V_SCREEN", I2, 0.8, chord)
    for p in (r115, r107, r111):
        c.track("V_SCREEN", I2, 0.8, [(p[0], vy), p])

    # ---- G2: pin 4 to its screen resistor
    c.track("G2_1", F, 0.8, [pin(4, sx1), c.pad("R103", 2)])
    c.track("G2_2", F, 0.8, [pin(4, sx2), c.pad("R107", 2)])
    for sx, net, ref in ((sx3, "G2_3", "R111"), (sx4, "G2_4", "R115")):
        p4 = pin(4, sx)
        o, m, i = gap(8, 1, sx, out=2.5, inn=1.5)
        way = [(478.0, 171.8)] if net == "G2_4" else []
        c.track(net, I2, 0.6, [p4, (sx + 5.37, 173.4), i, m, o] + way + [c.pad(ref, 2)])

    # ---- grid leads: stopper pad 1 -> out of the pin circle between pins 5 and 6 -> coupling cap
    stoppers = {1: "R102", 2: "R106", 3: "R110", 4: "R114"}
    caps = {1: ("C103", "GRID1"), 2: ("C104", "GRID2"), 3: ("C105", "GRID3"), 4: ("C106", "GRID4")}
    for n, sx in enumerate((sx1, sx2, sx3, sx4), 1):
        st = c.pad(stoppers[n], 1)
        cap, net = caps[n]
        cp = c.pad(cap, 2)
        if n == 4:
            o, m, i = gap(8, 1, sx, out=2.5, inn=1.5)
            c.via(net, st[0] - 1.0, st[1] - 0.8, 0.6, 0.3)
            c.track(net, F, 0.4, [st, (st[0] - 1.0, st[1] - 0.8)])
            c.track(net, B, 0.4, [(st[0] - 1.0, st[1] - 0.8), i, m, o, (480.0, 169.6), (476.0, 169.4), (473.2, 168.5), (471.0, 167.0), cp])
            continue
        o, m, i = gap(5, 6, sx, out=2.0, inn=1.5)
        if n == 1:
            c.track(net, F, 0.4, [st, i, m, o, (o[0] + 1.6, 181.4), (309.5, 181.4)])
            c.via(net, 309.5, 181.4, 0.6, 0.3)
            c.track(net, I2, 0.4, [(309.5, 181.4), (310.2, 182.0), (cp[0], 182.0), cp])
        else:
            c.track(net, F, 0.4, [st, i, m, o, (o[0] + 1.6, 181.4), (cp[0], 181.4), cp])

    # ---- DRV_A through V2's pin circle (In2, behind the V_SCREEN chord): C104 <-> C103
    o56, m56, i56 = gap(5, 6, sx2, out=3.0, inn=2.0)
    o67, m67, i67 = gap(6, 7, sx2, out=3.0, inn=2.0)
    c104, c103 = c.pad("C104", 1), c.pad("C103", 1)
    c.track("DRV_A", I2, 0.6, [c104, (c104[0] - 1.0, o56[1]), o56, m56, i56, i67, m67, o67,
                                (c103[0] + 2.0, o67[1]), c103])

    # ---- DRV_A / DRV_B from J105 (In2): DRV_A through V1's pin circle (pins 1-2 -> 4-5) to C103; DRV_B
    # through it (8-1 -> 5-6), along the rear edge (In2, y 184.5) to C105, and on F to C106
    j2, j4 = c.pad("J105", 2), c.pad("J105", 4)
    o12, m12, i12 = gap(1, 2, sx1, out=2.5, inn=1.5)
    o45, m45, i45 = gap(4, 5, sx1, out=2.5, inn=1.5)
    c.track("DRV_A", I2, 0.6, [j2, (j2[0], 138.0), (297.5, 138.0), (297.5, 152.0), o12, m12, i12, i45, m45, o45,
                               (o45[0] + 0.5, 176.1), (340.0, 176.1), c103])
    o81, m81, i81 = gap(8, 1, sx1, out=2.5, inn=1.5)
    o56b, m56b, i56b = gap(5, 6, sx1, out=2.5, inn=1.5)
    c105, c106 = c.pad("C105", 1), c.pad("C106", 1)
    c.track("DRV_B", I2, 0.6, [j4, (283.6, j4[1] + 3.0), (283.6, 165.5), o81, m81, i81, i56b, m56b, o56b,
                               (o56b[0] + 0.6, 184.5), (c105[0] - 0.6, 184.5), c105])
    c.track("DRV_B", F, 0.6, [c105, c106])

    # ---- heater pair: HTR1 F / HTR2 B stacked at the rear edge, pin 7 stubs (B), HTR1 to pin 2 (F)
    HY, HW = 185.0, 2.4
    g1, g4 = gap(6, 7, sx1)[1][0], gap(6, 7, sx4)[1][0]
    c.track("HTR1", F, HW, [(g1, HY), (g4, HY)])
    c.track("HTR2", B, HW, [(pin(7, sx1)[0], HY), (pin(7, sx4)[0], HY)])
    for sx in (sx1, sx2, sx3, sx4):
        p7, p2 = pin(7, sx), pin(2, sx)
        c.track("HTR2", B, 1.2, [(p7[0], HY), p7])
        o, m, i = gap(6, 7, sx, out=2.0, inn=1.0)
        c.track("HTR1", F, 1.0, [(m[0], HY), m, i, p2])
    h1 = [c.pad("J103", 1, near=(380, 166.5)), c.pad("J103", 1, near=(386, 166.5))]
    h2 = [c.pad("J103", 2, near=(391, 166.5)), c.pad("J103", 2, near=(398, 166.5))]
    c.track("HTR1", F, 2.0, [h1[0], h1[1], (h1[1][0] + 2.5, h1[1][1] + 2.5), (h1[1][0] + 2.5, HY)])
    c.track("HTR2", B, 2.0, [h2[1], h2[0], (h2[0][0] - 2.0, h2[0][1] + 2.0), (h2[0][0] - 2.0, HY)])
    return ot_segs


def crescent(p3, sock, r_keep, r_area, n=48):
    """Circle round pad p3 (radius r_keep) minus the socket area circle (r_area): polygon."""
    (px, py), (sx, sy) = p3, sock
    pts = []
    for k in range(n):
        a = 2 * math.pi * k / n
        q = (px + r_keep * math.cos(a), py + r_keep * math.sin(a))
        pts.append((q, math.hypot(q[0] - sx, q[1] - sy) >= r_area))
    # rotate so the list starts with an outside point after an inside one
    while not (pts[0][1] and not pts[-1][1]):
        pts = pts[1:] + pts[:1]
    out = [q for q, ok in pts if ok]
    a0 = math.atan2(out[-1][1] - sy, out[-1][0] - sx)
    a1 = math.atan2(out[0][1] - sy, out[0][0] - sx)
    while a1 < a0:
        a1 += 2 * math.pi
    if a1 - a0 > math.pi:
        a1 -= 2 * math.pi
    arc = [(sx + r_area * math.cos(a0 + (a1 - a0) * k / 12), sy + r_area * math.sin(a0 + (a1 - a0) * k / 12))
           for k in range(1, 12)]
    return out + arc


def keepouts(board, ot_segs, c):
    """The plate lanes run on In2 (B1, 3.2 mm). B lies 0.21 mm (7628 prepreg) below In2: no copper on B
    within 4.2 mm of the lane copper. In1 is 1.065 mm (core) above: it keeps its plane. Vias stay 3.2 mm
    (plus the via) from the lanes. Round every exposed 1.25 kV pad, F / B tracks and vias of other nets keep
    6.3 mm (router aid; the DRC rules check it), except inside a socket's pin area (its own exception)."""
    for i, (a, c_) in enumerate(ot_segs):
        keepout(board, band(a, c_, 1.0 + 3.2), (B,), f"OT B void {i}", tracks=True, vias=True, fill=True)
        keepout(board, band(a, c_, 1.0 + 3.2 + 0.4), (F, I1, B), f"OT vias {i}", tracks=False, vias=True, fill=False)
    hv_pads = []
    for f in board.GetFootprints():
        for p in f.Pads():
            if p.GetNetname().rsplit("/", 1)[-1] in ("OT_A", "OT_B", "CL_A", "CL_B") \
                    and p.GetAttribute() == pcbnew.PAD_ATTRIB_PTH:
                hv_pads.append((f.GetReference(), (620.0 - T(p.GetPosition().x), 250.0 - T(p.GetPosition().y)),
                                T(p.GetSize().x) / 2))
    for k, (ref, (x, y), r) in enumerate(hv_pads):
        # circumscribed 32-gon, r + 6.3 mm + margin; these router fences are removed again by pours.py
        # (the DRC rules check the real distances; the fences would also cover the drawn in-ring copper)
        rk = (r + 6.3 + 0.3) / math.cos(math.pi / 32)
        poly = [(x + rk * math.cos(2 * math.pi * j / 32), y + rk * math.sin(2 * math.pi * j / 32)) for j in range(32)]
        keepout(board, poly, (F, B), f"HV pad fence {k}", tracks=True, vias=True, fill=False)
        s = pcbnew.PCB_SHAPE(board)               # the same fence for the router (--keepout, User.2)
        s.SetShape(pcbnew.SHAPE_T_POLY)
        s.SetPolyPoints([kpt(*q) for q in poly])
        s.SetLayer(pcbnew.User_2)
        s.SetWidth(mm(0.05))
        s.SetFilled(False)
        board.Add(s)


def main():
    src, dst = sys.argv[1], sys.argv[2]
    b = pcbnew.LoadBoard(src)
    c = Copper(b)
    segs = draw(c)
    keepouts(b, segs, c)
    pcbnew.SaveBoard(dst, b)
    print(f"{dst}: {c.n_tracks} scripted tracks, {c.n_vias} vias, {len(segs)} OT segments kept out")


if __name__ == "__main__":
    main()
