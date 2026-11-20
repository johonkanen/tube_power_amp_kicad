"""proteus2kicad configuration of the OUTPUT board (tools in tools/p2k, see its README).

Plain Python; every value here is specific to this board. Coordinates in mm, IPC frame (Y up).
Phase 0 (2026-11-20): sheets, IPC fix-ups, expected counts, layers, drills, outline.
"""

PROJECT = "tube_power_amp"  # KiCad project / library name

# Sources (relative to the repo root). The CADCAM export with Gerber X2 attributes.
CADCAM = "source/cadcam"
IPC = "source/cadcam/tube_output - CADCAM Netlist.IPC"

# --- Schematic skeleton (make_skeleton) ----------------------------------------------

# (Proteus page, sheet name, file). The 2010 PDF pages have no title block (no PATH or
# title field, and ROOT.DSN / PROJECT.XML carry no sheet names), so the names describe the
# page content (STATUS.md "Phase 0"); rename here before make_skeleton if wanted.
SHEETS = [
    (1, "Output stage", "01_output_stage.kicad_sch"),      # U6-U9 EL34, R1-R16, C1-C4, OT
    (2, "Bias regulator", "02_bias_regulator.kicad_sch"),  # Q1-Q3, R17-R23, VS' divider, BIASPOTX/O
    (3, "Bias supply", "03_bias_supply.kicad_sch"),        # D1-D5, R24/R25, C5/C6, B-, VREF
]
SCH_TITLE = "Tube power amplifier"
SCH_COMPANY = "Tube amplifier"
SCH_REV = "rev A (as built)"
SCH_COMMENT = "Redrawn from Proteus OUTPUT"
SCH_NOTE = ("Tube power amplifier (4x EL34) rev A - redrawn from Proteus OUTPUT (2010).\n"
            "One sheet per Proteus PDF page. Net names follow the IPC-D-356A netlist "
            "(reference/pins_by_net.md).")

# --- IPC-D-356A fix-ups (ipc356) -----------------------------------------------------

# Truncated refdes (IPC 6-char field) -> full Proteus refdes, from the schematic PDF and
# ROOT.DSN. BIASPO is two parts (sheet 2): BIASPOTX at the R22 / Q1 collector node, BIASPOTO
# at R23, so both are keyed by their pad coordinate (um). "VA GND" and "REFGND" are exactly
# 6 characters and complete.
TRUNCATED_REFDES = {
    "STANDB": "STANDBY",
    ("BIASPO", -27305, -13970): "BIASPOTX",
    ("BIASPO", 3175, -6985): "BIASPOTO",
    "BIASGN": "BIASGND",
    "P.I.GN": "P.I.GND",
}
# Expected net per restored refdes, keyed by the KiCad refdes (ipc356 --check looks the KiCad
# name up; a key that matches no part is silently ignored - "P.I.GND" was, until Phase 2).
TRUNCATED_NETS = {
    "STANDBY": "VS'",
    "BIASPOTX": "#00035",   # R22-2, Q1-2
    "BIASPOTO": "#00044",   # R23-2
    "BIASGND": "OTGND",
    "PI_GND": "#00023",     # with VA GND and R9-R12 pin 2
}

# Full Proteus refdes -> KiCad refdes (KiCad references: letter first, then letters, digits,
# '_'; no spaces, '+', '-', '.', "'"). Every script that compares against the IPC goes through
# this table (ipc356_pads.json carries it). Sign convention as tube_psu: + -> P, - -> N.
KICAD_REFDES = {
    "+6": "P6",
    "-6": "N6",
    "HT+6": "HT_P6",
    "HT -6": "HT_N6",
    "HT-0": "HT_0",
    "VA GND": "VA_GND",
    "P.I.GND": "PI_GND",
    "VS'": "VS_PRIME",
    "IN6+7": "IN6_7",
    "IN8+9": "IN8_9",
}

# No Proteus power nets (no "=POWER" names) on this board; the named nets "HT +6", "VS'",
# "B-" and "OTGND" keep their IPC spelling (KiCad labels may contain spaces and quotes;
# tube_psu uses "-100V BIAS").
NET_ALIASES = {}

# Blank-refdes records: there are no vias and no free pads on this board; the 4 records
# without a net are the plated 3.0 mm mounting holes (6.35 mm pad on both layers).
VIA_DRILLS = ()
FREE_PAD_DRILLS = ()
HOLE_DRILLS = (3.0,)
HOLES_PLATED = True

