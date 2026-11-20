#!/usr/bin/env python3
"""Footprint assignment and the project footprint library of the power amp (stdlib only).

Writes (through the shared generator tools/p2k/p2k/footprints.py)
  lib/footprint_map.csv        refdes -> footprint for all 74 parts of lib/part_map.csv
                               (72 on the board, OT and VA_PRIME off board: OFF_BOARD_PARTS)
  lib/tube_power_amp.pretty/   project footprints: derived from KiCad library footprints (pads
                               renumbered to the Proteus ids, pad centres moved onto the Proteus
                               positions) or built from the IPC-D-356A pads where KiCad has nothing
  kicad/fp-lib-table           registers the project library (p2k_config.py FP_LIB_TABLE)

Usage: python3 tools/gen_footprints.py [--check]      (needs the KiCad AppImage mount)

This file holds what is decided for this board: RULES (symbol + IPC pad pattern -> footprint)
and PROJECT (the project footprint specs); the rule syntax and the spec keys are documented in
tools/p2k/p2k/footprints.py. Pad numbers always equal the IPC pin ids.

Pad sizes: p2k_config.py FOOTPRINT_PAD_SIZES = "kicad" (KiCad library pads and drills; the
footprints built from the IPC pads - octal socket, fly-lead terminal - have the Proteus pads).
tools/p2k check_footprints verifies every footprint against the IPC pads (residual < 0.05 mm per
pad) and reports the pad size / drill differences.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools", "p2k"))  # proteus2kicad
from p2k import footprints  # noqa: E402

P = "tube_power_amp:"

# (symbol, conditions, footprint, note). Conditions: n = pad count, tht, span (mm, +-0.02),
# pad = (w, h) of the IPC pads, drill, package / device (lib/part_map.csv columns), refdes.
# One rule per Proteus package (2010 package name in the note).
RULES = [
    # --- resistors
    ("R", dict(package="RES40", span=10.16, pad=(1.778, 1.778), drill=0.762),
     "Resistor_THT:R_Axial_DIN0207_L6.3mm_D2.5mm_P10.16mm_Horizontal", "RES40: 1/4 W axial, P10.16"),
    ("R", dict(package="1K/ 5W WIREWOUND", span=30.0, pad=(2.54, 2.54), drill=1.143),
     P + "R_Axial_Power_L25.0mm_W6.4mm_P30.00mm", "1K/ 5W WIREWOUND: 5 W axial box, P30.00"),
    ("R", dict(package="2W METAL FILM RESISTOR", span=19.05, pad=(2.286, 2.286), drill=1.016),
     P + "R_Axial_DIN0414_L11.9mm_D4.5mm_P19.05mm_Horizontal", "2W METAL FILM RESISTOR: 2 W axial, P19.05"),
    # --- capacitors
    ("C", dict(package="22N XICON", span=9.70, pad=(2.54, 2.54), drill=1.143),
     P + "C_Rect_L13.0mm_W6.0mm_P9.70mm", "22N XICON: film box 13 x 6 mm, P9.70"),
    ("C_Polarized", dict(package="RAD ELEC R5 D10", span=5.0, pad=(2.54, 2.54), drill=1.143),
     P + "CP_Radial_D10.0mm_P5.00mm_PM", "RAD ELEC R5 D10: 10 mm radial electrolytic, P5.00, pads +/-"),
    ("C_Polarized", dict(package="ELEC-RAD20", span=5.08, pad=(2.54, 2.54), drill=1.143),
     P + "CP_Radial_D10.0mm_P5.08mm_PM", "ELEC-RAD20: 10 mm radial electrolytic, P5.08, pads +/-"),
    # --- diodes
    ("D", dict(package="DO41", span=10.16), P + "D_DO-41_SOD81_P10.16mm_Horizontal_AK", "DO41: pads A/K"),
    ("D_Zener", dict(package="DO41", span=10.16), P + "D_DO-41_SOD81_P10.16mm_Horizontal_AK", "DO41: pads A/K"),
    # --- transistors
    ("TIPL760", dict(package="TO220", span=5.08), "Package_TO_SOT_THT:TO-220-3_Vertical",
     "TO220: vertical, 1=B 2=C 3=E, P2.54"),
    ("MPSA92", dict(package="TO92", span=4.064), P + "TO-92_Inline_P2.03mm",
     "TO92: inline, 1=E 2=B 3=C, P2.032"),
    # --- tubes
    ("EL34", dict(package="8-PIN BELTON OCTAL", n=8, pad=(3.81, 3.81), drill=1.6),
     P + "Valve_Octal_Belton_PCD17.20mm",
     "8-PIN BELTON OCTAL: octal socket, Proteus pads and pin ids, standard octal numbering, bottom side"),
    # --- terminals (fly leads)
    ("PIN", dict(package="C-120-60", n=1, pad=(3.048, 3.048), drill=1.524),
     P + "FlyLead_Pad_D3.048mm_Drill1.524mm", "C-120-60: fly-lead terminal pad"),
]


# Project footprints (spec keys: see p2k.footprints). `ipc` = refdes whose IPC pads give the
# pad centres. All parts are THT and on the top side (Proteus Top Assembly), except the octal
# sockets U6-U9 (bottom side, user decision).
PROJECT = {
    # 5 W wirewound: KiCad's 25 x 6.4 mm box (Proteus silk 24 x 6.1 mm) with the pads 30.00 mm apart
    # (KiCad P30.48: 0.24 mm inwards per pad, still 1.3 mm between pad and body)
    "R_Axial_Power_L25.0mm_W6.4mm_P30.00mm": dict(
        base="Resistor_THT:R_Axial_Power_L25.0mm_W6.4mm_P30.48mm", ipc="R13",
        descr="5 W axial wirewound resistor, box 25 x 6.4 mm, Proteus pads 30.00 mm apart"),
    "R_Axial_DIN0414_L11.9mm_D4.5mm_P19.05mm_Horizontal": dict(
        base="Resistor_THT:R_Axial_DIN0414_L11.9mm_D4.5mm_P20.32mm_Horizontal", ipc="R24",
        descr="2 W axial metal film resistor DIN0414, Proteus pads 19.05 mm apart"),
    # 22n Xicon film: Proteus silk 12.8 x 6.0 mm, pads 9.70 mm apart
    "C_Rect_L13.0mm_W6.0mm_P9.70mm": dict(
        base="Capacitor_THT:C_Rect_L13.0mm_W6.0mm_P10.00mm_FKS3_FKP3_MKS4", ipc="C1",
        descr="Film capacitor box 13 x 6 mm (22n Xicon), Proteus pads 9.70 mm apart"),
    # electrolytics: KiCad pad 1 (square, '+' silk) = Proteus pin '+'
    "CP_Radial_D10.0mm_P5.00mm_PM": dict(
        base="Capacitor_THT:CP_Radial_D10.0mm_P5.00mm", renumber={"1": "+", "2": "-"}, ipc="C5",
        descr="10 mm radial electrolytic P5.00, pads + (KiCad pad 1) / -"),
    "CP_Radial_D10.0mm_P5.08mm_PM": dict(
        base="Capacitor_THT:CP_Radial_D10.0mm_P5.00mm", renumber={"1": "+", "2": "-"}, ipc="C6",
        descr="10 mm radial electrolytic, pads + (KiCad pad 1) / -, Proteus pads 5.08 mm apart"),
    # DO-41: KiCad pad 1 = cathode (band)
    "D_DO-41_SOD81_P10.16mm_Horizontal_AK": dict(
        base="Diode_THT:D_DO-41_SOD81_P10.16mm_Horizontal", renumber={"1": "K", "2": "A"}, ipc="D1",
        descr="DO-41 diode P10.16, pads K (KiCad pad 1, band) / A"),
    # TO-92 at the Proteus 2.032 mm (80 mil) pitch: KiCad has 1.27 (Inline) and 2.54 (Inline_Wide)
    "TO-92_Inline_P2.03mm": dict(
        base="Package_TO_SOT_THT:TO-92_Inline_Wide", ipc="Q2",
        descr="TO-92 inline, pads 1-3 2.032 mm apart (Proteus TO92)"),
    # Octal socket built from the IPC pads: KiCad's Valve_Octal is on a 2.54 mm grid (pads 10.2-10.8
    # mm from the centre, a 5.5 mm plated centre hole), Proteus has a 17.20 mm pitch circle and no
    # centre hole. Pad ids = the IPC pin ids. The sockets are mounted on the BOTTOM (solder) side
    # (user decision 2026-11-20, STATUS.md Findings 10): the footprint is built mirrored (spec key
    # `bottom`), so in the footprint's own view the pads run in the standard octal direction (as
    # KiCad's Valve_Octal) and check_footprints places U6-U9 on B (graphics, courtyard on the B
    # layers; pad positions and nets unchanged). Body: the socket outline of the Proteus Top
    # Assembly layer (a 21 mm square turned 45 deg around U6's centre, the midpoint of pads 2/6 and
    # 4/8): the 4 draws longer than 15 mm within 15.5 mm of the centre. No 3D model: KiCad has no
    # octal socket model.
    "Valve_Octal_Belton_PCD17.20mm": dict(
        ipc="U6", body_from=dict(centre=(118.4, 19.685), min_len=15, radius=15.5, expect=4), bottom=True,
        descr="Octal tube socket (Proteus 8-PIN BELTON OCTAL), standard octal numbering, mounted on the "
              "solder side: 8 pads 3.81 mm / drill 1.6 on a 17.20 mm pitch circle, pad 6 without a net, "
              "body = the Proteus assembly outline"),
    "FlyLead_Pad_D3.048mm_Drill1.524mm": dict(
        ipc="AC5", descr="Fly-lead terminal (Proteus C-120-60): one 3.048 mm pad, drill 1.524"),
    # Board-only (no symbol; placed by p2k.build_pcb at the 4 IPC 'hole' records)
    "MountingHole_3.0mm_PTH_Pad6.35mm": dict(
        board_only=True, pad=(6.35, 3.0), plated=True,
        descr="Plated 3.0 mm mounting hole with a 6.35 mm pad on both layers, no net"),
}

if __name__ == "__main__":
    footprints.run(RULES, PROJECT)
