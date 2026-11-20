#!/usr/bin/env python3
"""Pin-order check: the UNMOVED KiCad base footprints with the Proteus renumbering, fitted onto
the IPC pads (playbook Phase 2, step 2). A small residual confirms that the Proteus pin ids sit on
the pads the renumbering says; a residual of a pad pitch or more means the ids are on other pads.

Inline and two-pad parts always fit (a 180 deg turn reverses the pad order), so for them the
orientation of the body marker decides: the fitted KiCad graphics (band, flat side, tab, '+',
pin-1 pad) are drawn over the Proteus silk with --render (reports/pin_order/<refdes>.png) and
were compared by eye (STATUS.md "Phase 2 - pin order").

For the octal socket the KiCad footprint (Valve:Valve_Octal) is on a 2.54 mm grid, not on the
Proteus 17.20 mm pitch circle, so the residual is never small; the chirality test compares the
unmirrored fit (KiCad = standard octal numbering, clockwise seen from the pin side = solder side
of a top-mounted socket) with the mirrored one, and also fits an ideal standard octal on the
Proteus pitch circle.

Phase 5 (user decision 2026-11-20: the sockets are on the BOTTOM side): the project footprint
tube_power_amp:Valve_Octal_Belton_PCD17.20mm has the standard octal numbering in its own view
(fits the ideal standard octal unmirrored, not mirrored), fits the IPC pads only mirrored (so
check_footprints places it on the bottom), reports/footprint_fit.csv has U6-U9 on the bottom and
every other part on top, and the board has U6-U9 on B.Cu and every other footprint on F.Cu.

Usage: tools/p2k/bin/kipy tools/check_pin_order.py [--render]   (python3 works without --render;
       --render needs matplotlib, e.g. the system python3)
Exit 1 when a result differs from EXPECT (so a changed footprint or renumbering is noticed).
"""
import csv
import glob
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools", "p2k"))
os.chdir(ROOT)
from p2k import fpgeom, pcb, sexpr  # noqa: E402
from p2k.footprints import footprint_path  # noqa: E402

OCTAL = "tube_power_amp:Valve_Octal_Belton_PCD17.20mm"
OCTALS = "U6 U7 U8 U9".split()

# refdes group -> (KiCad base footprint, Proteus renumbering of the base pads)
CHECKS = [
    ("Q1", "Package_TO_SOT_THT:TO-220-3_Vertical", {}),
    ("Q2 Q3", "Package_TO_SOT_THT:TO-92_Inline_Wide", {}),
    ("D1 D2 D3 D4 D5", "Diode_THT:D_DO-41_SOD81_P10.16mm_Horizontal", {"1": "K", "2": "A"}),
    ("C5", "Capacitor_THT:CP_Radial_D10.0mm_P5.00mm", {"1": "+", "2": "-"}),
    ("C6", "Capacitor_THT:CP_Radial_D10.0mm_P5.00mm", {"1": "+", "2": "-"}),
    ("U6 U7 U8 U9", "Valve:Valve_Octal", {}),
]
# expected best fit per group: (mirror, residual upper bound mm)
EXPECT = {
    "Q1": (False, 0.01),
    "Q2 Q3": (False, 0.51),        # TO-92_Inline_Wide is P2.54, Proteus P2.032: 0.508 at the outer pads
    "D1 D2 D3 D4 D5": (False, 0.01),
    "C5": (False, 0.01),
    "C6": (False, 0.05),           # P5.00 vs P5.08
    "U6 U7 U8 U9": (True, 2.3),    # only the MIRRORED KiCad octal matches the Proteus numbering
}


def base_pads(fpid, ren):
    pads = fpgeom.load_footprint(footprint_path(fpid))
    out = []
    for p in pads:
        if p["num"] == "":
            continue   # Valve_Octal centre hole
        q = dict(p)
        q["num"] = ren.get(p["num"], p["num"])
        out.append(q)
    return out


def ideal_octal(r=8.6):
    """Standard octal numbering in KiCad's top view (Y up): counter-clockwise from the top,
    i.e. clockwise seen from the pin / solder side; pad 1 at -45 deg."""
    return [{"num": str(k + 1), "x": r * math.cos(math.radians(-45 + 45 * k)),
             "y": r * math.sin(math.radians(-45 + 45 * k)), "w": 3.81, "h": 3.81, "rot": 0.0, "drill": 1.6,
             "kind": "thru_hole", "shape": "circle"} for k in range(8)]


