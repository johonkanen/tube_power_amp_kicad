"""Power amp rev B layout: placement table, net classes and design rules (the one place they live).

Positions are CHASSIS coordinates (D748 top plate, mm, plan from above) of the footprint origin; rotations
are KiCad orientations (F side: local +x -> chassis west at 0, rear at 90, east at 180, front at 270).
make_pcb.py converts to the KiCad frame (x_k = 620 - X, y_k = 250 - Y).
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
    ("HV450", 0.5, 1.0, "rgba(230, 120, 0, 1.000)", 1),
    ("BIAS80", 0.2, 0.3, "rgba(0, 120, 200, 1.000)", 3),
    ("HTR", 0.2, 2.0, "rgba(140, 40, 180, 1.000)", 4),
    ("PWR", 0.15, 0.5, "rgba(0, 150, 0, 1.000)", 5),
]
CLASS_NETS = {
    "HV1250": ["OT_A", "OT_B", "CL_A", "CL_B"],
    "HV450": ["V_ANODE", "V_SCREEN", "DRV_A", "DRV_B"] + [f"G2_{n}" for n in range(1, 5)],
    "BIAS80": (["M80", "M80_IN", "ZR", "ZF", "Z1", "VS1", "VS2", "VNC", "MVA"]
               + [f"{p}{n}" for p in ("OUT", "FE", "PM", "BIAS", "GRID") for n in range(1, 5)]
               + [f"G1_{n}" for n in range(1, 5)]),
    "HTR": ["HTR1", "HTR2", "HS_AC1", "HS_P", "HS_N", "HS_Z"],
    "PWR": ["GND", "GNDD", "+15V", "-15V", "+5V"],
}

# ---------------------------------------------------------------------------------- design rules
SOCKETS = " || ".join(f"A.memberOfFootprint('{v}')" for v in LF.SOCKETS)
DRU = """(version 1)
# Power amp rev B design rules (rev_b/tools/layout/placement.py; STATUS "Layout, first pass").
# Spacing: IPC-2221B table 6-1, B2 (external conductors, uncoated, sea level to 3050 m) on F / B, and
# B1 (internal conductors) on In1 / In2; cross-checked against IEC 60664-1 functional insulation,
# pollution degree 2, material group IIIb (FR-4, CTI 175): 6.3 mm creepage covers 630 V rms working.
# Classes (net classes in the project):
#   HV1250  OT_A, OT_B, CL_A, CL_B: 1.25 kV peak with the open-load clamps (STATUS third pass)
#   HV450   V_ANODE, V_SCREEN, DRV_A / DRV_B (280-390 V), G2_1..4: up to 480 V transient
#   BIAS80  the -80 V reference, followers, bias nodes, grids: up to about 100 V
#   HTR     the floating heater and its sense: 0 V or +90 V (elevated option)
# B2: >500 V 0.005 mm/V (1.25 kV: 6.3 mm), 301-500 V 2.5 mm, 31-100 V 0.6 mm.
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
(rule "BIAS80 and heater outer"
  (layer outer)
  (condition "(A.NetClass == 'BIAS80' || A.NetClass == 'HTR') && A.Net != B.Net && B.NetClass != 'HV450' && B.NetClass != 'HV1250'")
  (constraint clearance (min 0.6mm)))
(rule "BIAS80 pad to pad (parts' own pitch)"
  (layer outer)
  (condition "A.NetClass == 'BIAS80' && A.Type == 'Pad' && B.Type == 'Pad' && A.Net != B.Net && B.NetClass != 'HV450' && B.NetClass != 'HV1250'")
  (constraint clearance (min 0.2mm)))
# Chassis standoffs (unplated holes; the standoff and screw head are chassis): HV keeps its class
# distance from the 6.4 mm standoff, i.e. hole clearance = spacing + 3.2 - 1.6.
(rule "HV1250 to standoff holes"
  (condition "A.NetClass == 'HV1250' && B.Pad_Type == 'NPTH, mechanical'")
  (constraint hole_clearance (min 8.0mm)))
(rule "HV450 to standoff holes"
  (condition "A.NetClass == 'HV450' && B.Pad_Type == 'NPTH, mechanical'")
  (constraint hole_clearance (min 4.2mm)))
(rule "HV to board edge"
  (condition "A.NetClass == 'HV1250' || A.NetClass == 'HV450'")
  (constraint edge_clearance (min 2.0mm)))

# Exceptions: the octal socket's own pins (2.77 mm between pads, the tube base sets it) and the
# copper inside the socket's pin circle area (rule areas SKT1..4, r 12.5 mm): 2.5 mm.
(rule "socket pins"
  (condition "(%s) && (%s)")
  (constraint clearance (min 2.0mm)))
