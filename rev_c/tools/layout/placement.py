"""Power amp rev C layout: fixed positions, net classes and design rules (the one place they live).

Rev C keeps rev B's mechanics (rev_c/PLAN.md "Kept from rev B"; layout decisions of 2026-11-25):
- 4 layers, standard 1.6 mm build. The 1.25 kV plate lanes (OT_A, OT_B) run on B, with In1 / In2 voided
  under them and no vias near them. The decision of 2026-11-25 said "F only, short", but OT_B has to run about
  135 mm from J104 to V3 and V4. B carries no SMD parts in rev C, so a lane there blocks no part, and F tracks
  cross over it (1.6 mm of FR-4). The clamps and tabs are THT and reach the lanes through their own pads.
  Lanes (for placement: no THT pads and no vias within 6.3 mm + 1 mm of them): OT_A from J104 / D101-D102
  along y about 158 to V1 / V2 pin 3; OT_B from J104 / D105 north to y about 150, east to V3 / V4 pin 3. In1 = GND plane; In2 = -80 V area
  under the op amps (their PowerPADs are on V-) plus GND elsewhere.
- Single-sided SMD assembly: every SMD part on F (the side facing down, away from the plate). Only the
  octal sockets and the lying 5 W screen resistors are on B (the plate side), as rev B. The 91k grid
  leaks (on B in rev B) move to F.
- Connectors at rev B's laid-out positions (interfaces.md 12.6); J503 removed.
- East rear standoff: interfaces.md 12.5's (513.5, 179.0) was tried first, but it sits 2.7 mm from
  J101's GND_PWR tab at (514.5, 181.7), inside its receptacle envelope. Rev B's (475.9, 165.3) is kept;
  it is also an existing plate hole (V4's other flange hole), so no new chassis work is needed.

Positions are CHASSIS coordinates (D748 top plate, mm, plan from above) of the footprint origin; rotations
are KiCad orientations (F side: local +x -> chassis west at 0, rear at 90, east at 180, front at 270).
make_pcb.py converts to the KiCad frame (x_k = 620 - X, y_k = 250 - Y).
Refs: rev C's sheet 01 numbering equals rev B's except the coupling caps (rev B C103-C106 = rev C C101-C104;
rev B's HF caps C101 / C102 are gone).
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import layout_frame as LF  # noqa: E402

import pcbnew  # noqa: E402

CU_ALL = (pcbnew.F_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu, pcbnew.B_Cu)
CU_OUT = (pcbnew.F_Cu, pcbnew.B_Cu)
CU_IN = (pcbnew.In1_Cu, pcbnew.In2_Cu)

# ---------------------------------------------------------------------------------- net classes
# (name, clearance, track width, colour, priority)
NETCLASSES = [
    ("Default", 0.15, 0.25, "rgba(0, 0, 0, 0.000)", 2147483647),
    ("HV1250", 6.3, 2.0, "rgba(220, 0, 0, 1.000)", 0),
    ("HV450", 2.5, 0.6, "rgba(230, 120, 0, 1.000)", 1),
    ("BIAS80", 0.6, 0.25, "rgba(0, 120, 200, 1.000)", 3),
    ("HTR", 0.25, 1.0, "rgba(140, 40, 180, 1.000)", 4),
    ("PWR", 0.15, 0.5, "rgba(0, 150, 0, 1.000)", 5),
]
CLASS_NETS = {
    "HV1250": ["OT_A", "OT_B", "CL_A", "CL_B"],
    "HV450": ["V_ANODE", "V_SCREEN", "DRV_A", "DRV_B"] + [f"G2_{n}" for n in range(1, 5)],
    # -80 V rail, op amp outputs and feedback nodes (up to 80 V), bias and grid. Not MON_M80 (1-2.5 V: only the
    # 536k's far pad is at -80 V, and that pad is M80)
    "BIAS80": (["M80", "M80_IN"]
               + [f"{p}{n}" for p in ("OA", "FB", "BIAS", "GRID") for n in range(1, 5)]
               + [f"G1_{n}" for n in range(1, 5)]),
    "HTR": ["HTR1", "HTR2"],
    "PWR": ["GND", "GNDD", "+15V", "+5V"],
}

# ---------------------------------------------------------------------------------- design rules
SOCKETS = " || ".join(f"A.memberOfFootprint('{v}')" for v in LF.SOCKETS)
DRU = """(version 1)
# Power amp rev C design rules (rev_c/tools/layout/placement.py), as rev B (rev_b/STATUS.md "Layout, first pass" B).
# Spacing: IPC-2221B table 6-1, B2 (external conductors, uncoated, sea level to 3050 m) on F / B, and
# B1 (internal conductors) on In1 / In2; cross-checked against IEC 60664-1 functional insulation,
# pollution degree 2, material group IIIb (FR-4, CTI 175): 6.3 mm creepage covers 630 V rms working.
# Classes (net classes in the project):
#   HV1250  OT_A, OT_B, CL_A, CL_B: 1.25 kV peak with the open-load clamps. Rev C: F only, inner layers voided
#           under them and no vias near them (drawn with the copper); the inner rule stays as a backstop.
#   HV450   V_ANODE, V_SCREEN, DRV_A / DRV_B (280-390 V), G2_1..4: up to 480 V transient
#   BIAS80  -80 V rail, op amp outputs / feedback, bias and grid nets: up to about 100 V
#   HTR     the floating heater: 0 V or +90 V (elevated option)
# B2: >500 V 0.005 mm/V (1.25 kV: 6.3 mm), 301-500 V 2.5 mm (HV classes, exposed pads and tracks alike).
# B1: >500 V 0.0025 mm/V (1.25 kV: 3.1 mm -> 3.2), 301-500 V 0.25 mm (-> 0.5 mm used).
# Later rules win over earlier ones (KiCad order); the exceptions come last.

