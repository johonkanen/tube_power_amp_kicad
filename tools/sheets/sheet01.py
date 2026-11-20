#!/usr/bin/env python3
"""Sheet 1 - Output stage (PDF page 1): four EL34 (U6-U9) in push-pull parallel. Per tube: coupling
capacitor, grid stop, bias feed (BIASx), 1R cathode sense resistor (VBx) and 1K/5W screen resistor
from the net VS' (STANDBY terminal). U8/U9 anodes -> OT1 / OT P1, U6/U7 anodes -> OT2 / OT P2.
The output transformer OT and the terminal VA' are drawn in the PDF but are not on the board.

Differences from the PDF drawing (same nets): the KiCad EL34 symbol has G3 on the right and the
cathode at the bottom, so the G3-cathode link and the cathode row run below the tube; the heaters
are the second unit of each tube and are drawn as a block of their own (right), with the heater
terminals HT+6, +6, HT-0, -6 and HT -6 next to them."""
from _common import *  # noqa: F401,F403

sh = sheet("01_output_stage.kicad_sch")

XIN, XGND, XVS, XOT = 13, 65, 129, 169      # columns (PDF render, 10 px units): input, cathode ground, VS', anodes

ch9 = tube_channel(sh, "U9", "C1", "R1", "R5", "BIAS9", "R9", "VB9", "R13", cy=15, by=31, xj=43, xjog=69, xk=86, xvb=93)
ch8 = tube_channel(sh, "U8", "C2", "R2", "R6", "BIAS8", "R10", "VB8", "R14", cy=43, by=57, xj=41, xjog=75, xk=90, xvb=97)
ch7 = tube_channel(sh, "U7", "C3", "R3", "R7", "BIAS7", "R11", "VB7", "R15", cy=87, by=101, xj=41, xjog=81, xk=90, xvb=97)
ch6 = tube_channel(sh, "U6", "C4", "R4", "R8", "BIAS6", "R12", "VB6", "R16", cy=115, by=129, xj=41, xjog=95, xk=76, xvb=89,
                   vb_left=True)

# inputs: IN8+9 -> C1, C2 (#00033); IN6+7 -> C3, C4 (#00028)
for ref, y, a, b in (("IN8_9", 29, ch9, ch8), ("IN6_7", 101, ch7, ch6)):
    term(sh, ref, *P(9, y), "left")
    sh.wire(P(9, y), P(XIN, y))
    xi = P(XIN, 0)[0]
    sh.wire(a["in"], (xi, a["in"][1]), (xi, b["in"][1]), b["in"])
    sh.junction(*P(XIN, y))

# cathode resistor ground bus (#00023): R9-R12 pin 2, P.I.GND, VA GND
top, bot = ch9["gnd"][1], ch6["gnd"][1]
xg = P(XGND, 0)[0]
sh.wire(ch9["gnd"], (xg, top), (xg, bot))
for ch in (ch8, ch7):
    sh.wire(ch["gnd"], (xg, ch["gnd"][1]))
    sh.junction(xg, ch["gnd"][1])
sh.wire(ch6["gnd"], P(51, 127), P(51, 131))
sh.junction(xg, bot)
term(sh, "PI_GND", *P(51, 131), "down")
sh.wire((xg, bot), P(XGND, 131))
term(sh, "VA_GND", *P(XGND, 131), "down")

# screen supply VS' (R13-R16 pin 2, STANDBY); local label: the net is only on this sheet
xv = P(XVS, 0)[0]
sh.wire(ch9["vs"], (xv, ch9["vs"][1]), (xv, ch6["vs"][1]), ch6["vs"])
for ch in (ch8, ch7):
    sh.wire(ch["vs"], (xv, ch["vs"][1]))
    sh.junction(xv, ch["vs"][1])
term(sh, "STANDBY", *P(153, 77), "right")
sh.wire(P(122, 77), P(153, 77))
sh.junction(*P(XVS, 77))
sh.label("VS'", *P(122, 77), 180)

# anodes: U9, U8 -> OT1, OT P1 (#00000); U7, U6 -> OT2, OT P2 (#00006)
ot = sh.place("OT_1650TA", "OT", *P(181, 63), value=sh_value("OT"))
sh.wire(ch9["anode"], P(107, 3), P(XOT, 3), P(XOT, 59), ot.pin("P1"))
sh.wire(ch8["anode"], P(107, 33), P(XOT, 33))
sh.junction(*P(XOT, 33))
term(sh, "OT1", *P(177, 33), "right")
sh.wire(P(XOT, 33), P(177, 33))
sh.wire(ot.pin("P2"), P(XOT, 67), P(XOT, 105))
sh.wire(ch7["anode"], P(107, 71), P(XOT, 71))
sh.junction(*P(XOT, 71))
sh.wire(ch6["anode"], P(107, 105), P(XOT, 105))
sh.junction(*P(XOT, 105))
term(sh, "OT2", *P(177, 105), "right")
sh.wire(P(XOT, 105), P(177, 105))
# OT centre tap -> VA' (off-board terminal); secondaries open in the PDF
term(sh, "VA_PRIME", *P(159, 63), "left")
sh.wire(P(159, 63), ot.pin("CT"))
for s in ("S1", "S2", "S3", "S4", "S5"):
    sh.no_connect(*ot.pin(s))

# heaters (unit 2): +6 -> U9, U8 -> HT-0 (#00004) -> U7, U6 -> -6 (#00010)
HY, R6P, R0, R6N = 20, 34, 40, 46          # heater units row; rails HT +6, HT-0, -6
XL, XR = 205, 265
for ref, x, ra, rb in (("U9", 213, R6P, R0), ("U8", 227, R6P, R0), ("U7", 241, R0, R6N), ("U6", 255, R0, R6N)):
    h = sh.place(sym(ref), ref, *P(x, HY), unit=2, value=sh_value(ref))
    sh.wire(h.pin(2), P(x - 2, ra))
    sh.wire(h.pin(7), P(x + 2, rb))
    sh.junction(*P(x - 2, ra))
    if (x + 2, rb) != (215, R0):           # the HT-0 rail starts at U9 pin 7
        sh.junction(*P(x + 2, rb))
sh.wire(P(XL, R6P), P(XR, R6P))
sh.wire(P(215, R0), P(XR, R0))
sh.wire(P(XL, R6N), P(XR, R6N))
term(sh, "P6", *P(XL, R6P), "left")
term(sh, "HT_P6", *P(XR, R6P), "right")
term(sh, "HT_0", *P(XR, R0), "right")
term(sh, "N6", *P(XL, R6N), "left")
term(sh, "HT_N6", *P(XR, R6N), "right")
sh.wire(P(207, R6P), P(207, 30))
sh.junction(*P(207, R6P))
sh.glabel("HT +6", *P(207, 30), 90)

sh.text("Heaters (unit 2 of U6-U9), drawn at the tubes in the PDF", *P(205, 8))
sh.text("OT (1650TA) and VA' are not on the board: OT1 / OT2 are the board's connections to the transformer primary.", *P(9, 146))
sh.text("PDF terminal names: +6 = P6, -6 = N6, HT+6 = HT_P6, HT -6 = HT_N6, HT-0 = HT_0, P.I.GND = PI_GND, "
        "VA GND = VA_GND, IN8+9 = IN8_9, IN6+7 = IN6_7, VA' = VA_PRIME.", *P(9, 149))
sh.text("Pin 6 of the EL34 sockets has no net (as in Proteus).", *P(9, 152))
sh.save()
print("sheet01: written")
