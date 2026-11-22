#!/usr/bin/env python3
"""Board-local footprints for the power amp rev B (lib/tube_power_amp_revb.pretty) and the
project's fp-lib-table. Everything else comes from KiCad's stock libraries.

- Valve_Octal_Belton_PCD17.20mm, R_Axial_Power_L25.0mm_W6.4mm_P30.00mm: copied unchanged from the
  rev A conversion (lib/tube_power_amp.pretty at the repo root, which is frozen and only read
  here), so the sockets and the 5 W resistors keep the as-built pad pattern.
- BladeTab_x{1,2,3}_P5.00mm_Drill1.4mm_PLACEHOLDER: interfaces.md 2 / 4.1, "PCB blade tab, 2 legs
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


def tab(n):
    name = f"BladeTab_x{n}_P5.00mm_Drill1.4mm_PLACEHOLDER"
    pads, gfx = [], []
    for i in range(n):
        x = i * PITCH
        for dy in (-2.5, 2.5):
            pads.append(f'\t(pad "{i + 1}" thru_hole circle (at {x:.2f} {dy:.2f}) (size 2.6 2.6) (drill 1.4) '
                        f'(layers "*.Cu" "*.Mask"))')
        gfx.append(f'\t(fp_rect (start {x - 3.6:.2f} -4.6) (end {x + 3.6:.2f} 4.6) (stroke (width 0.12) (type solid)) '
                   f'(fill no) (layer "F.SilkS"))')
        gfx.append(f'\t(fp_text user "{i + 1}" (at {x:.2f} 0) (layer "F.Fab") (effects (font (size 1 1) (thickness 0.15))))')
    body = "\n".join([
        f'(footprint "{name}"', '\t(version 20260206)', '\t(generator "make_footprints")', '\t(layer "F.Cu")',
        f'\t(descr "PLACEHOLDER: {n} PCB blade tab(s), 2 legs on 5.00 mm, 1.4 mm drill (interfaces.md 4.1), tabs {PITCH} mm apart; '
        'tab width per rail class (HV 4.8 mm, heaters 6.3 mm); part and spacing to be chosen at layout")',
        '\t(property "Reference" "REF**" (at 0 -6 0) (layer "F.SilkS") (effects (font (size 1 1) (thickness 0.15))))',
        f'\t(property "Value" "{name}" (at 0 6 0) (layer "F.Fab") (effects (font (size 1 1) (thickness 0.15))))',
        '\t(attr through_hole)', *gfx, *pads, ')'])
    open(os.path.join(OUT, name + ".kicad_mod"), "w").write(body + "\n")


def main():
    os.makedirs(OUT, exist_ok=True)
    for f in COPY:
        shutil.copy(os.path.join(REVA, f + ".kicad_mod"), os.path.join(OUT, f + ".kicad_mod"))
    for n in (1, 2, 3):
        tab(n)
    open(os.path.join(RB, "kicad", "fp-lib-table"), "w").write(
        '(fp_lib_table\n\t(version 7)\n\t(lib (name "tube_power_amp_revb")(type "KiCad")'
        '(uri "${KIPRJMOD}/../lib/tube_power_amp_revb.pretty")(options "")'
        '(descr "rev B board-local footprints (tools/make_footprints.py)"))\n)\n')
    print(sorted(os.listdir(OUT)))


if __name__ == "__main__":
    main()
