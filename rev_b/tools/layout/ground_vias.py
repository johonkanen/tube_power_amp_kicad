#!/usr/bin/env python3
"""Power amp rev B: a stitching via (and a short stub) beside every SMD ground pad, placed BEFORE the router,
so every GND / GNDD pad reaches the In1 / In2 ground fill and no pad is left boxed in by signal tracks.
    tools/p2k/bin/kipy rev_b/tools/layout/ground_vias.py IN.kicad_pcb OUT.kicad_pcb
A candidate spot (four sides of the pad, two distances) is taken when it keeps the via's clearance to every
other-net pad, track and via (class-aware: 6.3 / 2.5 / 0.6 / 0.25 mm) and lies outside the via keep-outs."""
import math
import os
import sys

import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
import placement as PL  # noqa: E402

VIA, DRILL, STUB = 0.6, 0.3, 0.4
CLS = {}
for c, d in (("HV1250", 6.4), ("HV450", 2.6), ("BIAS80", 0.65), ("HTR", 0.3)):
    for n in PL.CLASS_NETS[c]:
        CLS[n] = d
GROUNDS = ("GND", "GNDD")


def mm(v):
    return pcbnew.FromMM(v)


def T(v):
    return pcbnew.ToMM(v)


def short(n):
    return n.rsplit("/", 1)[-1]


def seg_dist(p, a, b):
    (px, py), (ax, ay), (bx, by) = p, a, b
    dx, dy = bx - ax, by - ay
    L2 = dx * dx + dy * dy
    t = 0.0 if L2 == 0 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / L2))
    return math.hypot(px - ax - t * dx, py - ay - t * dy)


def box_dist(p, box):
    x0, y0, x1, y1 = box
    dx = max(x0 - p[0], 0.0, p[0] - x1)
    dy = max(y0 - p[1], 0.0, p[1] - y1)
    return math.hypot(dx, dy)


def main():
    src, dst = sys.argv[1], sys.argv[2]
    b = pcbnew.LoadBoard(src)
    pads, gpads = [], []
    for f in b.GetFootprints():
        for p in f.Pads():
            bb = p.GetBoundingBox()
            box = (T(bb.GetLeft()), T(bb.GetTop()), T(bb.GetRight()), T(bb.GetBottom()))
            n = short(p.GetNetname())
            pads.append((box, n, p))
            if n in GROUNDS and p.GetAttribute() == pcbnew.PAD_ATTRIB_SMD:
                gpads.append((box, n, p, f.IsFlipped()))
    tracks = []
    vias = []
    for t in b.GetTracks():
        n = short(t.GetNetname())
        if t.GetClass() == "PCB_VIA":
            vias.append(((T(t.GetPosition().x), T(t.GetPosition().y)), n, T(t.GetWidth(pcbnew.F_Cu)) / 2))
        else:
            tracks.append(((T(t.GetStart().x), T(t.GetStart().y)), (T(t.GetEnd().x), T(t.GetEnd().y)),
                           T(t.GetWidth()) / 2, n))
    keep = [z for z in b.Zones() if z.GetIsRuleArea() and z.GetDoNotAllowVias()]
    edge = b.GetBoardEdgesBoundingBox()
    ex0, ey0, ex1, ey1 = T(edge.GetLeft()), T(edge.GetTop()), T(edge.GetRight()), T(edge.GetBottom())
    nets = b.GetNetsByName()
    netinfo = {short(str(k)): v for k, v in nets.items()}
    added = 0
    for box, n, p, flipped in gpads:
        cx, cy = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
        hw, hh = (box[2] - box[0]) / 2, (box[3] - box[1]) / 2
        cands = []
        for extra in (0.3, 0.6, 0.9, 1.3, 1.8, 2.4):
            for k in range(16):
                a = 2 * math.pi * k / 16
                ux, uy = math.cos(a), math.sin(a)
                # distance from the centre to the pad's bounding box edge along (ux, uy)
                dd = min(hw / abs(ux) if abs(ux) > 1e-9 else 1e9, hh / abs(uy) if abs(uy) > 1e-9 else 1e9)
                cands.append((cx + ux * (dd + VIA / 2 + extra), cy + uy * (dd + VIA / 2 + extra)))
        if any(v[1] == n and math.hypot(v[0][0] - cx, v[0][1] - cy) < max(hw, hh) + 1.2 for v in vias):
            continue
        for q in cands:
            if not (ex0 + 0.8 < q[0] < ex1 - 0.8 and ey0 + 0.8 < q[1] < ey1 - 0.8):
                continue
            ok = True
            for bx, bn, _ in pads:
                if bn == n:
                    continue
                need = VIA / 2 + max(0.25, CLS.get(bn, 0.0))
                if box_dist(q, bx) < need:
                    ok = False
                    break
                # the stub from the pad centre to the via (sampled)
                if bn and any(box_dist((cx + (q[0] - cx) * s, cy + (q[1] - cy) * s), bx) < STUB / 2 + max(0.25, CLS.get(bn, 0.0))
                              for s in (0.2, 0.4, 0.6, 0.8)):
                    ok = False
                    break
            if not ok:
                continue
            for a, c, w, tn in tracks:
                if tn == n:
                    continue
                need = VIA / 2 + w + max(0.25, CLS.get(tn, 0.0))
                if seg_dist(q, a, c) < need or any(seg_dist((cx + (q[0] - cx) * s, cy + (q[1] - cy) * s), a, c) < STUB / 2 + w + 0.25
                                                   for s in (0.2, 0.4, 0.6, 0.8)):
                    ok = False
                    break
            if not ok:
                continue
            for vp, vn, vr in vias:
                if math.hypot(vp[0] - q[0], vp[1] - q[1]) < VIA / 2 + vr + (0.0 if vn == n else 0.3) + 0.2:
                    ok = False
                    break
            if not ok:
                continue
            pt = pcbnew.VECTOR2I(mm(q[0]), mm(q[1]))
            if any(z.Outline().Contains(pt) for z in keep):
                continue
            v = pcbnew.PCB_VIA(b)
            v.SetPosition(pt)
            v.SetWidth(mm(VIA))
            v.SetDrill(mm(DRILL))
            v.SetNet(netinfo[n])
            v.SetLocked(True)
            b.Add(v)
            s = pcbnew.PCB_TRACK(b)
            s.SetStart(pcbnew.VECTOR2I(mm(cx), mm(cy)))
            s.SetEnd(pt)
            s.SetWidth(mm(STUB))
            s.SetLayer(pcbnew.B_Cu if flipped else pcbnew.F_Cu)
            s.SetNet(netinfo[n])
            s.SetLocked(True)
            b.Add(s)
            vias.append((q, n, VIA / 2))
            tracks.append(((cx, cy), q, STUB / 2, n))
            added += 1
            break
    pcbnew.SaveBoard(dst, b)
    print(f"{dst}: {added} stitching vias for {len(gpads)} SMD ground pads")


if __name__ == "__main__":
    main()