(rule "HV inside the socket areas"
  (layer outer)
  (condition "(A.NetClass == 'HV1250' || A.NetClass == 'HV450') && A.Net != B.Net && (A.enclosedByArea('SKT1') || A.enclosedByArea('SKT2') || A.enclosedByArea('SKT3') || A.enclosedByArea('SKT4')) && (B.enclosedByArea('SKT1') || B.enclosedByArea('SKT2') || B.enclosedByArea('SKT3') || B.enclosedByArea('SKT4'))")
  (constraint clearance (min 2.0mm)))
# J105 (Mini-Fit Jr, 600 V rated part): 1.5 mm between its own pads (4.2 mm pitch).
(rule "J105 own pads"
  (condition "A.memberOfFootprint('J105') && B.memberOfFootprint('J105')")
  (constraint clearance (min 1.4mm)))
""" % (SOCKETS, SOCKETS.replace("A.", "B."))

# ---------------------------------------------------------------------------------- mechanics
STANDOFF_R = 3.5          # copper keep-out round each standoff on all layers (6.4 mm standoff / screw head)
HOLES = {"H1": (475.9, 165.3), "H2": (315.4, 178.9), "H3": (514.95, 131.45), "H4": (284.95, 131.45)}

# ---------------------------------------------------------------------------------- placement
S = LF.SOCKETS
P = {}
for v, (sx, sy) in S.items():
    P[v] = (sx, sy, 180, "B")                               # rev A orientation: pin 3 (plate) front-east

# grid stoppers 5.6k 1206 inside the pin circle at pin 5 (rear-east), pad 2 (G1) toward pin 5
for n, v in enumerate(S, 1):
    sx, sy = S[v]
    P[f"R1{(n - 1) * 4 + 2:02d}"] = (sx + 2.95, sy + 2.95, 135, "F")

# connectors (interfaces: STATUS "Layout sketch" / interfaces.md 12.5)
P["J105"] = (294.90, 146.50, 0, "F")        # W24, pin 1 at the east end (the sketch's 180 deg turn)
P["J104"] = (311.70, 139.00, 180, "F")      # OT_A 311.7 / OT_CT 338.1 / OT_B 364.5, y 134
P["J103"] = (383.00, 166.50, 180, "F")      # heaters, 6.3 mm tabs on 11.5 mm (gap V2-V3)
P["J101"] = (514.50, 171.50, 90, "F")      # V_ANODE / GND_PWR (star)
P["J102"] = (514.50, 161.30, 90, "F")      # V_SCREEN
P["J201"] = (482.50, 143.20, 270, "F")      # -80 V / BIAS_RTN, blades along y
P["J501"] = (499.40, 132.80, 90, "F")       # W14, translation of control board J4
P["J502"] = (511.30, 141.10, 180, "F")      # W15, turned 90 deg, one 45 deg fold
P["J503"] = (499.00, 145.50, 180, "F")      # W16

# open-load clamps: one row at y 144.5 behind the tabs (10.16 mm parts)
P["D101"] = (310.16, 145.50, 0, "F")        # RGP02 OT_A (310.16) -> GND (300.0)
P["D102"] = (313.20, 145.50, 180, "F")      # P6KE350CA OT_A (313.2) -> CL_A (323.36)
P["D103"] = (326.40, 145.50, 180, "F")      # CL_A (326.4) -> V_ANODE (336.56)
P["D106"] = (349.76, 145.50, 0, "F")        # CL_B (349.76) -> V_ANODE (339.6)
P["D105"] = (362.96, 145.50, 0, "F")        # OT_B (362.96) -> CL_B (352.8)
P["D104"] = (370.50, 137.50, 180, "F")      # RGP02 OT_B (366.0) -> GND (376.16)
P["C101"] = (345.00, 135.50, 90, "F")      # V_ANODE HF decoupling at the centre tap (pad 1 rear)

# per-gap power parts: coupling caps on F (pads y 167 / 177.5), screen resistors lying on B
P["C103"] = (344.00, 178.50, 0, "F")        # V1 DRV_A (335.0) / GRID1 (312.5)
P["C104"] = (399.00, 178.50, 0, "F")        # V2 (GRID2 378.5)
P["C105"] = (467.10, 178.50, 0, "F")        # V3 DRV_B (GRID3 444.6)
P["C106"] = (467.10, 166.50, 0, "F")        # V4 (GRID4 444.6, on In2 to V4)
P["R103"] = (340.74, 172.20, 0, "B")      # V1 screen: V_SCREEN 340.5 / G2_1 310.5
P["R107"] = (404.00, 172.20, 0, "B")      # V2 screen
P["R111"] = (406.70, 178.50, 270, "F")      # V3 screen
P["R115"] = (442.30, 172.20, 180, "B")      # V4 screen (G2_4 on In2), rear row
P["C102"] = (507.60, 180.00, 90, "F")        # V_SCREEN HF decoupling
# grid leaks 91k 2512 on B next to the coupling cap's grid pad
P["R101"] = (329.50, 178.50, 0, "B")
P["R105"] = (382.50, 181.20, 0, "B")
P["R109"] = (452.50, 178.50, 0, "B")
P["R113"] = (452.50, 166.50, 0, "B")

# cathode sets: 1 ohm shunt, S3M, Kelvin net tie, test pads (K and its ground) on F
P["R104"] = (292.00, 156.00, 90, "F"); P["D107"] = (285.50, 156.00, 90, "F"); P["N101"] = (294.80, 160.00, 90, "F")
P["TP101"] = (296.80, 152.40, 0, "F"); P["TP102"] = (296.80, 155.90, 0, "F")
P["R108"] = (349.50, 165.50, 90, "F"); P["D108"] = (346.00, 166.50, 90, "B"); P["N102"] = (349.50, 170.40, 90, "F")
P["TP103"] = (350.50, 174.00, 0, "F"); P["TP104"] = (350.50, 177.50, 0, "F")
P["R112"] = (415.50, 167.00, 90, "F"); P["D109"] = (414.80, 176.60, 90, "F"); P["N103"] = (412.80, 170.10, 0, "F")
P["TP105"] = (418.60, 160.80, 0, "F"); P["TP106"] = (418.60, 157.30, 0, "F")
P["R116"] = (480.00, 173.10, 90, "F"); P["D110"] = (482.80, 164.00, 90, "F"); P["N104"] = (477.60, 170.00, 90, "F")
P["TP107"] = (483.50, 178.50, 0, "F"); P["TP108"] = (483.50, 181.80, 0, "F")

# ---------------------------------------------------------------------------------- packing groups
# (name, refs, zone (x0, y0, x1, y1) chassis, side, rotation, gap). make_pcb.py packs them in rows.
def R(a, b, p="R"):
    return [f"{p}{i}" for i in range(a, b + 1)]


# bias channels: four 8.2 mm columns (F: transistors and 100 V caps; B: resistors), U303 between 2 and 3
BIAS_X = {1: 398.6, 2: 406.8, 3: 423.4, 4: 431.6}
for n, u0 in BIAS_X.items():
    q = 302 + 6 * (n - 1)
    c = 306 + 4 * (n - 1)
    rows = [(f"Q{q}", f"Q{q + 1}", 130.0), (f"C{c}", f"Q{q + 2}", 133.7), (f"Q{q + 3}", f"Q{q + 4}", 137.4),
            (f"C{c + 1}", f"Q{q + 5}", 141.1), (f"C{c + 2}", f"C{c + 3}", 144.8)]
    for a_, b_, y in rows:
        P[a_] = (u0 + 1.9, y, 90 if a_.startswith("C") else 0, "F")
        P[b_] = (u0 + 6.1, y, 90 if b_.startswith("C") else 0, "F")
P["U303"] = (419.15, 137.0, 180, "F")
P["Q301"] = (469.6, 130.2, 0, "B")           # DAC ~CLR clamp, next to the DAC (B side)

# precision strip (85 C parts >= 40 mm from a socket centre, op amps / comparators >= 30 mm): F side
P["U401"] = (444.45, 132.30, 90, "F")        # sense op amps
P["U402"] = (444.45, 141.40, 90, "F")        # over-current comparators
P["U405"] = (452.90, 131.00, 0, "F")         # ADC
P["U301"] = (460.90, 131.00, 0, "F")         # DAC
P["U201"] = (467.40, 130.60, 0, "F")         # LM4040-10
P["D202"] = (452.20, 138.60, 0, "F")         # 36 V zeners (1 cm2 copper each, poured later)
P["D203"] = (452.20, 143.40, 0, "F")
P["D204"] = (455.80, 141.00, 90, "F")
P["R203"] = (459.60, 138.40, 0, "F")
P["R202"] = (459.60, 141.40, 0, "F")
P["C202"] = (463.60, 138.20, 90, "F")
P["C203"] = (466.90, 138.20, 90, "F")
P["U302"] = (465.70, 145.40, 0, "F")         # ADR4525
# -80 V input and followers
P["R201"] = (384.70, 145.80, 180, "F")       # 10R fusible, pads (384.7, 397.4) at y 145.8
P["C201"] = (386.80, 138.60, 180, "F")         # 100 uF / 100 V radial D10
P["C204"] = (353.30, 133.50, 0, "F")         # 10 uF / 100 V radial D6.3
P["D201"] = (396.60, 138.80, 90, "F")        # S1G reverse clamp
P["U202"] = (388.30, 131.60, 90, "B")         # monitors (LM2901B) on B
P["Q201"] = (388.00, 151.80, 0, "F")         # BSP92P followers (corridor, between V2 and V3)
P["Q202"] = (397.20, 151.80, 0, "F")
P["U501"] = (488.00, 152.50, 90, "F")         # expander on the DGND island (corridor, over the OT_B lane)

BIAS_F = []
BIAS_B = []
for n, u0 in BIAS_X.items():
    r = 302 + 11 * (n - 1)
    BIAS_B.append((f"bias B{n}", [f"R{i}" for i in range(r, r + 11)], (u0 + 0.2, 128.0, u0 + 8.0, 146.8)))
BIAS_U303B = ["C304", "C305", "R301", "D401", "D402", "D403", "D404"]
PREC_F = []
PREC_B = (["R208", "R209", "R210", "R211", "R212", "R213", "R216", "R217", "R425", "R426", "C205", "C206", "C301", "C302",
           "C303"] + R(422, 427, "C") + R(429, 434) + ["R404", "R405", "R406", "R410", "R411", "R412", "R416", "R417", "R418",
                                                       "R422", "R423", "R424", "C406", "C410", "C414", "C418", "C401", "C402",
                                                       "C419", "C420", "C421", "R427", "R428"])
MON_B = ["R214", "R215", "R218", "R219", "R220", "R221", "R222", "R223", "D205", "D207", "C207", "C208"]
MON_F = ["R224", "R225", "R226", "R227", "R228", "D206", "D208", "D209", "C209", "C210"]
M80 = ["R204", "R205", "R206", "R207"]
WD = R(229, 232) + ["C211", "C212", "D210", "Q203"]
DIG = ["C505", "R501", "R502", "R504", "R505", "C501", "R503", "C502", "C503", "C504"]
LOGIC = (["R506", "R507", "R508", "R509", "R510", "R511", "R512", "R513", "R514", "R515", "R516",
          "U403", "U404", "U504", "U505", "C509", "C510", "C511", "Q501", "Q502", "Q503"] + R(523, 530) + ["U506", "D506"])
HEAT_BIG = ["U503", "U502"]
HEAT = ["D501", "D502", "R517", "R518", "C506", "C507", "C508"] + R(519, 522) + R(503, 505, "D")
SENSE_RC = {1: R(401, 403) + R(403, 405, "C"), 2: R(407, 409) + R(407, 409, "C"),
            3: R(413, 415) + R(411, 413, "C"), 4: R(419, 421) + R(415, 417, "C")}

GROUPS = [
    ("m80", M80, (384.0, 147.6, 400.0, 157.6), "F", 0, 0.4),
    ("mon B", MON_B, (384.0, 128.0, 398.0, 146.8), "B", 0, 0.25),
    ("u303 B", BIAS_U303B, (415.0, 128.0, 423.2, 146.8), "B", 0, 0.25),
    ("prec B", PREC_B, (439.5, 128.0, 469.0, 146.8), "B", 0, 0.25),
    ("dig B", DIG, (469.2, 128.0, 510.5, 139.2), "B", 0, 0.25),
    ("dig F", DIG, (469.0, 128.0, 478.4, 146.8), "F", 0, 0.3),
    ("wd", WD, (400.0, 147.6, 420.0, 157.6), "F", 0, 0.4),
    ("logic", ["U404"] + MON_F + [r for r in LOGIC[::-1] if r != "U404"], (420.0, 147.6, 500.0, 157.6), "F", 0, 0.35),
    ("heat big", HEAT_BIG, (311.0, 147.0, 340.0, 168.6), "F", 0, 0.3),
    ("heat", HEAT, (299.0, 147.0, 384.0, 168.6), "F", 0, 0.35),
    ("sense1", SENSE_RC[1], (281.0, 150.6, 296.0, 162.0), "B", 0, 0.25),
    ("sense2", SENSE_RC[2], (318.0, 161.8, 340.0, 169.3), "B", 0, 0.25),
    ("sense3", SENSE_RC[3], (389.5, 161.8, 403.0, 169.3), "B", 0, 0.25),
    ("sense4", SENSE_RC[4], (476.3, 168.5, 484.2, 182.4), "B", 0, 0.25),
] + [(nm, refs, zone, "B", 0, 0.2) for nm, refs, zone in BIAS_B]


def positions():
    return dict(P)


def keepouts():
    out = []
    for i, (v, (sx, sy)) in enumerate(S.items(), 1):
        # named areas for the DRC exceptions round the socket pins (no restriction of their own)
        out.append((f"SKT{i}", [(sx + 12.5 * math.cos(2 * math.pi * k / 32), sy + 12.5 * math.sin(2 * math.pi * k / 32))
                                for k in range(32)], CU_ALL,
                    dict(tracks=False, vias=False, fill=False, pads=False, fps=False)))
    return out


ZONE_NOTES = {}
SILK = []
SILK_REFS = {"J101", "J102", "J103", "J104", "J105", "J201", "J501", "J502", "J503", "V1", "V2", "V3", "V4"}
