#!/usr/bin/env python3
"""Power amp rev B, layout first pass: the placed board (outline, holes, every part, net classes, design
rules, keep-outs, notes) from the schematic netlist.

    tools/p2k/bin/kipy rev_b/tools/layout/make_pcb.py [OUT.kicad_pcb]   (default build/layout/00_placed.kicad_pcb)

Frame (STATUS "Layout, first pass"): positions are written in the CHASSIS frame (D748 top plate, mm, plan
from above, y from the front panel) and converted here: KiCad x_k = 620 - X, y_k = 250 - Y (rev A's KiCad
frame + (205.05, 97.55)). The board hangs 15 mm below the plate with KiCad's F side facing DOWN
(components down); the octal sockets are on B (the plate side) as rev A, the tubes stand on the plate.
The KiCad F view is the chassis plan mirrored left-right: east (HV supplies) on the left.

Rotations are KiCad orientations. For a part on F, its local +x then points to chassis -X (west) at 0 deg,
+Y (rear) at 90, +X (east) at 180, -Y (front) at 270.
"""
import json
import math
import os
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET

import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
RB = os.path.dirname(os.path.dirname(HERE))
ROOT = os.path.dirname(RB)
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)
import layout_frame as LF  # noqa: E402
import placement as PL  # noqa: E402

PROJECT = "tube_power_amp_revb"
K = os.path.join(RB, "kicad")
PRO = os.path.join(K, PROJECT + ".kicad_pro")
SCH = os.path.join(K, PROJECT + ".kicad_sch")
KICAD_CLI = os.path.join(ROOT, "tools", "p2k", "bin", "kicad-cli")
STOCK = os.path.join(os.environ.get("KICAD_MOUNT") or open(f"/tmp/p2k_kicad_mount.{os.getuid()}").read().strip(),
                     "share", "kicad", "footprints")
OUT = os.path.join(ROOT, "build", "layout", "00_placed.kicad_pcb")


def mm(v):
    return pcbnew.FromMM(v)


def T(v):
    return pcbnew.ToMM(v)


def kpt(X, Y):
    """Chassis (X, Y) -> KiCad point."""
    return pcbnew.VECTOR2I(mm(620.0 - X), mm(250.0 - Y))


def chassis(p):
    return 620.0 - T(p.x), 250.0 - T(p.y)


# ----------------------------------------------------------------------------------- rules
def project_settings():
    pro = json.load(open(PRO))
    classes = []
    for name, clr, tw, col, prio in PL.NETCLASSES:
        classes.append({"name": name, "clearance": clr, "track_width": tw, "via_diameter": 0.8, "via_drill": 0.4,
                        "pcb_color": col, "schematic_color": "rgba(0, 0, 0, 0.000)", "priority": prio})
    pats = []
    for cls, names in PL.CLASS_NETS.items():
        for n in names:
            pats += [{"netclass": cls, "pattern": n}, {"netclass": cls, "pattern": "*/" + n}]
    pro["net_settings"] = {"classes": classes, "meta": {"version": 4}, "net_colors": None,
                           "netclass_assignments": None, "netclass_patterns": pats}
    pro.setdefault("board", {})
    pro["board"]["design_settings"] = {
        "rules": {"min_clearance": 0.15, "min_track_width": 0.15, "min_connection": 0.15, "min_via_diameter": 0.6,
                  "min_via_annular_width": 0.15, "min_through_hole_diameter": 0.3, "min_hole_to_hole": 0.5,
                  "min_hole_clearance": 0.25, "min_copper_edge_clearance": 0.5, "min_silk_clearance": 0.0,
                  "min_text_height": 0.8, "min_text_thickness": 0.12, "solder_mask_to_copper_clearance": 0.0},
        "drc_exclusions": []}
    json.dump(pro, open(PRO, "w"), indent=2)
    open(os.path.join(K, PROJECT + ".kicad_dru"), "w").write(PL.DRU)


# ----------------------------------------------------------------------------------- footprints
def netlist():
    with tempfile.TemporaryDirectory() as td:
        out = os.path.join(td, "n.xml")
        subprocess.run([KICAD_CLI, "sch", "export", "netlist", "--format", "kicadxml", "-o", out, SCH],
                       check=True, capture_output=True)
        return ET.parse(out)


def load_fp(lib_id):
    lib, name = lib_id.split(":")
    path = os.path.join(RB, "lib", PROJECT + ".pretty") if lib == PROJECT else os.path.join(STOCK, lib + ".pretty")
    f = pcbnew.FootprintLoad(path, name)
    if f is None:
        raise SystemExit(f"footprint {lib_id} not found in {path}")
    f.SetFPID(pcbnew.LIB_ID(lib, name))
    return f