# Expected counts in the Proteus file (PLAN.md section 1).
EXPECTED_IPC = {
    "nets": 43,           # NNAME declarations
    "records": 146,       # 142 component pads + 4 holes
    "refdes_raw": 72,     # 71 distinct refdes fields + the blank one of the holes
    "tht_records": 146,
    "smd_records": 0,
    "smd_top": 0,
    "smd_bottom": 0,
    "nc_pads": 0,         # pin 6 of U6-U9 has no net record at all (not N/C)
    "vias": 0,
    "free_pads": 0,
    "holes": 4,
    "parts": 72,          # named refdes after the truncation fix-up (BIASPO -> 2 parts)
}

# --- Gerbers (check_sources, later the PCB tools) ------------------------------------

# Proteus copper gerber name -> KiCad copper layer, User layer for the pour outlines
# (there are no pours on this board: no G36 regions).
COPPER = [
    ("Top Copper", "F.Cu", "User.1"),
    ("Bottom Copper", "B.Cu", "User.2"),
]
DRILL_PLATED = "Drill TOP-BOT Plated"
DRILL_NONPLATED = None    # no NonPlated drill file: the mounting holes are plated
OUTLINE = "Mechanical 1"
OUTLINE_RECT = (-104.14, -25.4, 238.76, 60.325)  # x, y, width, height

# --- Footprints (Phase 2, tools/gen_footprints.py, p2k check_footprints) ---------------

# Pad sizes: "kicad" (KiCad library pad sizes and drills, pad centres on the Proteus positions;
# the IPC-built footprints have the Proteus pads). Changing it is a user decision (Phase 3 DRC).
FOOTPRINT_PAD_SIZES = "kicad"
# Parts drawn in the PDF without a layout part (no IPC pads): no footprint.
OFF_BOARD_PARTS = {
    "OT": "off board: 1650TA output transformer (chassis-mounted), wired to the OT1 / OT2 terminals",
    "VA_PRIME": "off board: VA' terminal (output transformer centre tap supply) drawn in the PDF only",
}

# kicad/fp-lib-table written / checked by tools/gen_footprints.py (footprints.run).
FP_LIB_TABLE = True
# THT parts on the bottom (solder) side: they fit the IPC pads only mirrored (check_footprints).
BOTTOM_THT = {r: "octal socket on the solder side (user decision 2026-11-20, STATUS.md Findings 10)"
              for r in ("U6", "U7", "U8", "U9")}

# --- ERC (p2k erc) ---------------------------------------------------------------------

# A wired no-connect pin is a netlist error for this conversion (KiCad: warning), STATUS.md "Phase 4".
ERC_FATAL_WARNINGS = {"no_connect_connected"}

# --- Pin order (p2k check_pin_order; playbook Phase 2, STATUS.md "Pin order") ------------

# The UNMOVED KiCad base footprints with the Proteus renumbering, fitted onto the IPC pads. Inline
# and two-pad parts fit both ways round: their body markers were compared on the renders
# (reports/pin_order/); `polarity` states the pin on the marked base pad 1. The octal: KiCad's
# Valve_Octal (2.54 mm grid) never fits closely; only its MIRRORED fit matches the Proteus ids, as
# does an ideal standard octal on the Proteus 17.20 mm pitch circle (pad 1 at -45 deg, counter-
# clockwise in KiCad's top view = clockwise seen from the pin side). The project footprint has the
# standard numbering in its own view and fits the IPC pads only mirrored: bottom side (Phase 5).
_OCTAL = "tube_power_amp:Valve_Octal_Belton_PCD17.20mm"
_IDEAL_OCTAL = dict(n=8, pcd=17.2, step=45, start=-45, pad=3.81, drill=1.6)
_U6_U9 = "U6 U7 U8 U9"
PIN_ORDER = [
    dict(refs="Q1", footprint="Package_TO_SOT_THT:TO-220-3_Vertical", mirror=False, res=0.01),
    dict(refs="Q2 Q3", spec="TO-92_Inline_P2.03mm", mirror=False, res=0.51,
         note="TO-92_Inline_Wide is P2.54, Proteus P2.032"),
    dict(refs="D1 D2 D3 D4 D5", spec="D_DO-41_SOD81_P10.16mm_Horizontal_AK", polarity="K", mirror=False, res=0.01),
    dict(refs="C5", spec="CP_Radial_D10.0mm_P5.00mm_PM", polarity="+", mirror=False, res=0.01),
    dict(refs="C6", spec="CP_Radial_D10.0mm_P5.08mm_PM", polarity="+", mirror=False, res=0.05,
         note="P5.00 vs P5.08"),
    dict(refs=_U6_U9, footprint="Valve:Valve_Octal", mirror=True, res=2.3,
         note="only the mirrored KiCad octal matches the Proteus ids"),
    dict(name="ideal octal", refs=_U6_U9, ideal=_IDEAL_OCTAL, mirror=True, res=0.01, other=0.01),
    dict(name="octal footprint", footprint=_OCTAL, on_ideal=_IDEAL_OCTAL, mirror=False, res=0.01, other=0.01,
         note="standard octal numbering in its own view"),
    dict(name="octal on IPC", refs=_U6_U9, footprint=_OCTAL, mirror=True, res=0.01, other=0.01,
         note="fits only mirrored = bottom side"),
]
PIN_ORDER_BOTTOM = {"U6", "U7", "U8", "U9"}

