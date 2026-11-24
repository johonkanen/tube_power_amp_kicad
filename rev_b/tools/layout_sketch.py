#!/usr/bin/env python3
"""Layout sketch of the power amp rev B: interfaces to the neighbouring boards (2026-11-24).

Draws, in the chassis frame (plan from above), the outline, holes, sockets, every connector and tab
that leaves the board with its footprint size and pin 1, the cable paths, block zones and keep-outs.
Positions come from tools/layout_frame.py. Output: rev_b/docs/layout_sketch.png (+ an east-end zoom).
Run: python3 rev_b/tools/layout_sketch.py
"""
import math
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt                      # noqa: E402
from matplotlib.patches import Circle, Polygon, Rectangle   # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import layout_frame as F                             # noqa: E402

RB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(RB, "docs")


def rect(ax, x0, y0, x1, y1, **kw):
    ax.add_patch(Rectangle((x0, y0), x1 - x0, y1 - y0, **kw))


def label(ax, x, y, s, size=5.5, **kw):
    ax.text(x, y, s, fontsize=size, ha=kw.pop("ha", "center"), va=kw.pop("va", "center"), **kw)


def idc_pins(pin1, n, dx=-2.54):
    """Pins of a 2-row IDC header whose long axis runs along x (step dx), odd row at pin1's y."""
    x, y = pin1
    return {k: (x + dx * ((k - 1) // 2), y + (0 if k % 2 else 2.54)) for k in range(1, n + 1)}


def cool_ymax(x, r=40.0, cap=145.0):
    """Largest y in the front band that is still >= r from every socket centre."""
    y = cap
    for sx, sy in F.SOCKETS.values():
        dx = abs(x - sx)
        if dx < r:
            y = min(y, sy - math.sqrt(r * r - dx * dx))
    return y


def cool_area(x0=280.33, x1=519.09, r=40.0, cap=145.0, y0=127.05):
    n = int((x1 - x0) / 0.1)
    return sum(max(0.0, cool_ymax(x0 + (i + 0.5) * 0.1, r, cap) - y0) * 0.1 for i in range(n))


def draw(ax, zoom=None):
    x0, y0, x1, y1 = F.OUTLINE
    # neighbours
    ax.add_patch(Polygon(F.HV_OUTLINE, closed=True, fc="#f3e6d0", ec="#a0703a", lw=0.8))
    label(ax, 545, 190, "HV supplies rev 3\n(arm x 525-560)", 6)
    rect(ax, 426, 30, 552, 122, fc="#e3ecf7", ec="#4a6fa5", lw=0.8)
    label(ax, 470, 100, "control board (x 426-552, y 30-122)", 6)
    rect(ax, 53, 104, 278.7, 176, fc="#e8f3e3", ec="#4c8a3c", lw=0.8)
    label(ax, 262, 112, "PI + FX\n(1.6 mm gap)", 6)
    rect(ax, 276, 195.7, 322, 210, fc="#efe3f3", ec="#80509a", lw=0.8)
    rect(ax, 160, 179.7, 276, 210, fc="#efe3f3", ec="#80509a", lw=0.8)
    label(ax, 300, 203, "rear I/O main board (SMD end), 8.3 mm gap", 5.5)
    ax.plot([0, 680], [210, 210], color="k", lw=1.2)
    label(ax, 450, 207.5, "rear panel (inner face y 210)", 5.5)
    rect(ax, 331.4, 52, 415.5, 128.1, fc="none", ec="#999999", lw=0.7, ls="--")
    label(ax, 373, 85, "output transformer 1650TA on top (bolt pattern)", 5.5, color="#666666")
    for (x, y) in F.OT_LEAD_HOLES:
        ax.add_patch(Circle((x, y), 7.5, fc="none", ec="#b03030", lw=0.8))
    label(ax, 415.5, 81, "OT lead hole 15 mm\n(primary assumed)", 5, color="#b03030")
    for (x, y) in F.OT_SCREWS:
        ax.add_patch(Circle((x, y), 1.75, fc="#999999", ec="none"))
        if y > 120:
            ax.add_patch(Circle((x, y), 6.3, fc="none", ec="#b03030", lw=0.5, ls=":"))
    # board
    rect(ax, x0, y0, x1, y1, fc="#fbfbf3", ec="k", lw=1.4)
    # block zones
    zones = [
        (281, 157, 329.5, 187, "#fff2cc", "tube V1 (side A)"), (330, 157, 373, 187, "#fff2cc", "tube V2 (side A)"),
        (418, 157, 461, 187, "#fff2cc", "tube V3 (side B)"), (462, 157, 509.5, 187, "#fff2cc", "tube V4 (side B)"),
        (373.5, 157, 417.5, 187, "#fde9d9", "gap: heater entry J103,\nscreen R overflow"),
        (300, 127.5, 382, 146, "#e2f0d9", "drive entry, coupling caps A,\nbias channels (300 V parts >= 25 mm)"),
        (469.2, 127.5, 518.6, 147, "#e4dfec", "digital island (DGND)"),
    ]
    for zx0, zy0, zx1, zy1, c, s in zones:
        rect(ax, zx0, zy0, zx1, zy1, fc=c, ec="#808080", lw=0.4, alpha=0.9)
        label(ax, (zx0 + zx1) / 2, (zy0 + zy1) / 2 + (6 if "tube" in s else 0), s, 5)
    # bias / reference strip: the front band clipped by the 40 mm circles round the socket centres
    poly = [(430.0, 127.5)] + [(x, cool_ymax(x)) for x in [430 + 0.5 * i for i in range(121)]] + [(490.0, 127.5)]
    ax.add_patch(Polygon(poly, closed=True, fc="#d9e1f2", ec="#3050c0", lw=0.5, alpha=0.9))
    label(ax, 452, 130.5, ">= 40 mm strip\n(reference, DAC, ADC)", 4.8, color="#203080")
    # HV 1.25 kV corridor (OT_A / OT_B on B, plate pins at the front) and the J104 cluster, with 6.3 mm keep-outs
    rect(ax, 290, 149.5, 505, 157.0, fc="#f4cccc", ec="#c00000", lw=0.6, alpha=0.8)
    rect(ax, 290 - 6.3, 149.5 - 6.3, 505 + 6.3, 157.0 + 6.3, fc="none", ec="#c00000", lw=0.5, ls="--")
    label(ax, 340, 153.2, "1.25 kV: OT_A (B layer, 6.3 mm keep-out dashed)", 5, color="#900000")
    label(ax, 465, 153.2, "1.25 kV: OT_B", 5, color="#900000")
    rect(ax, 383, 127.5, 427, 149.5, fc="#f4cccc", ec="#c00000", lw=0.6, alpha=0.8)
    label(ax, 405, 141.5, "J104 + clamps\n(RGP02, 2x P6KE350CA / side)", 5, color="#900000")
    # 440 V runs from the east tabs
    ax.plot([514.5, 509, 509, 405, 405], [161, 161, 153.2, 153.2, 137.5], color="#e06000", lw=2.0, alpha=0.7)
    label(ax, 440, 147.0, "V_ANODE 440 V on F, stacked over OT_B (B) to J104-3 OT_CT", 4.8, color="#a04000")
    # heater pair along the rear edge
    ax.plot([290, 500], [184.8, 184.8], color="#7030a0", lw=2.5, alpha=0.5)
    label(ax, 340, 186.3, "heater pair HTR1 F / HTR2 B stacked, 3.2 A each way", 4.8, color="#5a2080")
    # star
    ax.add_patch(Circle((514.5, 170.5), 3.2, fc="none", ec="#007000", lw=1.0))
    label(ax, 503, 166, "star\n(GND_PWR)", 5, color="#006000")
    # precision circles 40 mm / 25 mm
    for name, (sx, sy) in F.SOCKETS.items():
        ax.add_patch(Circle((sx, sy), 40, fc="none", ec="#3050c0", lw=0.4, ls=":"))
        ax.add_patch(Circle((sx, sy), 25, fc="none", ec="#40a040", lw=0.4, ls=":"))
    # sockets
    for name, (sx, sy) in F.SOCKETS.items():
        ax.add_patch(Circle((sx, sy), 15.0, fc="#ffffff", ec="#404040", lw=0.8))
        for n in range(1, 9):
            a = math.radians(F.PIN3_ANGLE + (n - 3) * 45)
            px, py = sx + F.PIN_CIRCLE_R * math.cos(a), sy + F.PIN_CIRCLE_R * math.sin(a)
            c = {3: "#c00000", 4: "#e06000", 5: "#2060c0", 2: "#7030a0", 7: "#7030a0", 1: "#008000", 8: "#008000"}.get(n, "#808080")
            ax.add_patch(Circle((px, py), 1.905, fc=c, ec="none"))
            label(ax, px, py, str(n), 4, color="white")
        label(ax, sx, sy, name, 7, weight="bold")
    # holes
    for (x, y) in F.OLD_SOCKET_HOLES:
        ax.add_patch(Circle((x, y), 1.75, fc="none", ec="#606060", lw=0.5))
    for (x, y, d) in F.BIAS_HOLES:
        ax.add_patch(Circle((x, y), d / 2, fc="none", ec="#606060", lw=0.5))
    label(ax, 400, 198.6, "old bias pot / test point holes (y 198.1): off the board, unused in rev B", 5, color="#606060")
    for hs, col in ((F.HOLES_KEPT, "k"), (F.HOLES_REAR_PREFERRED, "#0050a0")):
        for h, (x, y) in hs.items():
            ax.add_patch(Circle((x, y), 1.6, fc="white", ec=col, lw=0.9))
            ax.add_patch(Circle((x, y), 4.0, fc="none", ec=col, lw=0.4, ls="--"))
            label(ax, x, y - 5.2, h, 5, color=col)
    for h, (x, y) in F.HOLES_REAR_ALT.items():
        ax.plot([x - 1.2, x + 1.2], [y - 1.2, y + 1.2], color="#a0a0a0", lw=0.6)
        ax.plot([x - 1.2, x + 1.2], [y + 1.2, y - 1.2], color="#a0a0a0", lw=0.6)
    # connectors
    for ref, c in F.CONNECTORS.items():
        if "body" in c:
            bx0, by0, bx1, by1 = c["body"]
            rect(ax, bx0, by0, bx1, by1, fc="#c9c9c9", ec="k", lw=0.7)
            pins = c.get("pins")
            if not pins and ref in ("J501", "J502"):
                pins = idc_pins(c["pin1"], 14 if ref == "J501" else 10)
            if not pins and ref == "J503":
                pins = {1: c["pin1"], 2: (c["pin1"][0] + 2.54, c["pin1"][1])}
            for k, (px, py) in pins.items():
                ax.add_patch(Rectangle((px - 0.7, py - 0.7), 1.4, 1.4, fc="#c00000" if k == 1 else "#303030", ec="none"))
            label(ax, (bx0 + bx1) / 2, by1 + 1.6, f"{ref} {c['cable']}", 5.5, weight="bold")
        else:
            w, h = F.RECEPTACLE[c["width"]]
            for k, (net, tx, ty) in c["tabs"].items():
                ew, eh = (w, h) if c["blade"] == "x" else (h, w)
                rect(ax, tx - ew / 2, ty - eh / 2, tx + ew / 2, ty + eh / 2, fc="#ffe699", ec="k", lw=0.6)
                for d in (-2.5, 2.5):
                    px, py = (tx + d, ty) if c["blade"] == "x" else (tx, ty + d)
                    ax.add_patch(Circle((px, py), 1.3, fc="#c00000" if k == 1 else "#303030", ec="none"))
                label(ax, tx, ty, f"{k}", 4.5, color="white")
                label(ax, tx, ty + eh / 2 + 1.3 if c["blade"] == "x" else ty, net if c["blade"] == "x" else "",
                      4.5)
            if c["blade"] == "y":
                for k, (net, tx, ty) in c["tabs"].items():
                    label(ax, tx - 8.8, ty, f"{ref}-{k} {net}", 4.5, ha="center")
            else:
                xs = [t[1] for t in c["tabs"].values()]
                label(ax, sum(xs) / len(xs), list(c["tabs"].values())[0][2] - 5.6, f"{ref} {c['cable']}", 5.5, weight="bold")
    # control board headers (as placed, and shifted by the proposal)
    for j, d in F.CTRL_J.items():
        for shift, alpha, ls in ((0.0, 0.35, "-"), (F.CTRL_SHIFT_PROPOSED if j in ("J4", "J5") else None, 1.0, "-")):
            if shift is None:
                continue
            p1 = (d["pin1"][0] + shift, d["pin1"][1])
            pins = idc_pins(p1, d["n"])
            xs = [p[0] for p in pins.values()]
            rect(ax, min(xs) - 5.6, p1[1] - 4.68, max(xs) + 5.6, p1[1] + 2.54 + 3.68, fc="#c9c9c9", ec="k", lw=0.5,
                 alpha=alpha, ls=ls)
            for k, (px, py) in pins.items():
                ax.add_patch(Rectangle((px - 0.6, py - 0.6), 1.2, 1.2, fc="#c00000" if k == 1 else "#303030", ec="none",
                                       alpha=alpha))
        label(ax, d["pin1"][0] - 5, d["pin1"][1] - 6.5, f"ctrl {j}" + (" (faint: as placed)" if j != "J7" else ""), 4.5)
    # cables
    for j, ref in (("J4", "J501"), ("J5", "J502")):
        c = F.CONNECTORS[ref]
        n = F.CTRL_J[j]["n"]
        xa = c["pin1"][0] + 0.635
        xb = xa - (n - 1) * 1.27
        ax.add_patch(Polygon([(xa, 116.5), (xb, 116.5), (xb, c["pin1"][1] + 0.7), (xa, c["pin1"][1] + 0.7)], closed=True, fc="#9fc5e8", ec="#3d85c6",
                             lw=0.5, alpha=0.6))
    label(ax, 497, 124.5, "W14 / W15 flat, 0 folds", 4.8, color="#1f4e79")
    # W16 twisted pair
    ax.plot([492.3, 500, 522, 556, 556, 565.5], [146.5, 150.5, 141, 141, 52, 52], color="#38761d", lw=1.0, ls="-.")
    label(ax, 566, 100, "W16 pair through the\narm corridor, then along\nthe control board's\neast edge (~0.2 m)", 4.8,
          color="#38761d", ha="left")
    # HV jumpers to the arm's tabs
    for (sx, sy), (dx, dy) in (((514.5, 151.5), (532, 155)), ((514.5, 161), (532, 172)), ((514.5, 170.5), (532, 184))):
        ax.plot([sx, dx], [sy, dy], color="#e06000", lw=1.2)
    for (hx, hy, hw, hh) in F.HV_TABS.values():
        rect(ax, hx, hy, hx + hw, hy + hh, fc="#ffe699", ec="#a0703a", lw=0.6)
    # OT primary leads
    for tx in (393.0, 405.0, 417.0):
        ax.plot([415.5, tx], [90.1, 130.75], color="#b03030", lw=0.9)
    # W24
    ax.annotate("", xy=(262, 143.5), xytext=(286.5, 143.5), arrowprops=dict(arrowstyle="->", color="#4c8a3c", lw=1.0))
    label(ax, 270, 147, "W24 down, west\nto PI + FX J201", 4.8, color="#2e5e22")
    # keep-outs
    rect(ax, x0, y1, x1, 195.7, fc="none", ec="#80509a", hatch="////", lw=0.0, alpha=0.5)
    label(ax, 450, 191.5, "nothing past the rear edge, whole length: W19 runs behind (rear I/O 8.3 mm at x 280-322)", 5,
          color="#5a2a70")
    rect(ax, x1, 127, 525, 200, fc="none", ec="#a0703a", hatch="\\\\\\\\", lw=0.0, alpha=0.6)
    rect(ax, 525, 127, 560, 147, fc="none", ec="#38761d", hatch="....", lw=0.4, alpha=0.7)
    label(ax, 542.5, 137, "ribbon corridor\ny 127-147", 4.8, color="#38761d")
    # arrows for the tube PSU leads
    ax.annotate("from tube PSU (harness)", xy=(395.7, 177.3), xytext=(440, 205), fontsize=4.8, color="#5a2080",
                arrowprops=dict(arrowstyle="->", color="#7030a0", lw=0.7))
    ax.annotate("-80 V from tube PSU", xy=(477.0, 150.3), xytext=(440, 120.5), fontsize=4.8, color="#404040",
                arrowprops=dict(arrowstyle="->", color="#404040", lw=0.7))
    ax.set_aspect("equal")
    if zoom:
        ax.set_xlim(zoom[0], zoom[2])
        ax.set_ylim(zoom[1], zoom[3])
    else:
        ax.set_xlim(250, 575)
        ax.set_ylim(80, 212)
    ax.set_xlabel("chassis x (mm)")
    ax.set_ylabel("chassis y (mm, front panel = 0)")
    ax.grid(True, lw=0.2, alpha=0.5)


def main():
    os.makedirs(OUT, exist_ok=True)
    fig, ax = plt.subplots(figsize=(16, 7.5), dpi=200)
    draw(ax)
    ax.set_title("Power amp rev B, layout sketch: interfaces (2026-11-24). Plan from above (chassis frame); "
                 "board 15 mm below the plate, components down; red pad = pin 1", fontsize=9)
    fig.tight_layout()
    p = os.path.join(OUT, "layout_sketch.png")
    fig.savefig(p)
    plt.close(fig)
    fig, ax = plt.subplots(figsize=(12, 9), dpi=200)
    draw(ax, zoom=(462, 108, 572, 195))
    ax.set_title("East end: W14 / W15 (control board J4 / J5 shifted -8.90 mm), tabs to the HV arm, W16, -80 V", fontsize=9)
    fig.tight_layout()
    p2 = os.path.join(OUT, "layout_sketch_east.png")
    fig.savefig(p2)
    plt.close(fig)
    print(p, p2)
    for r in (40.0, 35.0, 30.0):
        print(f"front-band area >= {r:.0f} mm from every socket centre (y <= 145): {cool_area(r=r):.0f} mm2; "
              f"x 430-470 only: {cool_area(430, 470, r):.0f} mm2")


if __name__ == "__main__":
    main()