def place(f, X, Y, rot, side):
    f.SetPosition(pcbnew.VECTOR2I(0, 0))
    if (side == "B") != f.IsFlipped():
        f.Flip(f.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
    f.SetOrientationDegrees(rot)
    f.SetPosition(kpt(X, Y))


# ----------------------------------------------------------------------------------- graphics
def seg(board, a, b, layer, w=0.1):
    s = pcbnew.PCB_SHAPE(board)
    s.SetShape(pcbnew.SHAPE_T_SEGMENT)
    s.SetStart(kpt(*a))
    s.SetEnd(kpt(*b))
    s.SetLayer(layer)
    s.SetWidth(mm(w))
    board.Add(s)


def poly_line(board, pts, layer, w=0.1, closed=True):
    q = list(pts) + ([pts[0]] if closed else [])
    for a, b in zip(q, q[1:]):
        seg(board, a, b, layer, w)


def circle(board, c, r, layer, w=0.1):
    s = pcbnew.PCB_SHAPE(board)
    s.SetShape(pcbnew.SHAPE_T_CIRCLE)
    s.SetCenter(kpt(*c))
    s.SetEnd(kpt(c[0] + r, c[1]))
    s.SetLayer(layer)
    s.SetWidth(mm(w))
    board.Add(s)


def note(board, s, X, Y, size=1.2, layer=pcbnew.Cmts_User, mirror=False):
    t = pcbnew.PCB_TEXT(board)
    t.SetText(s)
    t.SetPosition(kpt(X, Y))
    t.SetLayer(layer)
    t.SetTextSize(pcbnew.VECTOR2I(mm(size), mm(size)))
    t.SetTextThickness(mm(max(0.12, size * 0.15)))
    t.SetHorizJustify(pcbnew.GR_TEXT_H_ALIGN_LEFT)
    t.SetMirrored(mirror)
    board.Add(t)


def rule_area(board, pts, layers, name="", tracks=True, vias=True, pads=False, fps=False, fill=True):
    z = pcbnew.ZONE(board)
    z.SetIsRuleArea(True)
    z.SetDoNotAllowTracks(tracks)
    z.SetDoNotAllowVias(vias)
    z.SetDoNotAllowZoneFills(fill)
    z.SetDoNotAllowPads(pads)
    z.SetDoNotAllowFootprints(fps)
    if name:
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
    return z


def circle_pts(X, Y, r, n=32):
    return [(X + r * math.cos(2 * math.pi * i / n), Y + r * math.sin(2 * math.pi * i / n)) for i in range(n)]


def outline(board):
    x0, y0, x1, y1 = LF.OUTLINE
    poly_line(board, [(x0, y0), (x1, y0), (x1, y1), (x0, y1)], pcbnew.Edge_Cuts, 0.1)


def holes(board):
    """Mounting holes: board-only footprints, 3.2 mm NPTH (unplated: no chassis net on the board)."""
    for ref, (X, Y) in PL.HOLES.items():
        f = pcbnew.FOOTPRINT(board)
        f.SetReference(ref)
        f.SetValue("M3 standoff 15 mm")
        f.SetBoardOnly(True)
        f.SetExcludedFromBOM(True)
        f.SetExcludedFromPosFiles(True)
        f.Value().SetVisible(False)
        board.Add(f)
        p = pcbnew.PAD(f)
        p.SetAttribute(pcbnew.PAD_ATTRIB_NPTH)
        p.SetShape(pcbnew.PAD_SHAPE_CIRCLE)
        p.SetSize(pcbnew.VECTOR2I(mm(3.2), mm(3.2)))
        p.SetDrillSize(pcbnew.VECTOR2I(mm(3.2), mm(3.2)))
        p.SetLayerSet(pcbnew.PAD.UnplatedHoleMask())
        f.Add(p)
        f.SetPosition(kpt(X, Y))
        f.Reference().SetPosition(kpt(X, Y - 4.2))
        f.Reference().SetLayer(pcbnew.F_SilkS)
        for lay in (pcbnew.F_CrtYd, pcbnew.F_Fab):
            s = pcbnew.PCB_SHAPE(f)
            s.SetShape(pcbnew.SHAPE_T_CIRCLE)
            s.SetCenter(kpt(X, Y))
            s.SetEnd(kpt(X + PL.STANDOFF_R, Y))
            s.SetLayer(lay)
            s.SetWidth(mm(0.05))
            f.Add(s)
        # no copper under the standoff / screw head
        rule_area(board, circle_pts(X, Y, PL.STANDOFF_R), PL.CU_OUT, name=f"standoff {ref}")
        rule_area(board, circle_pts(X, Y, 2.2), PL.CU_IN, name=f"standoff {ref} inner")


def keepouts(board):
    for name, pts, layers, kw in PL.keepouts():
        rule_area(board, pts, layers, name=name, **kw)


def notes(board):
    C = pcbnew.Cmts_User
    for name, (x0, y0, x1, y1) in PL.ZONE_NOTES.items():
        poly_line(board, [(x0, y0), (x1, y0), (x1, y1), (x0, y1)], C, 0.12)
        note(board, name, x1 - 0.5, y1 - 0.6, 0.9)
    for name, (X, Y) in LF.SOCKETS.items():
        circle(board, (X, Y), 40.0, pcbnew.Dwgs_User, 0.08)
        circle(board, (X, Y), 30.0, pcbnew.Dwgs_User, 0.08)
        circle(board, (X, Y), 25.0, pcbnew.Dwgs_User, 0.08)
    for (X, Y) in LF.OT_SCREWS:
        if Y > 120:
            circle(board, (X, Y), 1.75, pcbnew.Dwgs_User, 0.1)
            note(board, "OT bolt above", X - 1, Y + 2.5, 0.8, pcbnew.Dwgs_User)
    S = pcbnew.F_SilkS
    for txt, X, Y, sz in PL.SILK:
        note(board, txt, X, Y, sz, S, mirror=False)


def silk_refs(board):
    for f in board.GetFootprints():
        if f.GetReference() not in PL.SILK_REFS and not f.GetReference().startswith("TP"):
            f.Reference().SetLayer(pcbnew.B_Fab if f.IsFlipped() else pcbnew.F_Fab)


def court_bbox(f):
    """Courtyard bounding box (KiCad mm) of a placed footprint, else its pads' box."""
    lay = pcbnew.B_CrtYd if f.IsFlipped() else pcbnew.F_CrtYd
    try:
        c = f.GetCourtyard(lay)
        if c.OutlineCount():
            b = c.BBox()
            return T(b.GetLeft()), T(b.GetTop()), T(b.GetRight()), T(b.GetBottom())
    except Exception:
        pass
    b = f.GetBoundingBox(False)
    return T(b.GetLeft()), T(b.GetTop()), T(b.GetRight()), T(b.GetBottom())


def _hit(box, boxes, m=0.1):
    x0, y0, x1, y1 = box
    for a0, b0, a1, b1 in boxes:
        if x0 < a1 + m and a0 < x1 + m and y0 < b1 + m and b0 < y1 + m:
            return True
    return False


HV_INFLATE = {}
for _c, _d in (("HV1250", 6.4), ("HV450", 2.6), ("BIAS80", 0.0), ("HTR", 0.0)):
    for _n in PL.CLASS_NETS.get(_c, []):
        HV_INFLATE[_n] = _d


def occupancy(fps, refs):
    """Courtyard boxes per side of the placed parts; a through-hole part also blocks its pads on the
    other side. Pads of the HV classes are grown by their spacing (6.4 / 2.6 mm), so the packer keeps
    low-voltage parts out of the HV keep-outs."""
    occ = {"F": [], "B": []}
    for r in refs:
        f = fps[r]
        side = "B" if f.IsFlipped() else "F"
        occ[side].append(court_bbox(f))
        other = "F" if side == "B" else "B"
        for p in f.Pads():
            b = p.GetBoundingBox()
            box = [T(b.GetLeft()), T(b.GetTop()), T(b.GetRight()), T(b.GetBottom())]
            g = HV_INFLATE.get(p.GetNetname().rsplit("/", 1)[-1], 0.0)
            grown = (box[0] - g, box[1] - g, box[2] + g, box[3] + g)
            if p.GetAttribute() == pcbnew.PAD_ATTRIB_PTH:
                occ[other].append((box[0] - 0.3, box[1] - 0.3, box[2] + 0.3, box[3] + 0.3))
                if g:
                    occ["F"].append(grown)
                    occ["B"].append(grown)
            elif g:
                occ[side].append(grown)
    return occ


def pack(board, fps, missing):
    """Bottom-left fill for PL.GROUPS, avoiding everything already placed: each part goes to the first
    free spot scanning from the zone's front (KiCad bottom) rearward and, in each row, from its chassis
    west end (KiCad right) eastward, on a 0.25 mm grid. Returns the refs left over (parked off the board)."""
    left = set(missing)
    placed = [r for r in fps if r not in left]
    occ = occupancy(fps, placed)
    parked = 0
    step = 0.25
    for name, refs, (X0, Y0, X1, Y1), side, rot, gap in PL.GROUPS:
        kx0, kx1 = 620 - X1, 620 - X0          # KiCad x range
        ky0, ky1 = 250 - Y1, 250 - Y0          # KiCad y range
        zone_boxes = [b for b in occ[side] if b[0] < kx1 + 1 and b[2] > kx0 - 1 and b[1] < ky1 + 1 and b[3] > ky0 - 1]
        over = []
        for ref in [r for r in refs if r in left]:
            f = fps[ref]
            place(f, 620 - kx1, 250 - ky1, rot, side)
            bx0, by0, bx1, by1 = court_bbox(f)
            w, h = bx1 - bx0, by1 - by0
            spot = None
            cy = ky1
            while spot is None and cy - h >= ky0 - 1e-6:
                cx = kx1
                while cx - w >= kx0 - 1e-6:
                    box = (cx - w, cy - h, cx, cy)
                    if not _hit(box, zone_boxes, gap * 0.5):
                        spot = box
                        break
                    cx -= step
                cy -= step
            if spot is None:
                over.append(ref)
                f.SetPosition(pcbnew.VECTOR2I(mm(60.0), mm(30.0 + 7.0 * parked)))
                parked += 1
                continue
            pos = f.GetPosition()
            f.SetPosition(pcbnew.VECTOR2I(pos.x + mm(spot[2] - bx1), pos.y + mm(spot[3] - by1)))
            zone_boxes.append(spot)
            occ[side].append(spot)
            if any(p.GetAttribute() == pcbnew.PAD_ATTRIB_PTH for p in f.Pads()):
                occ["F" if side == "B" else "B"].append(spot)
            left.discard(ref)
        if over:
            print(f"pack {name}: {len(over)} did not fit: {' '.join(over)}")
    return sorted(left)


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else OUT
    os.makedirs(os.path.dirname(out), exist_ok=True)
    project_settings()
    board = pcbnew.NewBoard(out)
    board.SetCopperLayerCount(4)
    ds = board.GetDesignSettings()
    ds.SetBoardThickness(mm(1.6))
    ds.m_TrackMinWidth = mm(0.15)
    ds.m_MinClearance = mm(0.15)
    ds.m_ViasMinSize = mm(0.6)
    ds.m_MinThroughDrill = mm(0.3)
    ds.m_CopperEdgeClearance = mm(0.5)
    ds.m_HoleToHoleMin = mm(0.5)
    outline(board)

    t = netlist()
    nets = {}
    for n in t.iter("net"):
        name = n.get("name")
        ni = pcbnew.NETINFO_ITEM(board, name)
        board.Add(ni)
        for nd in n.iter("node"):
            nets[(nd.get("ref"), nd.get("pin"))] = ni
    placed = PL.positions()
    missing = []
    fps = {}
    for c in t.iter("comp"):
        ref = c.get("ref")
        f = load_fp(c.findtext("footprint"))
        f.SetReference(ref)
        f.SetValue(c.findtext("value"))
        sym = {fld.get("name"): fld.text or "" for fld in c.iter("field")}
        for fd in f.GetFields():
            if fd.GetName() in ("Datasheet", "Description"):
                fd.SetText(sym.get(fd.GetName(), ""))
        sp = c.find("sheetpath")
        f.SetPath(pcbnew.KIID_PATH(sp.get("tstamps") + c.findtext("tstamps")))
        f.SetSheetname(sp.get("names"))
        f.SetSheetfile(c.find("property[@name='Sheetfile']").get("value"))
        f.SetExcludedFromBOM(c.find("property[@name='exclude_from_bom']") is not None)
        for p in f.Pads():
            ni = nets.get((ref, p.GetNumber()))
            if ni is not None:
                p.SetNet(ni)
        board.Add(f)
        fps[ref] = f
        if ref not in placed:
            missing.append(ref)
            continue
        place(f, *placed[ref])
    missing = pack(board, fps, missing)
    if missing:
        print(f"no position for {len(missing)} parts: {' '.join(sorted(missing))}")
    holes(board)
    keepouts(board)
    notes(board)
    silk_refs(board)
    pcbnew.SaveBoard(out, board)
    txt = open(out).read()
    open(out, "w").write(txt.replace('(paper "A4")', '(paper "A3")', 1))
    print(f"{out}: {len(placed)} placed, {len(missing)} missing")


if __name__ == "__main__":
    main()