def graphics(fpid):
    """F.SilkS / F.Fab polylines of a footprint (footprint frame, Y up)."""
    node = sexpr.load(footprint_path(fpid))
    lines = []

    def xy(n):
        return float(n[1]), -float(n[2])
    for g in node:
        if not isinstance(g, list) or not g or str(g[0]) not in ("fp_line", "fp_rect", "fp_circle", "fp_arc", "fp_poly"):
            continue
        layer = sexpr.find(g, "layer")
        if layer is None or layer[1] not in ("F.SilkS", "F.Fab"):
            continue
        kind = str(g[0])
        if kind == "fp_line":
            lines.append([xy(sexpr.find(g, "start")), xy(sexpr.find(g, "end"))])
        elif kind == "fp_rect":
            (x0, y0), (x1, y1) = xy(sexpr.find(g, "start")), xy(sexpr.find(g, "end"))
            lines.append([(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)])
        elif kind == "fp_circle":
            (cx, cy), (ex, ey) = xy(sexpr.find(g, "center")), xy(sexpr.find(g, "end"))
            r = math.hypot(ex - cx, ey - cy)
            lines.append([(cx + r * math.cos(t / 20 * math.pi), cy + r * math.sin(t / 20 * math.pi)) for t in range(41)])
        elif kind == "fp_arc":
            a, m, b = xy(sexpr.find(g, "start")), xy(sexpr.find(g, "mid")), xy(sexpr.find(g, "end"))
            lines.append(_arc(a, m, b))
        else:
            pts = [xy(p) for p in sexpr.find(g, "pts")[1:]]
            lines.append(pts + pts[:1])
    return lines


def _arc(a, m, b):
    ax, ay = a
    bx, by = m
    cx, cy = b
    d = 2 * (ax * (by - cy) + bx * (cy - ay) + cx * (ay - by))
    if abs(d) < 1e-12:
        return [a, m, b]
    ux = ((ax * ax + ay * ay) * (by - cy) + (bx * bx + by * by) * (cy - ay) + (cx * cx + cy * cy) * (ay - by)) / d
    uy = ((ax * ax + ay * ay) * (cx - bx) + (bx * bx + by * by) * (ax - cx) + (cx * cx + cy * cy) * (bx - ax)) / d
    r = math.hypot(ax - ux, ay - uy)
    t0, tm, t1 = (math.atan2(p[1] - uy, p[0] - ux) for p in (a, m, b))

    def ccw(s, e):
        return (e - s) % (2 * math.pi)
    if ccw(t0, tm) <= ccw(t0, t1):
        span = ccw(t0, t1)
    else:
        span = -ccw(t1, t0)
    return [(ux + r * math.cos(t0 + span * k / 24), uy + r * math.sin(t0 + span * k / 24)) for k in range(25)]


def to_board(fr, x, y):
    a = math.radians(fr["angle"])
    x = -x if fr["mirror"] else x
    return fr["tx"] + math.cos(a) * x - math.sin(a) * y, fr["ty"] + math.sin(a) * x + math.cos(a) * y


def render(ref, fpid, fr, ipc_pads, out):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Circle
    from p2k import gerber
    silk = gerber.parse(glob.glob("source/cadcam/*Top Silk Screen.GBR")[0]).of(gerber.Draw)
    xs = [p["x_mm"] for p in ipc_pads]
    ys = [p["y_mm"] for p in ipc_pads]
    m = 16 if len(ipc_pads) == 8 else 8
    box = (min(xs) - m, max(xs) + m, min(ys) - m, max(ys) + m)
    fig, ax = plt.subplots(figsize=(6, 6))
    for d in silk:
        if box[0] <= d.x1 <= box[1] and box[2] <= d.y1 <= box[3]:
            ax.plot([d.x1, d.x2], [d.y1, d.y2], color="k", lw=1.0)
    for p in ipc_pads:
        ax.add_patch(Circle((p["x_mm"], p["y_mm"]), p["pad_w"] / 2, color="orange", alpha=0.6))
        ax.text(p["x_mm"], p["y_mm"], p["pin"], ha="center", va="center", fontsize=9, color="b")
    for line in graphics(fpid):
        pts = [to_board(fr, x, y) for x, y in line]
        ax.plot([p[0] for p in pts], [p[1] for p in pts], color="r", lw=0.8)
    for num, f, q, _ in fr["pads"]:
        bx, by = to_board(fr, f["x"], f["y"])
        ax.add_patch(Circle((bx, by), 0.35, color="r"))
        if f is fr["pads"][0][1] or num in ("1", "K", "+"):
            ax.text(bx + 0.6, by + 0.6, f"KiCad {num}", fontsize=7, color="r")
    ax.set_title(f"{ref}: black = Proteus silk, orange = IPC pads (pin ids)\n"
                 f"red = unmoved {fpid.split(':')[1]} fitted ({'mirrored, ' if fr['mirror'] else ''}"
                 f"{fr['angle']:g} deg, res {fr['max_res']:.3f} mm)", fontsize=7)
    ax.set_aspect("equal")
    ax.set_xlim(box[0], box[1])
    ax.set_ylim(box[2], box[3])
    fig.savefig(out, dpi=120, bbox_inches="tight")
    plt.close(fig)