# --- PCB (Phase 3, build_pcb) ----------------------------------------------------------

# The 4 IPC 'hole' records: plated 3.0 mm holes with a 6.35 mm pad on both layers, no net.
HOLE_FOOTPRINT = "tube_power_amp:MountingHole_3.0mm_PTH_Pad6.35mm"
HOLE_VALUE = "MountingHole_3.0mm"
# Board thickness: 1.6 mm, the 2010 standard; the 2010 fab READ-ME (source/fab_2010) gives no
# stack-up. The 2026 export's READ-ME lists Proteus 8's default 2-layer stack (2 x 0.036 Cu +
# 1.483 FR4 = 1.555 mm, + 2 x 0.01 resist), written when the design was re-saved, not the 2010 order.
PCB_THICKNESS = 1.6
# Design rules from the Proteus copper as built (STATUS.md "Phase 3", kipy -m p2k.measure_gaps), mm.
# No vias on this board: the via values are only the netclass defaults.
PCB_RULES = dict(
    min_track=0.5,        # thinnest conductor draw 0.508 (20 mil)
    min_via=0.6,          # no vias (netclass default only)
    min_annular=0.1,
    min_drill=0.7,        # smallest drill 0.762 (Proteus) / 0.8 (KiCad footprints)
    clearance=0.38,       # smallest different-net gap 0.381 (15 mil, pad-track); pad-pad 0.508, track-track 1.016
    hole_clearance=0.25,  # drill to other-net copper: >= 0.381 gap + annular ring
    hole_to_hole=1.0,     # smallest drill-to-drill 1.270 (Proteus), 1.232 with the KiCad TO-92 drills
    edge_clearance=0.5,   # copper to outline >= 0.635
    track=0.508,          # Default netclass
    via=0.8,
    via_drill=0.4,
)
# DRC error types that remain by design (p2k drc; STATUS.md "Phase 3", remaining DRC items).
DRC_ACCEPTED = {
    "courtyards_overlap": "KiCad courtyards vs the Proteus placement (6: R24/R25 with each other "
                          "and R25 with C5/C6/D5, R18 with Q2/Q3; the octal sockets are on the bottom "
                          "side since Phase 5)",
    "pth_inside_courtyard": "VB6-VB9 terminal pads in the bottom-side octal socket courtyard (Proteus "
                            "placement: pad centre 0.07 mm outside the socket body outline)",
}

# --- Phase 4 checks (p2k.gerber_roundtrip, p2k.ipc356_diff) ---------------------------

# The June 2010 fab Excellon drill file (inch, 146 hits, same frame as the 2026 X2 export):
# gerber_roundtrip reads it in its own unit and compares it 1:1 with the Proteus plated drill gerber.
DRILL_EXCELLON = "source/fab_2010/OUTPUT - CADCAM Drill.TXT"
# KiCad footprint drills smaller than the Proteus drill, accepted by the user (2026-11-20):
# C1-C4 C_Rect film caps and C5/C6 CP_Radial keep the KiCad 1.0 mm drills. The pad set makes both
# checks require exactly these 12 pads with the smaller drill.
DRILL_SMALLER = {
    (1.143, 1.0): ("C1-C6: KiCad C_Rect / CP_Radial 1.0 mm drills kept (Proteus 1.143 = 45 mil); user decision 2026-11-20",
                   {"C1", "C2", "C3", "C4", "C5", "C6"}),
}
