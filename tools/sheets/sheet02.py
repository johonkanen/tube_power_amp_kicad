#!/usr/bin/env python3
"""Sheet 2 - Bias regulator (PDF page 2): PNP pair Q2/Q3 (tail resistor R17 from HT +6) compares
OTGND with the tap of the divider R19-R21 / R22 and drives Q1 (shunt transistor to B-); BIASPOTX
and BIASPOTO (through R23 to OTGND) go to the bias trimmers.
The terminal VS' (KiCad refdes VS_PRIME) is a part on its own net (#00043), NOT the net VS' of
sheet 1: no label on it. The terminal VCC is on net HT +6."""
from _common import *  # noqa: F401,F403

sh = sheet("02_bias_regulator.kicad_sch")

TAIL, BM, OTG = 59, 107, 117       # rows: emitter rail, B- rail, OTGND rail (PDF render, 10 px units)

# VCC / HT +6, tail resistor R17 (#00038)
term(sh, "VCC", *P(69, 31), "up")
_, r17t, r17b = vert2(sh, "R", "R17", *P(69, 46), sh_value("R17"), top=1)
sh.wire(P(69, 31), r17t)
sh.wire(P(69, 37), P(57, 37))
sh.junction(*P(69, 37))
sh.glabel("HT +6", *P(57, 37), 180)
sh.wire(r17b, P(69, TAIL))

# Q2 (base left, emitter up: mirrored), Q3 (base right, emitter up)
q2 = sh.place("MPSA92", "Q2", *P(59, 67), 0, mirror="x", value=sh_value("Q2"),
              ref_at=(*P(63, 64), 0, "left"), value_at=(*P(63, 66), 0, "left"))
q3 = sh.place("MPSA92", "Q3", *P(79, 67), 180, value=sh_value("Q3"),
              ref_at=(*P(84, 60), 0, "left"), value_at=(*P(84, 74), 0, "left"))
sh.wire(q2.pin(1), P(61, TAIL), P(77, TAIL), q3.pin(1))
sh.junction(*P(69, TAIL))

# Q2 collector: Q1 base, R18 to B- (#00034)
q1 = sh.place("TIPL760", "Q1", *P(97, 91), value=sh_value("Q1"))
_, r18t, r18b = vert2(sh, "R", "R18", *P(61, 100), sh_value("R18"), top=1)
sh.wire(q2.pin(3), r18t)
sh.wire(P(61, 91), q1.pin(1))
sh.junction(*P(61, 91))

# B- rail: R18, Q3 collector, Q1 emitter
sh.wire(r18b, P(61, BM), P(99, BM), q1.pin(3))
sh.wire(q3.pin(3), P(77, 112))
sh.junction(*P(77, BM))
sh.glabel("B-", *P(77, 112), 270)

# divider VS' terminal - R19 - R20 - R21 - (Q3 base, #00039) - R22 - (Q1 collector, BIASPOTX, #00035)
term(sh, "VS_PRIME", *P(99, 27), "up")
prev = P(99, 27)
for ref, y in (("R19", 36), ("R20", 48), ("R21", 60), ("R22", 76)):
    _, t, b = vert2(sh, "R", ref, *P(99, y), sh_value(ref), top=1)
    sh.wire(prev, t)
    prev = b
sh.wire(q3.pin(2), P(99, 67))
sh.junction(*P(99, 67))
sh.wire(prev, q1.pin(2))
term(sh, "BIASPOTX", *P(119, 67), "right")
sh.wire(P(99, 83), P(115, 83), P(115, 67), P(119, 67))
sh.junction(*P(99, 83))

# BIASPOTO - R23 - OTGND (#00044)
term(sh, "BIASPOTO", *P(119, 91), "right")
_, r23t, r23b = vert2(sh, "R", "R23", *P(113, 100), sh_value("R23"), top=2)
sh.wire(r23t, P(113, 91), P(119, 91))

# OTGND rail: Q2 base, R23
sh.glabel("OTGND", *P(40, OTG), 180)
sh.wire(P(40, OTG), P(113, OTG), r23b)
sh.wire(q2.pin(2), P(51, 67), P(51, OTG))
sh.junction(*P(51, OTG))

sh.text("The terminal VS' (refdes VS_PRIME) is its own net, not the net VS' of sheet 1 (STANDBY, R13-R16).", *P(40, 126))
sh.text("The terminal VCC is on the heater net HT +6 (sheet 1: +6, HT+6, U8/U9 pin 2).", *P(40, 129))
sh.save()
print("sheet02: written")
