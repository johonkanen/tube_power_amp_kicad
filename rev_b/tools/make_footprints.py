#!/usr/bin/env python3
"""Board-local footprints for the power amp rev B (lib/tube_power_amp_revb.pretty) and the
project's fp-lib-table. Everything else comes from KiCad's stock libraries.

- Valve_Octal_Belton_PCD17.20mm, R_Axial_Power_L25.0mm_W6.4mm_P30.00mm: copied unchanged from the
  rev A conversion (lib/tube_power_amp.pretty at the repo root, which is frozen and only read
  here), so the sockets and the 5 W resistors keep the as-built pad pattern.
- BladeTab_*: (layout 2026-11-24, replace the PLACEHOLDERs): interfaces.md 2 / 4.1, "PCB blade tab, 2 legs
  on 5.00 mm, 1.4 mm drill" (DEFINED), one pad number per tab (both legs), tabs 15.24 mm apart.
  PLACEHOLDER: the tab part, its leg size and the spacing that the insulated receptacles need are
  chosen at layout; only the leg pattern is the contract.
Run: python3 rev_b/tools/make_footprints.py
"""
import os
import shutil

RB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REVA = os.path.join(RB, "..", "lib", "tube_power_amp.pretty")
OUT = os.path.join(RB, "lib", "tube_power_amp_revb.pretty")
COPY = ("Valve_Octal_Belton_PCD17.20mm", "R_Axial_Power_L25.0mm_W6.4mm_P30.00mm")
PITCH = 15.24


# Receptacle envelopes (plan): fully insulated push-on receptacles, along the blade x across it (mm).
ENVELOPE = {4.8: (8.0, 6.5), 6.3: (9.5, 7.5)}


def tab_fp(name, width, tabs, descr):
    """tabs = [(pad number, x, y)]: each tab is a blade along local x with its 2 legs at x +- 2.5 (5.00 mm,
    1.4 mm holes: interfaces.md 4.1, DEFINED). Courtyard / Fab = the insulated receptacle's envelope."""
    ew, eh = ENVELOPE[width]
    pads, gfx = [], []
    for num, x, y in tabs:
        for dx in (-2.5, 2.5):
            pads.append(f'\t(pad "{num}" thru_hole circle (at {x + dx:.2f} {y:.2f}) (size 2.6 2.6) (drill 1.4) '
                        f'(layers "*.Cu" "*.Mask"))')
        gfx.append(f'\t(fp_rect (start {x - width / 2:.2f} {y - 0.4:.2f}) (end {x + width / 2:.2f} {y + 0.4:.2f}) '
                   f'(stroke (width 0.12) (type solid)) (fill no) (layer "F.SilkS"))')
        for lay, w in (("F.Fab", 0.1), ("F.CrtYd", 0.05)):
            gfx.append(f'\t(fp_rect (start {x - ew / 2:.2f} {y - eh / 2:.2f}) (end {x + ew / 2:.2f} {y + eh / 2:.2f}) '
                       f'(stroke (width {w}) (type solid)) (fill no) (layer "{lay}"))')
        gfx.append(f'\t(fp_text user "{num}" (at {x:.2f} {y - eh / 2 - 0.9:.2f}) (layer "F.SilkS") '
                   f'(effects (font (size 1 1) (thickness 0.15))))')
    ys = [y for _, _, y in tabs]
    body = "\n".join([
        f'(footprint "{name}"', '\t(version 20260206)', '\t(generator "make_footprints")', '\t(layer "F.Cu")',
        f'\t(descr "{descr}")',
        f'\t(property "Reference" "REF**" (at 0 {min(ys) - eh / 2 - 2.5:.2f} 0) (layer "F.SilkS") (effects (font (size 1 1) (thickness 0.15))))',
        f'\t(property "Value" "{name}" (at 0 {max(ys) + eh / 2 + 1.5:.2f} 0) (layer "F.Fab") (effects (font (size 1 1) (thickness 0.15))))',
        '\t(attr through_hole)', *gfx, *pads, ')'])
    open(os.path.join(OUT, name + ".kicad_mod"), "w").write(body + "\n")