(rule "HV1250 outer"
  (layer outer)
  (condition "A.NetClass == 'HV1250' && A.Net != B.Net")
  (constraint clearance (min 6.3mm)))
(rule "HV1250 inner"
  (layer inner)
  (condition "A.NetClass == 'HV1250' && A.Net != B.Net")
  (constraint clearance (min 3.2mm)))
(rule "HV450 outer"
  (layer outer)
  (condition "A.NetClass == 'HV450' && B.NetClass != 'HV450' && B.NetClass != 'HV1250' && A.Net != B.Net")
  (constraint clearance (min 2.5mm)))
(rule "HV450 to HV450 outer"
  (layer outer)
  (condition "A.NetClass == 'HV450' && B.NetClass == 'HV450' && A.Net != B.Net")
  (constraint clearance (min 1.25mm)))
(rule "HV450 inner"
  (layer inner)
  (condition "A.NetClass == 'HV450' && B.NetClass != 'HV1250' && A.Net != B.Net")
  (constraint clearance (min 0.5mm)))
# BIAS80: B2 0.6 mm outer (net class), 0.2 mm inside, 0.2 mm between pads of different nets only at the
# parts' own pitch (the OPA462's 1.27 mm pins carry -80 V next to the inputs).
(rule "BIAS80 inner"
  (layer inner)
  (condition "A.NetClass == 'BIAS80' && A.Net != B.Net")
  (constraint clearance (min 0.2mm)))
(rule "BIAS80 pad to pad (parts' own pitch)"
  (layer outer)
  (condition "A.NetClass == 'BIAS80' && A.Type == 'Pad' && B.Type == 'Pad' && A.Net != B.Net && B.NetClass != 'HV450' && B.NetClass != 'HV1250'")
  (constraint clearance (min 0.2mm)))
# Chassis standoffs (unplated holes; the standoff and screw head are chassis): HV keeps its class
# distance from the 6.4 mm standoff, i.e. hole clearance = spacing + 3.2 - 1.6.
(rule "HV1250 to standoff holes"
  (layer outer)
  (condition "A.NetClass == 'HV1250' && B.Pad_Type == 'NPTH, mechanical'")
  (constraint hole_clearance (min 8.0mm)))
(rule "HV450 to standoff holes"
  (layer outer)
  (condition "A.NetClass == 'HV450' && B.Pad_Type == 'NPTH, mechanical'")
  (constraint hole_clearance (min 4.2mm)))
(rule "HV1250 to standoff holes, inner"
  (layer inner)
  (condition "A.NetClass == 'HV1250' && B.Pad_Type == 'NPTH, mechanical'")
  (constraint hole_clearance (min 3.2mm)))
(rule "HV450 to standoff holes, inner"
  (layer inner)
  (condition "A.NetClass == 'HV450' && B.Pad_Type == 'NPTH, mechanical'")
  (constraint hole_clearance (min 0.5mm)))
(rule "HV to board edge"
  (condition "A.NetClass == 'HV1250' || A.NetClass == 'HV450'")
  (constraint edge_clearance (min 2.0mm)))

# Exceptions: the octal socket's own pins (2.77 mm between pads, the tube base sets it) and the copper round
# them: an HV item that reaches into a socket's area (rule areas SKT1..4, r 13.5 mm) keeps 2.0 mm from what
# lies wholly inside that area; everywhere else its class.
(rule "socket pins"
  (condition "(%s) && (%s)")
  (constraint clearance (min 2.0mm)))
