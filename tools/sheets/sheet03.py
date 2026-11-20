#!/usr/bin/env python3
"""Sheet 3 - Bias supply (PDF page 3): bridge rectifier D1-D4 from the AC5/AC6 winding, R24 into
the negative bias rail B- (C5), R25 and zener D5 / C6 for the reference VREF. The positive side of
the bridge is the ground OTGND (the PDF writes 'otgnd'), so B- and VREF are negative."""
from _common import *  # noqa: F401,F403

sh = sheet("03_bias_supply.kicad_sch")

TOP, GND = 51, 75          # rows of the PDF render (10 px units): B- / VREF rail and OTGND rail


def diode(ref, y, left):
    return horiz2(sh, sym(ref), ref, *P(68, y), sh_value(ref), left=left, text="above")


_, d1k, d1a = diode("D1", 51, "K")
_, d2a, d2k = diode("D2", 63, "A")
_, d3a, d3k = diode("D3", 75, "A")
_, d4k, d4a = diode("D4", 87, "K")

# AC5: D1 cathode, D2 anode (#00045)
term(sh, "AC5", *P(43, 55), "up")
sh.wire(P(43, 55), P(43, 63), d2a)
sh.wire(d1k, P(63, 51), P(63, 63))
sh.junction(*P(63, 63))
# AC6: D3 anode, D4 cathode (#00046)
term(sh, "AC6", *P(43, 83), "down")
sh.wire(P(43, 83), P(43, 75), d3a)
sh.wire(d4k, P(63, 87), P(63, 75))
sh.junction(*P(63, 75))
# negative output of the bridge: D1, D4 anodes to R24 (#00047)
_, r24l, r24r = horiz2(sh, "R", "R24", *P(92, TOP), sh_value("R24"), left=2, text="above")
sh.wire(d1a, r24l)
sh.wire(d4a, P(79, 87), P(79, TOP))
sh.junction(*P(79, TOP))
# positive output: D2, D3 cathodes = OTGND rail
sh.wire(d2k, P(75, 63), P(75, GND))
sh.wire(d3k, P(146, GND))
sh.junction(*P(75, GND))
sh.glabel("OTGND", *P(146, GND), 0)

# B- rail: R24, C5, R25
_, r25l, r25r = horiz2(sh, "R", "R25", *P(114, TOP), sh_value("R25"), left=2, text="above")
sh.wire(r24r, r25l)
sh.wire(P(103, TOP), P(103, 43))
sh.glabel("B-", *P(103, 43), 90)
_, c5t, c5b = vert2(sh, "C_Polarized", "C5", *P(103, 63), sh_value("C5"), top="-")
sh.wire(c5t, P(103, TOP))
sh.wire(c5b, P(103, GND))
sh.junction(*P(103, TOP))
sh.junction(*P(103, GND))
term(sh, "BIASGND", *P(103, 81), "down")
sh.wire(P(103, GND), P(103, 81))

# VREF: R25, C6, zener D5 (#00050)
sh.wire(r25r, P(137, TOP))
_, c6t, c6b = vert2(sh, "C_Polarized", "C6", *P(123, 63), sh_value("C6"), top="-")
sh.wire(c6t, P(123, TOP))
sh.wire(c6b, P(123, GND))
sh.junction(*P(123, TOP))
sh.junction(*P(123, GND))
_, d5t, d5b = vert2(sh, "D_Zener", "D5", *P(137, 63), sh_value("D5"), top="A")
sh.wire(d5t, P(137, TOP))
sh.wire(d5b, P(137, GND))
sh.junction(*P(137, TOP))
sh.junction(*P(137, GND))
term(sh, "VREF", *P(137, 41), "up")
sh.wire(P(137, 41), P(137, TOP))
term(sh, "REFGND", *P(137, 81), "down")
sh.wire(P(137, GND), P(137, 81))

sh.text("PDF label 'otgnd' = net OTGND (Proteus net names are case-insensitive).", *P(43, 100))
sh.text("OTGND is the positive side of the bridge: B- (C5) and VREF (D5, 22 V) are negative.", *P(43, 103))
sh.save()
print("sheet03: written")
