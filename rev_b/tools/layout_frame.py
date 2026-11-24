#!/usr/bin/env python3
"""Power amp rev B: board frame and interface positions, the one place the layout reads them from.

Chassis frame (D748 top plate, mm): x along the front from the left, y from the front panel's inner
face (y = 0) to the rear, plan view from above. The board hangs 15 mm below the plate, components
down (KiCad F side faces down, away from the plate); the octal sockets are on the B side (toward the
plate) and the tubes stand on top of the plate through the 30 mm holes.

Rev A (2010 OUTPUT) to chassis: X = 414.95 - x_revA, Y = 152.45 - y_revA (KiCad mm, y down;
mechanical/README.md "Board positions in D748": mirrored, offset (414.95, 152.45)).
Rev B KiCad frame (planned for the layout, keeps rev A's geometry on a positive page area):
x_k = 620 - X, y_k = 250 - Y, i.e. rev A + (205.05, 97.55). The KiCad F view is the chassis plan
mirrored left-right (east end on the left).

Status: layout sketch of 2026-11-24 (interfaces only, STATUS.md "Layout sketch: interfaces").
"""

# ---- board -------------------------------------------------------------------------------------
OUTLINE = (280.33, 127.05, 519.09, 187.38)          # x0, y0, x1, y1 (rev A outline, 238.76 x 60.33)
THICK, STANDOFF = 1.6, 15.0                          # board, standoff below the plate


def to_kicad(x, y):
    return round(620.0 - x, 3), round(250.0 - y, 3)


# Octal sockets (rev A centres, chassis frame). V1 / V2 = side A (OT_A), V3 / V4 = side B (OT_B).
SOCKETS = {"V1": (296.55, 172.13), "V2": (362.59, 172.13), "V3": (428.63, 172.13), "V4": (494.67, 172.13)}
PIN_CIRCLE_R = 8.6                                    # Belton PCD 17.2 mm, pads 3.81 / drill 1.6 (as rev A)
# Rev B socket rotation: pin 3 (plate) points to the front (-y); plan view runs 1 -> 8 counter-clockwise
# (checked on rev A's U6: pin 2 front, pin 3 front-east). Pin n at angle -90 + (n - 3) * 45 deg.
# Result: 3 plate front, 4 G2 front-east, 5 G1 east, 6 NC rear-east, 7 heater rear, 8 K rear-west,
# 1 K west, 2 heater front-west. Rev A had pin 2 at the front (rev B = rev A turned 45 deg clockwise).
PIN3_ANGLE = -90.0

# Mounting holes (board holes 3.2 mm, NOT plated, 4 mm copper keep-out; grounding.md: no chassis net).
HOLES_KEPT = {"H3": (514.95, 131.45), "H4": (284.95, 131.45)}       # rev A H3 / H4: on D748 holes
# Rear support: rev A's H1 / H2 (514.95 / 284.95, 182.45) have no plate hole. Preferred: two of the old
# chassis-socket flange holes that are already in the plate (D748, 3.5 mm, unused) under the board.
HOLES_REAR_PREFERRED = {"H1": (513.5, 179.0), "H2": (315.4, 178.9)}
HOLES_REAR_ALT = {"H1": (514.95, 182.45), "H2": (284.95, 182.45)}  # rev A positions: new plate holes