(rule "HV round the socket pins"
  (layer outer)
  (condition "(A.NetClass == 'HV1250' || A.NetClass == 'HV450') && A.Net != B.Net && ((A.intersectsArea('SKT1') && B.enclosedByArea('SKT1')) || (A.intersectsArea('SKT2') && B.enclosedByArea('SKT2')) || (A.intersectsArea('SKT3') && B.enclosedByArea('SKT3')) || (A.intersectsArea('SKT4') && B.enclosedByArea('SKT4')))")
  (constraint clearance (min 2.0mm)))
(rule "HV round the socket pins (reverse)"
  (layer outer)
  (condition "(B.NetClass == 'HV1250' || B.NetClass == 'HV450') && A.Net != B.Net && ((B.intersectsArea('SKT1') && A.enclosedByArea('SKT1')) || (B.intersectsArea('SKT2') && A.enclosedByArea('SKT2')) || (B.intersectsArea('SKT3') && A.enclosedByArea('SKT3')) || (B.intersectsArea('SKT4') && A.enclosedByArea('SKT4')))")
  (constraint clearance (min 2.0mm)))
# J105 (Mini-Fit Jr, 600 V rated part): 1.4 mm between its own pads (4.2 mm pitch).
(rule "J105 own pads"
  (condition "A.memberOfFootprint('J105') && B.memberOfFootprint('J105')")
  (constraint clearance (min 1.4mm)))