def bottom_side_octal(ipc):
    """Phase 5: the octal footprint is the standard octal and U6-U9 are on the bottom side."""
    bad = []
    fp = fpgeom.load_footprint(footprint_path(OCTAL))
    target = [dict(p, pin=p["num"], x_mm=p["x"], y_mm=p["y"]) for p in ideal_octal()]   # as IPC pads
    ideal = {m: fpgeom.fit(fp, target, m)["max_res"] for m in (False, True)}
    on_ipc = {m: max(fpgeom.fit(fp, ipc[r], m)["max_res"] for r in OCTALS) for m in (False, True)}
    name = OCTAL.split(":")[1]
    print(f"{'(footprint)':16s} {name + ' vs ideal octal':44s} {ideal[False]:7.3f}{'':11s} "
          f"{ideal[True]:7.3f}{'':11s}  {'unmirrored' if ideal[False] < ideal[True] else 'mirrored'}")
    print(f"{'U6 U7 U8 U9':16s} {name + ' (project)':44s} {on_ipc[False]:7.3f}{'':11s} "
          f"{on_ipc[True]:7.3f}{'':11s}  {'mirrored = bottom side' if on_ipc[True] < on_ipc[False] else 'unmirrored'}")
    if not (ideal[False] < 0.01 < ideal[True]):
        bad.append(f"{name}: expected the standard octal numbering in the footprint's own view")
    if not (on_ipc[True] < 0.01 < on_ipc[False]):
        bad.append(f"{name}: expected to fit the IPC pads only mirrored (bottom side)")
    with open("reports/footprint_fit.csv") as f:
        rows = list(csv.DictReader(l for l in f if not l.startswith("# ")))
    wrong = [r["refdes"] for r in rows if (r["side"] == "bottom") != (r["refdes"] in OCTALS)]
    if wrong:
        bad.append(f"reports/footprint_fit.csv: wrong side for {wrong} (bottom = exactly {OCTALS})")
    layers = {}
    BOARD = os.path.relpath(pcb.board_file())   # kicad/tube_power_amp.kicad_pcb (P2K_PCB overrides)
    for node in sexpr.find_all(sexpr.load(BOARD), "footprint"):
        ref = next((p[2] for p in sexpr.find_all(node, "property") if p[1] == "Reference"), "")
        layers[ref] = sexpr.find(node, "layer")[1]
    wrong = sorted(r for r, l in layers.items() if l != ("B.Cu" if r in OCTALS else "F.Cu"))
    if wrong or not set(OCTALS) <= set(layers):
        bad.append(f"{BOARD}: wrong layer for {wrong or OCTALS} (B.Cu = exactly {OCTALS})")
    else:
        print(f"{'':16s} footprint_fit.csv and board: U6-U9 bottom (B.Cu), the other {len(layers) - 4} footprints top")
    return bad


def main():
    do_render = "--render" in sys.argv[1:]
    ipc = fpgeom.ipc_pads_by_refdes()
    bad = []
    print(f"{'parts':16s} {'KiCad base (unmoved)':44s} {'unmirrored':>18s} {'mirrored':>18s}  best")
    for refs, fpid, ren in CHECKS:
        fp = base_pads(fpid, ren)
        worst = {False: (0.0, None), True: (0.0, None)}
        for ref in refs.split():
            for mir in (False, True):
                r = fpgeom.fit(fp, ipc[ref], mir)
                if r["missing"] or r["extra"] or r["count_diff"]:
                    bad.append(f"{ref}: pad numbers differ from {fpid}: {r['missing']} {r['extra']} {r['count_diff']}")
                if worst[mir][1] is None or r["max_res"] > worst[mir][0]:
                    worst[mir] = (r["max_res"], r)
            if do_render:
                os.makedirs("reports/pin_order", exist_ok=True)
                best = min((fpgeom.fit(fp, ipc[ref], m) for m in (False, True)), key=lambda r: r["max_res"])
                render(ref, fpid, best, ipc[ref], f"reports/pin_order/{ref}.png")
        u, m = worst[False], worst[True]
        best = u[0] <= m[0]
        best_mir = not best
        cell = lambda w: f"{w[0]:7.3f} @{w[1]['angle']:5g}"  # noqa: E731
        print(f"{refs:16s} {fpid:44s} {cell(u):>18s} {cell(m):>18s}  {'mirrored' if best_mir else 'unmirrored'}")
        want_mir, lim = EXPECT[refs]
        res = m[0] if best_mir else u[0]
        if best_mir != want_mir or res > lim:
            bad.append(f"{refs}: best fit {'mirrored' if best_mir else 'unmirrored'} {res:.3f} mm, expected "
                       f"{'mirrored' if want_mir else 'unmirrored'} <= {lim}")
    # ideal standard octal on the Proteus pitch circle
    oct_res = {}
    for mir in (False, True):
        oct_res[mir] = max(fpgeom.fit(ideal_octal(), ipc[r], mir)["max_res"] for r in "U6 U7 U8 U9".split())
    print(f"{'U6 U7 U8 U9':16s} {'ideal standard octal, PCD 17.20 mm':44s} {oct_res[False]:7.3f}{'':11s} "
          f"{oct_res[True]:7.3f}{'':11s}  {'mirrored' if oct_res[True] < oct_res[False] else 'unmirrored'}")
    if not (oct_res[True] < 0.01 < oct_res[False]):
        bad.append("ideal octal: expected only the mirrored standard octal to fit")
    bad += bottom_side_octal(ipc)
    for b in bad:
        print("check_pin_order: ERROR " + b)
    print("check_pin_order: " + ("FAILED" if bad else "OK (results as recorded in STATUS.md)"))
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
