"""proteus2kicad configuration of the OUTPUT board (tools in tools/p2k, see its README).

Plain Python; every value here is specific to this board. Coordinates in mm, IPC frame (Y up).
Phase 0 fills in the rest (SHEETS names, IPC fix-ups, expected counts, layers, rules).
"""

PROJECT = "tube_power_amp"  # KiCad project / library name

# Sources (relative to the repo root). The CADCAM export with Gerber X2 attributes.
CADCAM = "source/cadcam"
IPC = "source/cadcam/tube_output - CADCAM Netlist.IPC"

# (Proteus page, sheet name, file): names to be taken from the PDF title blocks in Phase 0
SHEETS = [
    (1, "Sheet 1", "01_sheet1.kicad_sch"),
    (2, "Sheet 2", "02_sheet2.kicad_sch"),
    (3, "Sheet 3", "03_sheet3.kicad_sch"),
]
SCH_TITLE = "Tube power amplifier"
SCH_COMPANY = "Tube amplifier"
SCH_REV = "rev A (as built)"
SCH_COMMENT = "Redrawn from Proteus OUTPUT"
