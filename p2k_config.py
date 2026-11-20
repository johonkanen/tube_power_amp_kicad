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

# --- PCB (Phase 3, build_pcb) ----------------------------------------------------------

# The 4 IPC 'hole' records: plated 3.0 mm holes with a 6.35 mm pad on both layers, no net.
HOLE_FOOTPRINT = "tube_power_amp:MountingHole_3.0mm_PTH_Pad6.35mm"
HOLE_VALUE = "MountingHole_3.0mm"