# ---- connectors leaving the board (chassis frame) -----------------------------------------------
# pin1 = chassis position of pin 1; pins listed where the pattern matters.
CONNECTORS = {
    # W24 drive, Molex Mini-Fit Jr 5566-06A 2x3 vertical, 4.2 mm, F side (down), receptacle from below.
    "J105": dict(cable="W24-b", mate="PI + FX J201", fp="Molex_Mini-Fit_Jr_5566-06A_2x03_P4.20mm_Vertical",
                 pins={1: (286.50, 141.00), 2: (290.70, 141.00), 3: (294.90, 141.00),
                       4: (286.50, 146.50), 5: (290.70, 146.50), 6: (294.90, 146.50)},
                 body=(283.30, 138.25, 298.11, 150.25)),
    # W14 / W15 ribbons, shrouded IDC, F side. Preferred: the control board moves J4 and J5 by -8.90 mm in x;
    # J502 then sits one row behind J501 (clear of H3), so neither ribbon passes under the other's socket.
    "J501": dict(cable="W14-b", mate="control board J4", fp="IDC-Header_2x07_P2.54mm_Vertical",
                 pin1=(490.50, 132.80), long_axis="-x", odd_row="front (y 132.80), even row y 135.34",
                 body=(469.66, 128.12, 496.10, 139.02)),
    "J502": dict(cable="W15-b", mate="control board J5", fp="IDC-Header_2x05_P2.54mm_Vertical",
                 pin1=(512.50, 140.20), long_axis="-x", odd_row="front (y 140.20), even row y 142.74",
                 body=(496.74, 135.52, 518.10, 146.42)),
    "J503": dict(cable="W16-a", mate="HV supplies J501", fp="Molex_KK-254_AE-6410-02A_1x02_P2.54mm_Vertical",
                 pin1=(491.00, 146.50), long_axis="+x", body=(489.23, 143.08, 495.32, 149.88)),
    # Blade tabs: 2 legs on 5.00 mm, 1.4 mm drill (interfaces.md 4.1); env = insulated receptacle envelope.
    "J101": dict(cable="W04-b", mate="HV supplies J201", tabs={1: ("V_ANODE", 514.50, 161.00), 2: ("GND_PWR", 514.50, 170.50)},
                 width=4.8, blade="y"),
    "J102": dict(cable="W05-b", mate="HV supplies J202", tabs={1: ("V_SCREEN", 514.50, 151.50)}, width=4.8, blade="y"),
    "J103": dict(cable="W06-b", mate="tube PSU HT_6V3 / HT_GND", tabs={1: ("HTR1", 390.00, 181.00), 2: ("HTR2", 401.50, 181.00)},
                 width=6.3, blade="x"),
    "J104": dict(cable="W11-a", mate="output transformer primary (P1 / P2 / CT)",
                 tabs={1: ("OT_A", 393.00, 134.00), 3: ("OT_CT", 405.00, 134.00), 2: ("OT_B", 417.00, 134.00)},
                 width=4.8, blade="x"),
    "J201": dict(cable="W09-b", mate="tube PSU -80V OUT / SEC GND", tabs={1: ("-80V", 475.00, 147.00), 2: ("BIAS_RTN", 484.50, 147.00)},
                 width=4.8, blade="x"),
}
# Insulated receptacle envelopes (plan, mm) by tab width, blade plane along the long side.
RECEPTACLE = {4.8: (8.0, 6.5), 6.3: (9.5, 7.5)}

# ---- neighbours (chassis frame) -------------------------------------------------------------------
CTRL_J = {"J4": dict(pin1=(499.40, 115.73), n=14), "J5": dict(pin1=(521.40, 115.73), n=10),
          "J7": dict(pin1=(544.40, 115.73), n=10)}
CTRL_SHIFT_PROPOSED = -8.90     # J4 and J5 in x, for straight 1:1 W14 / W15 (J5 now ends past this board's east edge)
HV_TABS = {"J201": (527, 166, 10, 24), "J202": (527, 150, 10, 10), "J501": (562, 48, 7, 7)}   # x, y, w, h (lower-left)
HV_OUTLINE = [(560, 30), (649, 30), (649, 39), (668, 39), (668, 30), (675, 30), (675, 145), (649, 145), (649, 180),
              (585, 180), (585, 200), (525, 200), (525, 127), (560, 127)]
OT_LEAD_HOLES = [(331.4, 90.1), (415.5, 90.1)]       # 15 mm, 1650TA leads
OT_SCREWS = [(331.4, 52.0), (331.4, 128.1), (415.5, 52.0), (415.5, 128.1)]   # 3.5 mm; two are over this board's front edge
OLD_SOCKET_HOLES = [(277.8, 165.3), (315.4, 178.9), (343.8, 165.3), (381.4, 179.0), (409.8, 165.3), (447.4, 179.0),
                    (475.9, 165.3), (513.5, 179.0)]   # 3.5 mm, the old chassis-socket flange screws (r 20 from each socket)
BIAS_HOLES = [(279.1, 198.1, 6.0), (312.1, 198.1, 5.0), (345.1, 198.1, 6.0), (378.1, 198.1, 5.0), (411.1, 198.1, 6.0),
              (444.1, 198.1, 5.0), (477.2, 198.1, 6.0), (510.2, 198.1, 5.0)]   # old bias pots (6) / test points (5)