def tabs():
    d = "PCB blade tab(s), 2 legs on 5.00 mm, 1.4 mm holes (interfaces.md 4.1); courtyard = insulated receptacle envelope"
    tab_fp("BladeTab_4.8mm_x1", 4.8, [("1", 0, 0)], "4.8 mm " + d)
    tab_fp("BladeTab_4.8mm_x2_P9.50mm", 4.8, [("1", 0, 0), ("2", 0, 9.5)], "2x 4.8 mm, tabs on 9.5 mm, " + d)
    # J101: V_ANODE and GND_PWR in line (blades along the row), 10.2 mm apart: 2.6 mm between the legs
    tab_fp("BladeTab_4.8mm_x2_P10.20mm_Inline", 4.8, [("1", 0, 0), ("2", 10.2, 0)], "2x 4.8 mm in line on 10.2 mm, " + d)
    tab_fp("BladeTab_6.3mm_x2_P11.50mm", 6.3, [("1", 0, 0), ("2", 11.5, 0)], "2x 6.3 mm side by side on 11.5 mm, " + d)
    # J104: OT_A (1) / OT_CT (3) / OT_B (2) in a row on 16 mm, blades along the row: 9.4 mm between the
    # nearest legs of neighbouring tabs (>= 6.3 mm, the 1.25 kV rule)
    # J104: OT_A (1) / OT_CT (3) / OT_B (2) in a row, 26.4 mm apart, OT_CT 6.5 mm in front of the row (layout 2026-11-24: each tab
    # sits in front of its clamp group; >= 6.3 mm everywhere, the 1.25 kV rule)
    tab_fp("BladeTab_4.8mm_x3_OT", 4.8, [("1", 0, 0), ("3", 26.4, -6.5), ("2", 52.8, 0)],
           "3x 4.8 mm OT_A / OT_CT / OT_B (0 / 26.4 / 52.8 mm, OT_CT 6.5 mm forward), " + d)


def standing_tight():
    """R111: KiCad's standing 5 W footprint with a tighter courtyard (the body circle at pad 1 and the pad 2
    lead), so a pad under the bent lead's top run is not reported (layout 2026-11-24)."""
    stock = os.path.join(os.environ.get("KICAD_FOOTPRINTS", "/tmp/.mount_kicadremp17350511091871881925/share/kicad/footprints"),
                         "Resistor_THT.pretty", "R_Axial_Power_L25.0mm_W9.0mm_P10.16mm_Vertical.kicad_mod")
    name = "R_Axial_Power_L25.0mm_W9.0mm_P10.16mm_Vertical_Tight"
    s = open(stock).read().replace('"R_Axial_Power_L25.0mm_W9.0mm_P10.16mm_Vertical"', f'"{name}"', 1)
    lines = s.split("\n")
    blocks, cur = [], []
    for ln in lines[1:-2]:
        if ln.startswith("\t(") and cur:
            blocks.append(cur)
            cur = []
        cur.append(ln)
    if cur:
        blocks.append(cur)
    keep = [b for b in blocks if '(layer "F.CrtYd")' not in "\n".join(b)]
    s = "\n".join([lines[0]] + [ln for b in keep for ln in b]) + "\n"
    s += ('\t(fp_circle (center 0 0) (end 4.75 0) (stroke (width 0.05) (type solid)) (fill no) (layer "F.CrtYd"))\n'
          '\t(fp_rect (start 8.66 -1.5) (end 11.66 1.5) (stroke (width 0.05) (type solid)) (fill no) (layer "F.CrtYd"))\n)\n')
    open(os.path.join(OUT, name + ".kicad_mod"), "w").write(s)


def main():
    os.makedirs(OUT, exist_ok=True)
    for f in COPY:
        shutil.copy(os.path.join(REVA, f + ".kicad_mod"), os.path.join(OUT, f + ".kicad_mod"))
    # The octal socket is fixed to the plate and only its 20 mm legs reach the board (rev A mechanics):
    # its courtyard on the board is the pin circle (r 11 mm), not the 30 mm body (layout 2026-11-24).
    sp = os.path.join(OUT, "Valve_Octal_Belton_PCD17.20mm.kicad_mod")
    s = open(sp).read()
    lines = s.split("\n")
    blocks, cur = [], []
    for ln in lines[1:-2]:                        # top-level items start with one tab and "("
        if ln.startswith("\t(") and cur:
            blocks.append(cur)
            cur = []
        cur.append(ln)
    if cur:
        blocks.append(cur)
    keep = [b for b in blocks if '(layer "F.CrtYd")' not in "\n".join(b)]
    s = "\n".join([lines[0]] + [ln for b in keep for ln in b]) + "\n"
    s = s.rstrip() + "\n" + ('\t(fp_circle (center 0 0) (end 11 0) (stroke (width 0.05) (type solid)) (fill no) '
                                  '(layer "F.CrtYd"))\n)\n')
    open(sp, "w").write(s)
    for f in os.listdir(OUT):
        if "PLACEHOLDER" in f:
            os.remove(os.path.join(OUT, f))
    tabs()
    standing_tight()
    open(os.path.join(RB, "kicad", "fp-lib-table"), "w").write(
        '(fp_lib_table\n\t(version 7)\n\t(lib (name "tube_power_amp_revb")(type "KiCad")'
        '(uri "${KIPRJMOD}/../lib/tube_power_amp_revb.pretty")(options "")'
        '(descr "rev B board-local footprints (tools/make_footprints.py)"))\n)\n')
    print(sorted(os.listdir(OUT)))


if __name__ == "__main__":
    main()