""" % (SOCKETS, SOCKETS.replace("A.", "B."))

# ---------------------------------------------------------------------------------- mechanics
STANDOFF_R = 3.5          # copper keep-out round each standoff on all layers (6.4 mm standoff / screw head)
HOLES = {"H1": (475.9, 165.3), "H2": (315.4, 178.9), "H3": (514.95, 131.45), "H4": (284.95, 131.45)}

# ---------------------------------------------------------------------------------- fixed positions
# Everything here is rev B's laid-out position (rev_b/tools/layout/placement.py, commit a0c332e); the rest
# of the parts are parked below the board for the placement step.
S = LF.SOCKETS
P = {}
for v, (sx, sy) in S.items():
    P[v] = (sx, sy, 180, "B")                               # as rev B

# grid stoppers 5.6k 1206 inside the pin circle at pin 5, pad 2 (G1) toward pin 5
for n, v in enumerate(S, 1):
    sx, sy = S[v]
    P[f"R1{(n - 1) * 4 + 2:02d}"] = (sx + 2.95, sy + 2.95, 135, "F")

# connectors (interfaces.md 12.6)
P["J105"] = (286.50, 141.00, 180, "F")      # W24, pin 1 at (286.50, 141.00), pins 1 / 4 at the west end
P["J104"] = (311.70, 139.00, 180, "F")      # OT_A 311.7 / OT_CT 338.1 / OT_B 364.5
P["J103"] = (383.00, 166.50, 180, "F")      # heaters, 6.3 mm tabs on 11.5 mm (gap V2-V3)
P["J101"] = (514.50, 171.50, 90, "F")       # V_ANODE / GND_PWR (star)
P["J102"] = (514.50, 161.30, 90, "F")       # V_SCREEN
P["J201"] = (482.50, 143.20, 270, "F")      # -80 V / BIAS_RTN, blades along y
P["J501"] = (499.40, 132.80, 90, "F")       # W14, translation of control board J4
P["J502"] = (511.30, 141.10, 180, "F")      # W15, turned 90 deg, one 45 deg fold

# open-load clamps: one row behind the J104 tabs
P["D101"] = (310.16, 145.50, 0, "F")        # RGP02 OT_A -> GND
P["D102"] = (313.20, 145.50, 180, "F")      # P6KE350CA OT_A -> CL_A
P["D103"] = (326.40, 145.50, 180, "F")      # CL_A -> V_ANODE
P["D106"] = (349.76, 145.50, 0, "F")        # CL_B -> V_ANODE
P["D105"] = (362.96, 145.50, 0, "F")        # OT_B -> CL_B
P["D104"] = (370.50, 137.50, 180, "F")      # RGP02 OT_B -> GND

# per-gap power parts: coupling caps on F, screen resistors lying on B (R111 standing on F)
P["C101"] = (344.00, 178.50, 0, "F")        # V1 (rev B C103)
P["C102"] = (399.00, 178.50, 0, "F")        # V2 (rev B C104)
P["C103"] = (467.10, 178.50, 0, "F")        # V3 (rev B C105)
P["C104"] = (444.60, 166.50, 180, "F")      # V4 (rev B C106)
P["R103"] = (340.74, 172.20, 0, "B")        # V1 screen
P["R107"] = (404.00, 172.20, 0, "B")        # V2 screen
P["R111"] = (406.70, 178.50, 270, "F")      # V3 screen, standing
P["R115"] = (442.50, 172.20, 180, "B")      # V4 screen
# grid leaks 91k 2512, on F (rev B: on B), close to their coupling cap's grid pad
P["R101"] = (327.00, 171.50, 0, "F")        # GRID1 = C101 pad 2 (321.5, 178.5); under C101, clear of R103's pads
P["R105"] = (371.00, 185.20, 0, "F")        # GRID2 = C102 pad 2 (376.5, 178.5); rear edge strip (0.58 mm pad to edge)
P["R109"] = (448.00, 185.20, 0, "F")        # GRID3 = C103 pad 2 (444.6, 178.5); rear edge strip
P["R113"] = (460.00, 185.20, 0, "F")        # GRID4 = C104 pad 2 (467.1, 166.5); rear edge strip

# cathode sets: 1 ohm shunt, S3M, Kelvin net tie, test pads (K and its ground) on F
P["R104"] = (292.00, 156.00, 90, "F"); P["D107"] = (285.50, 156.00, 90, "F"); P["N101"] = (294.80, 160.00, 90, "F")
P["TP101"] = (296.80, 152.40, 0, "F"); P["TP102"] = (296.80, 155.90, 0, "F")
P["R108"] = (349.50, 165.50, 90, "F"); P["N102"] = (349.50, 170.40, 90, "F")
P["D108"] = (344.00, 163.00, 270, "F")      # rev B had it on B; F: K2 at the front (next to R108's K2 pad), GND rear
P["TP103"] = (350.50, 174.00, 0, "F"); P["TP104"] = (350.50, 177.50, 0, "F")
P["R112"] = (415.50, 167.00, 90, "F"); P["D109"] = (414.80, 176.60, 90, "F"); P["N103"] = (412.80, 170.10, 0, "F")
P["TP105"] = (418.60, 160.80, 0, "F"); P["TP106"] = (418.60, 157.30, 0, "F")
P["R116"] = (480.00, 173.10, 90, "F"); P["D110"] = (482.80, 164.00, 90, "F"); P["N104"] = (477.60, 170.00, 90, "F")
P["TP107"] = (483.50, 178.50, 0, "F"); P["TP108"] = (483.50, 181.80, 0, "F")

# ---------------------------------------------------------------------------------- packed groups
# (name, refs, zone (x0, y0, x1, y1) chassis, side, rotation, gap). make_pcb.py packs each group bottom-left
# (front first, then west to east) into its zone, around everything already placed.
# Front band: y 127.6 to 142.3 (the OT_B lane's via-free band starts there), x 377.8 (OT_B pads at J104 /
# D104 + 6.3 mm) to 478.4 (J501). All of it is >= 30 mm from every socket centre (dy >= 30 mm); every IC on
# rev C is rated to 125 C.
def ch(n):
    r, c = 202 + 5 * (n - 1), 206 + 4 * (n - 1)
    return [f"U{202 + n}"] + [f"R{r + k}" for k in (3, 2, 1, 0, 4)] + [f"C{c + k}" for k in range(4)]


OPAMP_X0, OPAMP_W = 395.5, 12.4
GROUPS = [
    ("m80 fuse", ["R201"], (463.0, 127.6, 478.4, 131.6), "F", 0, 0.3),       # near J201 (482.5, 140.7)
    ("m80 bulk", ["C201", "D201", "C202"], (377.8, 127.6, OPAMP_X0, 142.3), "F", 0, 0.3),
] + [(f"bias ch{n}", ch(n), (OPAMP_X0 + (n - 1) * OPAMP_W, 127.6, OPAMP_X0 + n * OPAMP_W, 142.3), "F", 0, 0.25)
     for n in range(1, 5)] + [
    ("precision, ADCs, ribbon parts",
     ["U202", "U201", "U301", "U302", "U303", "C302", "C303", "R314"]
     + ["C203", "C204", "C205", "C304", "C307", "C310", "C311", "C305", "C306", "C308", "C309", "C301"]
     + [f"R{i}" for i in range(301, 320) if i != 314],
     (OPAMP_X0 + 4 * OPAMP_W, 127.6, 478.4, 142.3), "F", 0, 0.25),
]


def positions():
    return dict(P)


def keepouts():
    out = []
    for i, (v, (sx, sy)) in enumerate(S.items(), 1):
        # named areas for the DRC exceptions round the socket pins (no restriction of their own)
        out.append((f"SKT{i}", [(sx + 13.5 * math.cos(2 * math.pi * k / 32), sy + 13.5 * math.sin(2 * math.pi * k / 32))
                                for k in range(32)], CU_ALL,
                    dict(tracks=False, vias=False, fill=False, pads=False, fps=False)))
    return out


ZONE_NOTES = {}
SILK = []
SILK_REFS = {"J101", "J102", "J103", "J104", "J105", "J201", "J501", "J502", "V1", "V2", "V3", "V4"}
