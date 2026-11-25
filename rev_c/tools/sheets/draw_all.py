#!/usr/bin/env python3
"""Draw the three power amp rev C sheets and write lib/footprint_map.csv and
bom/tube_power_amp_revc_bom.csv from the same part list.

Rev C (rev_c/PLAN.md, user decisions 2026-11-25): minimal parts. Bias from one OPA462 (180 V op amp)
per tube driven by a DAC7578; cathode currents read across the 1 ohm shunts by ADS1115s; no hardware
protection logic (the control board's FPGA does the protections and self-checks); no HV_PERMIT loop.
Sheet 01 (output stage, tabs, open-load clamps) is rev B's, unchanged apart from the HF decoupling
caps, which are dropped.

Netlist-first drawing, as rev B: every part on a grid, a wire stub and a label on every pin (local
label on one sheet, global label across sheets, a power symbol for the rails). Exact for ERC and
the netlist; a tidy layout pass comes later.

Grounds: GND = AGND, the local star at the GND_PWR tab (J101 pin 2): output stage, bias channels,
DAC, ADCs. GNDD = the DGND island (the two ribbon headers and W09's BIAS_RTN tab), joined to GND by
one soft tie (10 ohm || 100 nF) on sheet 03. I2C crosses through 100 ohm.
Run from anywhere: python3 rev_c/tools/sheets/draw_all.py
"""
import math
import os
import sys

RB = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("P2K_BOARD", RB)
sys.path.insert(0, os.path.join(RB, "..", "tools", "p2k"))
from p2k.sch_builder import Sheet, lib  # noqa: E402
from p2k.sexpr import find, find_all  # noqa: E402

POWER = {"GND", "GNDD", "+5V", "+15V"}
MULTI = {"EL34"}
PARTS = {}   # ref -> (symbol, value), filled in the collect pass
GRID = 2.54
KEEP_REFS = {"J501", "J502"}   # W14-b / W15-b keep rev B's refs (interfaces.md 2.4), though drawn on sheet 03


def g(v):
    return round(round(v / 1.27) * 1.27, 2)


def at(c, r):
    """Grid cell (column c, row r) -> schematic mm."""
    return g(30.48 + c * 20.32), g(35.56 + r * 17.78)


class Drawer:
    def __init__(self, fname, mode, globals_=frozenset()):
        self.fname, self.mode, self.globals = fname, mode, globals_
        self.nets = set()
        self.sheet_no = int(fname[:2])
        self.count = {}
        self.refmap = {}
        self.real = set()
        self.nflag = 0
        self.sh = Sheet(os.path.join(RB, "kicad", fname)).clear() if mode == "draw" else None
        if self.sh is not None:
            self.sh.pwr = self.sheet_no * 100   # #PWR / #FLG numbers unique across sheets

    def auto_ref(self, ref, sym):
        """Unique reference per sheet: prefix letter + sheet number x 100 + a running number
        (V1-V4 and #FLG keep their names; a multi-unit part keeps its first ref)."""
        if ref in KEEP_REFS:              # interface connector refs from interfaces.md 2.4
            self.real.add(ref)
            return ref
        if ref.startswith(("V", "#")):
            if ref.startswith("V"):
                self.real.add(ref)
            return ref
        if sym in MULTI and ref in self.refmap:
            return self.refmap[ref]
        pre = "TP" if ref.startswith("TP") else ref[0]
        self.count[pre] = self.count.get(pre, 0) + 1
        new = f"{pre}{self.sheet_no * 100 + self.count[pre]}"
        self.refmap[ref] = new
        self.real.add(new)
        return new

    def part(self, sym, ref, c, r, nets, value=None, rot=0, unit=1, stub=GRID):
        ref = self.auto_ref(ref, sym)
        if self.mode == "collect" and not ref.startswith("#"):
            if ref not in PARTS or (value and len(value) > len(PARTS[ref][1] or "")):
                PARTS[ref] = (sym, value or PARTS.get(ref, (sym, ""))[1])
        for n in nets.values():
            if n and n != "NC":
                self.nets.add(n)
        if self.mode != "draw":
            return ref
        x, y = at(c, r)
        p = self.sh.place(sym, ref, x, y, rot=rot, unit=unit, value=value)
        dirs = {}
        for sub in find_all(lib()[sym], "symbol"):
            u = int(sub[1].rsplit("_", 2)[-2])
            if u not in (0, unit):
                continue
            for pn in find_all(sub, "pin"):
                dirs[str(find(pn, "number")[1])] = float(find(pn, "at")[3])
        for pin, net in nets.items():
            if not net:
                continue
            x0, y0 = p.pin(pin)
            if net == "NC":
                self.sh.no_connect(x0, y0)
                continue
            out = (dirs[str(pin)] + 180 + rot) % 360
            a = math.radians(out)
            x1, y1 = g(x0 + math.cos(a) * stub), g(y0 - math.sin(a) * stub)
            self.sh.wire((x0, y0), (x1, y1))
            lrot = int(round(out / 90.0)) * 90 % 360
            if net in POWER:
                self.sh.power(net, x1, y1)
            elif net in self.globals:
                self.sh.glabel(net, x1, y1, rot=lrot)
            else:
                self.sh.label(net, x1, y1, rot=lrot)
        return ref

    def flag(self, net, c, r):
        self.nflag += 1
        self.part("PWR_FLAG", f"#FLG{self.sheet_no * 100 + self.nflag}", c, r, {1: net}, value="PWR_FLAG")

    def text(self, s, c, r, size=1.27):
        if self.mode == "draw":
            self.sh.text(s, *at(c, r), size=size)

    def save(self):
        if self.mode == "draw":
            self.sh.save()


# ------------------------------------------------------------------ helpers
def R(d, ref, c, r, a, b, v, rot=90):
    return d.part("R", ref, c, r, {1: a, 2: b}, value=v, rot=rot)


def C(d, ref, c, r, a, b, v, rot=0):
    return d.part("C", ref, c, r, {1: a, 2: b}, value=v, rot=rot)


def CP(d, ref, c, r, plus, minus, v, rot=0):
    return d.part("C_Polarized", ref, c, r, {1: plus, 2: minus}, value=v, rot=rot)


def NPN(d, ref, c, r, b, cc, e, v):
    # SOT-23 BJT symbols with numbered pins (1 B, 2 E, 3 C), so the footprint's pads match (layout)
    return d.part(v, ref, c, r, {1: b, 2: e, 3: cc}, value=v)


def PNP(d, ref, c, r, b, cc, e, v):
    return d.part(v, ref, c, r, {1: b, 2: e, 3: cc}, value=v)


def NMOS(d, ref, c, r, gate, drain, src="GND"):
    return d.part("2N7002", ref, c, r, {1: gate, 2: src, 3: drain}, value="2N7002")


TUBES = ((1, "V1", "DRV_A", "OT_A"), (2, "V2", "DRV_A", "OT_A"), (3, "V3", "DRV_B", "OT_B"), (4, "V4", "DRV_B", "OT_B"))


# ------------------------------------------------------------------ sheet 01
def sheet01(d):
    d.text("01 Output stage: 4 octal sockets (solder side, as built; standard octal numbering), per-tube 220n coupling "
           "cap and 91k grid leak to its own bias (BIASn, sheet 03), 5.6k grid stopper, 1k 5 W flameproof screen "
           "resistor from V_SCREEN, 1 ohm cathode shunt with a power diode and a Kelvin tap (KELVn) to the ADC (sheet 03).",
           0, -1.4, 2)
    d.text("Coupling cap 220 nF / 630 V film and grid leak 91k for all four types (decided 2026-11-23, V1 / V2): grid "
           "circuit 91k + 5.6k + 1k = 98 kOhm. 6550 DEVIATION: twice its 50 kOhm fixed-bias rating (Tung-Sol), accepted; "
           "covered by the cold-default bias and the FPGA's per-tube current loop and over-current cut-off (rev C). "
           "Within rating for 6L6GC / KT88 (100k) and EL34 (500k).", 6, 9.3, 1.6)
    d.text("Ground: GND = AGND, the local star at the GND_PWR tab (J101 pin 2). The cathode shunts, the drive grounds "
           "(W24, solid at this end), the HV decoupling and the bias circuit return here. Heaters float: no heater "
           "reference on this board (interfaces.md 5). OT secondary COM is not connected here.", 0, -0.9, 1.6)
    # power tabs and connectors
    d.part("Conn_01x02", "J101", 0, 1, {1: "V_ANODE", 2: "GND"}, value="W04-b V_ANODE / GND_PWR (4.8 mm tabs)")
    d.part("Conn_01x01", "J102", 0, 2.6, {1: "V_SCREEN"}, value="W05-b V_SCREEN (4.8 mm tab)")
    d.part("Conn_01x02", "J103", 0, 4, {1: "HTR1", 2: "HTR2"}, value="W06-b HEATER (6.3 mm tabs)")
    d.part("Conn_01x03", "J104", 0, 5.6, {1: "OT_A", 2: "OT_B", 3: "V_ANODE"}, value="W11-a OT_A / OT_B / OT_CT (4.8 mm tabs)")
    d.part("Conn_02x03_Top_Bottom", "J105", 0, 7.6, {1: "GND", 2: "DRV_A", 3: "GND", 4: "DRV_B", 5: "GND", 6: "NC"},
           value="W24-b DRIVE (Mini-Fit Jr 2x3, 600 V; 280-390 V DC on pins 2 / 4)")
    for i, n in enumerate(("V_ANODE", "V_SCREEN", "HTR1", "HTR2", "GND")):
        d.flag(n, 2, 1 + i * 0.7)
    d.text("Rev C: no local HF decoupling on V_ANODE / V_SCREEN (rev B's 100n/630V proposal dropped, minimal parts)", 2.6, 2.3)
    # open-load protection (decided 2026-11-23, V3): fitted
    for k, (side, ot) in enumerate((("A", "OT_A"), ("B", "OT_B"))):
        d.part("D", f"D1{k}1", 3 + k * 1.6, 4, {1: ot, 2: "GND"}, value="RGP02-20E (2 kV, plate diode)", rot=90)
        d.part("D_TVS", f"D1{k}2", 3 + k * 1.6, 5.2, {1: ot, 2: f"CL_{side}"}, value="P6KE350CA (TVS, bidirectional)", rot=90)
        d.part("D_TVS", f"D1{k}3", 3 + k * 1.6, 6.4, {1: f"CL_{side}", 2: "V_ANODE"}, value="P6KE350CA (TVS, bidirectional)", rot=90)
    d.text("Open-load protection, FITTED (docs/output_stage_stability.md): one 2 kV diode from GND to each plate (no "
           "series string, so no sharing resistors); 2x P6KE350CA in series from each plate to the centre tap "
           "(V_ANODE): 664-736 V string, off with a load at full overdrive, plates held at about 1.1-1.2 kV when the "
           "speaker is pulled. OT_A / OT_B / CL_x reach 1.25 kV to GND: >= 6.3 mm creepage and clearance (slots).", 2.6, 7.4)
    # tubes
    for n, v, drv, ot in TUBES:
        c0 = 6 + (n - 1) * 5
        d.text(f"{v}: {'side A' if ot == 'OT_A' else 'side B'}", c0, 0.4)
        C(d, f"C1{n}0", c0, 1, drv, f"GRID{n}", "220n/630V MKP", rot=90)
        R(d, f"R1{n}0", c0 + 1, 2, f"GRID{n}", f"BIAS{n}", "91k", rot=0)
        R(d, f"R1{n}1", c0 + 2, 1, f"GRID{n}", f"G1_{n}", "5.6k", rot=90)
        R(d, f"R1{n}2", c0 + 2, 3, "V_SCREEN", f"G2_{n}", "1k 5W flameproof", rot=90)
        d.part("EL34", v, c0 + 3, 2, {1: f"K{n}", 3: ot, 4: f"G2_{n}", 5: f"G1_{n}", 8: f"K{n}"},
               value="EL34 / 6L6GC / KT88 / 6550 (octal)", unit=1)
        d.part("EL34", v, c0 + 3, 6, {2: "HTR1", 7: "HTR2"}, value="EL34", unit=2)
        R(d, f"R1{n}3", c0 + 1, 4.5, f"K{n}", "GND", "1R 1W", rot=0)
        d.part("D", f"D1{n}3", c0 + 1, 5.5, {1: "GND", 2: f"K{n}"}, value="S3M (3 A)", rot=0)
        d.part("NetTie_2", f"NT1{n}", c0 + 1, 7, {1: "GND", 2: f"KELV{n}"}, value="Kelvin at shunt pad")
        # cathode test pads (layout 2026-11-24, user C6): the shunt voltage, 1 mV = 1 mA, probed from below
        d.part("TestPoint", f"TP1{n}0", c0 + 2.6, 4.5, {1: f"K{n}"}, value=f"K{n} (1 mV/mA)")
        d.part("TestPoint", f"TP1{n}1", c0 + 2.6, 7.0, {1: f"KELV{n}"}, value=f"K{n} GND")
    d.text("Pin 1 (g3 on EL34, NC on 6L6GC / KT88 / 6550) tied to pin 8 as built (PA-3). Pin 6 left free (internal "
           "on some types). UL taps of the 1650TA unused (VOX-10 / D7 reserved, not on this board).", 6, 8.2)
    d.text("Kelvin: each NetTie sits on its shunt's GND pad; KELVn runs as its own trace to the ADC's reference "
           "(sheet 03) and K n as the signal trace; the shunt's current goes straight to the GND_PWR star.", 6, 8.7)


# ------------------------------------------------------------------ sheet 02
def sheet02(d):
    d.text("02 -80 V input, 2.5 V reference, bias DAC (I2C 0x4A, resets to zero scale) and four bias channels: one OPA462 "
           "(180 V) per tube on +15 V / -80 V. Vout = 29 x 0.920 x Vdac - 70 V: DAC 0 = -70 V (cold), full scale = -3.3 V. "
           "rev_c/PLAN.md.", 0, -1.4, 2)
    d.part("Conn_01x02", "J201", 0, 1, {1: "M80_IN", 2: "GNDD"}, value="W09-b -80V / BIAS_RTN (4.8 mm tabs)")
    d.text("BIAS_RTN lands on the DGND island (grounding.md 4). -80 V +-2 V, 25 mA requested; rev C draws at most "
           "14.8 mA (four OPA462 at 3.7 mA max) + about 1 mA.", 0, 2.2)
    R(d, "R201", 2, 1, "M80_IN", "M80", "10R 1W fusible wirewound", rot=90)
    d.part("D", "D201", 3, 2, {1: "GND", 2: "M80"}, value="S1G (reverse clamp)")
    CP(d, "C201", 4, 2, "GND", "M80", "100u/100V 105C")
    C(d, "C202", 5, 2, "GND", "M80", "100n/100V")
    d.flag("M80", 3, 3.4)
    d.text("100 uF: hold-up for the op amps' negative rail (about 10 V drop in 60 ms at 15 mA), so the FPGA sees a "
           "falling -80 V on the ADC (sheet 03) before the bias moves", 2.6, 3.9)
    # reference and DAC
    d.part("ADR4525", "U201", 1, 5.5, {2: "+5V", 4: "GND", 6: "VREF2V5", 1: "NC", 3: "NC", 5: "NC", 7: "NC", 8: "NC"},
           value="ADR4525 (2.5 V, 0.02 %, 2 ppm/K)")
    C(d, "C203", 0, 6.5, "+5V", "GND", "1u")
    C(d, "C204", 3, 6.5, "VREF2V5", "GND", "1u")
    d.part("DAC7578xPW", "U202", 1, 9.5, {1: "GND", 2: "+5V", 3: "+5V", 4: "DAC1", 13: "DAC2", 5: "DAC3", 12: "DAC4",
                                          6: "NC", 7: "NC", 10: "NC", 11: "NC", 8: "VREF2V5", 9: "+5V",
                                          14: "GND", 15: "I2C_SDA_A", 16: "I2C_SCL_A"},
           value="DAC7578SPW (12-bit x8, I2C 0x4A)")
    C(d, "C205", 3, 8.5, "+5V", "GND", "100n")
    d.text("DAC7578 TSSOP-16: power-on reset to zero scale (TSSOP parts, TI). ADDR0 = VDD -> 0x4A (GND 0x48 and "
           "float 0x4C; 0x48 / 0x49 / 0x4B are the ADCs). ~LDAC = GND (outputs update on write), ~CLR = VDD (unused). "
           "Outputs E-H unused. VREF2V5 also sets the bias offset (Rg) and is read back by ADC3.", 0, 11.6)
    for n in range(1, 5):
        c0 = 5 + (n - 1) * 5
        r0 = 4.6
        d.text(f"Channel {n} (V{n})", c0, r0 - 0.4)
        R(d, f"R2{n}0", c0, r0 + 0.4, f"DAC{n}", f"IN{n}", "10k", rot=90)
        R(d, f"R2{n}1", c0 + 0.8, r0 + 1.6, f"IN{n}", "GND", "115k", rot=0)
        C(d, f"C2{n}0", c0, r0 + 1.6, f"IN{n}", "GND", "330n")
        d.part("OPA462", f"U2{n}0", c0 + 2.4, r0 + 1.4,
               {3: f"IN{n}", 2: f"FB{n}", 6: f"OA{n}", 7: "+15V", 4: "M80", 9: "M80", 8: "+5V", 1: "GND", 5: "NC"},
               value="OPA462DDA (180 V)")
        R(d, f"R2{n}2", c0 + 1.6, r0 + 3.4, f"FB{n}", "VREF2V5", "10k 0.1%", rot=0)
        R(d, f"R2{n}3", c0 + 3.0, r0 + 3.4, f"OA{n}", f"FB{n}", "280k 0.1%", rot=0)
        R(d, f"R2{n}4", c0 + 4.0, r0 + 0.4, f"OA{n}", f"BIAS{n}", "1k", rot=90)
        C(d, f"C2{n}2", c0 + 4.4, r0 + 1.6, f"BIAS{n}", "GND", "1u/100V")
        C(d, f"C2{n}3", c0 + 1.2, r0 + 5.6, "+15V", "GND", "100n")
        C(d, f"C2{n}4", c0 + 2.2, r0 + 5.6, "GND", "M80", "100n/100V")
    d.text("Per channel: DAC -> 10k / 115k (k = 0.920; the 115k holds the input at 0 V = cold if the DAC output is "
           "high-Z) with 330n (50 Hz); OPA462 non-inverting, Rf / Rg = 280k / 10k to VREF2V5 (0.1 %: sets the cold "
           "point -70.0 V); no cap across Rf (sim P1: phase margin 81 deg without it, 48 deg with 1n); 1k / 1u to BIASn (the tube's 91k grid leak, sheet 01). E/D Com = GND, E/D = +5 V "
           "(enabled; E/D low would leave the output high-Z). Status flag unused. PowerPAD (pin 9) = V- = -80 V copper. "
           "Input CM 0-2.3 V within (V-)+1 .. (V+)-3; supply 95-97 V of 12-180 V; Iq 3.2 / 3.7 mA; about 0.35 W each.",
           5, 11.2)
    d.text("Placement: op amps >= 30 mm from a socket centre, DAC / reference / 0.1 % resistors >= 40 mm (interfaces.md 12.5).",
           5, 12.4)


# ------------------------------------------------------------------ sheet 03
def sheet03(d):
    d.text("03 Cathode-current ADCs (ADS1115, differential across each 1 ohm shunt, +-0.256 V = 0-256 mA, 7.8 uA / count), "
           "rail and reference readback, ribbons W14-b / W15-b on the DGND island, soft tie. The FPGA does the "
           "over-current cut-off and the rail checks from these readings (rev_c/PLAN.md F1-F5).", 0, -1.4, 2)
    d.part("Conn_02x07_Odd_Even", "J501", 0, 2, {1: "+5V", 2: "GNDD", 3: "+15V", 4: "GNDD", 5: "NC", 6: "GNDD",
                                                  7: "NC", 8: "GNDD", 9: "NC", 10: "NC", 11: "NC", 12: "NC",
                                                  13: "NC", 14: "GNDD"},
           value="W14-b CONTROL (template 2x7)")
    d.text("W14 (interfaces.md 6.1): rev C uses only +5 V, +15 V and GND. -15 V (5), SPI (7, 9, 10, 11), MUTE_ALL_N (12) "
           "and RESET_N (13) are not connected: no expander, no -15 V load.", 0, 3.6)
    for i, n in enumerate(("+5V", "+15V", "GNDD")):
        d.flag(n, 2, 1 + i * 0.6)
    d.part("Conn_02x05_Odd_Even", "J502", 0, 5.5, {1: "GNDD", 2: "SCL_R", 3: "GNDD", 4: "SDA_R", 5: "GNDD",
                                                    6: "NC", 7: "NC", 8: "NC", 9: "NC", 10: "GNDD"},
           value="W15-b BIAS (2x5)")
    d.text("W15 (rev C): 1 GND, 2 SCL, 3 GND, 4 SDA, 5 GND, 6-9 spare (were BIAS_EN, BIAS_OK, OC_TRIP_N, HV_PERMIT_MON), 10 GND. "
           "I2C 5 V, 100 kHz.", 0, 7.0)
    R(d, "R301", 3, 5, "SCL_R", "I2C_SCL_A", "100R", rot=90)
    R(d, "R302", 3, 6, "SDA_R", "I2C_SDA_A", "100R", rot=90)
    R(d, "R303", 4.5, 4.4, "+5V", "I2C_SCL_A", "4.7k", rot=0)
    R(d, "R304", 5.3, 4.4, "+5V", "I2C_SDA_A", "4.7k", rot=0)
    R(d, "R305", 0, 9, "GNDD", "GND", "10R", rot=90)
    C(d, "C301", 1, 9, "GNDD", "GND", "100n", rot=90)
    d.text("Soft tie GNDD - GND (AGND star), the only DGND-AGND join (grounding.md 4)", 0, 9.8)
    CP(d, "C302", 3, 9, "+15V", "GND", "10u/25V")
    CP(d, "C303", 4, 9, "+5V", "GND", "10u/10V")
    # ADCs
    ADDR = {1: ("GND", "0x48"), 2: ("+5V", "0x49"), 3: ("I2C_SCL_A", "0x4B")}
    for k in (1, 2, 3):
        c0 = 7 + (k - 1) * 5.5
        if k < 3:
            a, b = 2 * k - 1, 2 * k
            ins = {4: f"S{a}P", 5: f"S{a}N", 6: f"S{b}P", 7: f"S{b}N"}
        else:
            ins = {4: "MON_M80", 5: "MON_P15", 6: "VREF2V5", 7: "MON_P5"}
        d.part("ADS1115IDGS", f"U30{k}", c0 + 2.5, 2, {1: ADDR[k][0], 2: "NC", 3: "GND", 8: "+5V", 9: "I2C_SDA_A",
                                                     10: "I2C_SCL_A", **ins}, value=f"ADS1115IDGS (I2C {ADDR[k][1]})")
        C(d, f"C3{k}0", c0 + 4, 1, "+5V", "GND", "100n")
        if k < 3:
            for j, t in enumerate((a, b)):
                r = 4.5 + j * 2.4
                d.text(f"V{t}: shunt 1 ohm, K{t} - KELV{t}", c0, r - 0.5)
                R(d, f"R3{k}{j}0", c0 + 1, r, f"K{t}", f"S{t}P", "1k", rot=90)
                R(d, f"R3{k}{j}1", c0 + 1, r + 1, f"KELV{t}", f"S{t}N", "1k", rot=90)
                C(d, f"C3{k}{j}1", c0 + 2.6, r + 0.5, f"S{t}P", f"S{t}N", "1u", rot=0)
    c0 = 7 + 2 * 5.5
    R(d, "R330", c0, 4.5, "M80", "MON_M80", "536k 1206", rot=90)
    R(d, "R331", c0 + 1.5, 5.3, "MON_M80", "VREF2V5", "10k", rot=0)
    C(d, "C331", c0 + 2.5, 5.3, "MON_M80", "GND", "100n")
    R(d, "R332", c0, 6.8, "+15V", "MON_P15", "100k", rot=90)
    R(d, "R333", c0 + 1.5, 7.6, "MON_P15", "GND", "20k", rot=0)
    R(d, "R334", c0, 9.0, "+5V", "MON_P5", "10k", rot=90)
    R(d, "R335", c0 + 1.5, 9.8, "MON_P5", "GND", "10k", rot=0)
    d.text("ADC3 (0x4B): AIN0 -80 V (offset divider to VREF2V5: 0.99 V at -80 V, 2.45 V at 0 V), AIN1 +15 V (/6), "
           "AIN2 VREF2V5 direct (the external reference against the ADC's internal one), AIN3 +5 V (/2). "
           "ADDR: GND 0x48, VDD 0x49, SCL 0x4B (ADS1115 datasheet table 7-2); SDA (0x4A) unused, it is the DAC's.", 7, 11.2)
    d.text("Shunt inputs: 1k in each leg, 1u across the pair (80 Hz differential, anti-aliasing). Not 10k: the ADS1115's "
           "differential input impedance at +-0.256 V is about 710 kOhm, so 2x 10k would read about 2.8 % low (2x 1k: 0.3 %, "
           "calibrated out). The S3M across the shunt holds K below about 1.2 V; 1k limits a negative cathode transient "
           "into the input diodes to 10 mA at -10 V. "
           "ALERT/RDY unused (the FPGA polls).", 7, 12.2)


# ------------------------------------------------------------------ footprints and BOM
LOC = "tube_power_amp_revc:"
R0805, R1206 = "Resistor_SMD:R_0603_1608Metric", "Resistor_SMD:R_1206_3216Metric"   # R0805 = the default chip size (0603 since the layout)
AX0207 = "Resistor_THT:R_Axial_DIN0207_L6.3mm_D2.5mm_P10.16mm_Horizontal"
SOT23 = "Package_TO_SOT_SMD:SOT-23"
SYMFP = {   # symbol -> (footprint, candidate part, note)
    "EL34": (LOC + "Valve_Octal_Belton_PCD17.20mm", "Belton octal PCB socket (as rev A)", "solder side, as built"),
    "2N7002": (SOT23, "2N7002,215 (Nexperia)", ""),
    "BAT54S": (SOT23, "BAT54S,215 (Nexperia)", ""),
    "Q_PMOS_GDS": ("Package_TO_SOT_SMD:SOT-223-3_TabPin2", "BSP92P H6327 (Infineon)", "250 V"),
    "NetTie_2": ("NetTie:NetTie-2_SMD_Pad0.5mm", "", "Kelvin tap at the shunt pad"),
    "TestPoint": ("TestPoint:TestPoint_Pad_D2.0mm", "", "cathode test pad, probed from below"),
    "OPA462": ("Package_SO:TI_SO-PowerPAD-8_ThermalVias", "OPA462DDAR (TI, 180 V)", "PowerPAD = V- (-80 V): copper area for 0.35 W; confirm the pad against DDA0008J"),
    "ADS1115IDGS": ("Package_SO:MSOP-10_3x3mm_P0.5mm", "ADS1115IDGSR (TI)", "VSSOP-10 (DGS)"),
    "DAC7578xPW": ("Package_SO:TSSOP-16_4.4x5mm_P0.65mm", "DAC7578SPW (TI)", "TSSOP: power-on reset to zero scale (TI)"),
    "ADR4525": ("Package_SO:SOIC-8_3.9x4.9mm_P1.27mm", "ADR4525BRZ (ADI)", ""),
    "ADS7828": ("Package_SO:TSSOP-16_4.4x5mm_P0.65mm", "ADS7828E (TI)", "-40 to 85 C: keep it at the cool end"),
    "OPA4197xD": ("Package_SO:SOIC-14_3.9x8.7mm_P1.27mm", "OPA4197IDR (TI)", ""),
    "LM2901": ("Package_SO:SOIC-14_3.9x8.7mm_P1.27mm", "LM2901BIDR (TI, -40 to 125 C)", "orderable suffix to confirm"),
    "LM4040DBZ-10": (SOT23, "LM4040A10IDBZR (TI)", "10 V only in I grade (-40 to 85 C)"),
    "74HC74": ("Package_SO:TSSOP-14_4.4x5mm_P0.65mm", "74HC74PW (Nexperia)", ""),
    "74HC4060": ("Package_SO:SOIC-16_3.9x9.9mm_P1.27mm", "74HC4060D (Nexperia)", ""),
    "74LVC1G11": ("Package_TO_SOT_SMD:SOT-363_SC-70-6", "74LVC1G11GW (Nexperia)", ""),
    "74LVC1G08": ("Package_TO_SOT_SMD:SOT-353_SC-70-5", "74LVC1G08GW (Nexperia)", ""),
    "74LVC2G17": ("Package_TO_SOT_SMD:SOT-363_SC-70-6", "74LVC2G17GW (Nexperia)", ""),
    "PC817": ("Package_DIP:SMDIP-4_W7.62mm", "PC817X1NIP1B (Sharp, SMD gull wing)", "7.62 mm row spacing keeps the heater-side isolation"),
    "MCP23S17x-x-SS": ("Package_SO:SSOP-28_5.3x10.2mm_P0.65mm", "MCP23S17-E/SS (Microchip)", ""),
    "D_Bridge_+AA-": ("Package_TO_SOT_SMD:TO-269AA", "MB1S (onsemi)", ""),
    "Conn_02x07_Odd_Even": ("Connector_IDC:IDC-Header_2x07_P2.54mm_Vertical", "61201421621 (Wurth)", "shrouded, keyed"),
    "Conn_02x05_Odd_Even": ("Connector_IDC:IDC-Header_2x05_P2.54mm_Vertical", "61201021621 (Wurth)", "shrouded, keyed"),
}
TAB48 = "2x PCB blade tab 4.8 mm (0.187 in), 2 legs on 5.00 mm, 1.4 mm holes (interfaces.md 4.1); order code to confirm"
CONN = {"J101": (LOC + "BladeTab_4.8mm_x2_P10.20mm_Inline", TAB48, "fully insulated receptacles; in line on 10.2 mm"),
        "J102": (LOC + "BladeTab_4.8mm_x1", TAB48.replace("2x ", "1x "), "fully insulated receptacle"),
        "J103": (LOC + "BladeTab_6.3mm_x2_P11.50mm", TAB48.replace("4.8 mm (0.187 in)", "6.3 mm (0.250 in)"), "6.4 A; tabs on 11.5 mm"),
        "J104": (LOC + "BladeTab_4.8mm_x3_OT", TAB48.replace("2x ", "3x "), "OT_A / OT_CT / OT_B at 0 / 26.4 / 52.8 mm, OT_CT 6.5 mm forward"),
        "J105": ("Connector_Molex:Molex_Mini-Fit_Jr_5566-06A_2x03_P4.20mm_Vertical", "Molex 39-28-1063 class (Mini-Fit Jr 5566-06A; order code to confirm)",
                 "600 V AC/DC; housing 39-01-2060, terminals 39-00-0039; circuit 6 N/C"),
        "J201": (LOC + "BladeTab_4.8mm_x2_P9.50mm", TAB48, "fully insulated receptacles")}


REF_FP = {   # per-part footprint exceptions (rev B layout 2026-11-24): R111 = V3 screen resistor, same ref in rev C
    "R111": (LOC + "R_Axial_Power_L25.0mm_W9.0mm_P10.16mm_Vertical_Tight", "1k 5 W flameproof metal oxide, standing",
             "V3's screen resistor stands on F in the V2-V3 gap (no room for a lying one)"),
}


def footprint_for(ref, sym, v):
    v = v or ""
    if ref in REF_FP:
        return REF_FP[ref]
    if sym.startswith("Conn"):
        return CONN.get(ref) or SYMFP[sym]
    if sym in SYMFP:
        return SYMFP[sym]
    if sym == "R":
        if v.startswith("1k 5W"):
            return ("Resistor_THT:R_Axial_Power_L25.0mm_W6.4mm_P27.94mm", "1k 5 W flameproof metal oxide (25 x 6.4 mm, as rev A)",
                    "layout 2026-11-24: mounted lying on the B (plate) side, body raised 2 mm, hand-soldered")
        if "fusible" in v:
            return ("Resistor_THT:R_Axial_DIN0309_L9.0mm_D3.2mm_P12.70mm_Horizontal", "CRF251-4 / CRF110 10R (Yageo Vitrohm)",
                    "fusible wirewound; inrush of C201 (8 A peak, 0.32 J) to confirm")
        if v.startswith("1R"):
            return "Resistor_SMD:R_2512_6332Metric", "1R 1 W 1 % 50 ppm/K metal strip (2512)", ""
        if ref[2:3] == "1" and ref[1] == "1" and len(ref) == 4 and ref[3] in "01" and ref[2] in "1234":
            pass
        if v == "91k":
            return ("Resistor_SMD:R_2512_6332Metric", "91k 1 % 2512 high-voltage thick film, >= 500 V working (KOA HV732H / Vishay CRHV class)",
                    "grid leak; -240 V blocking transient across it (layout 2026-11-24: SMD on the B side)")
        if v == "5.6k":
            return R1206, "5.6k 1 % 1206 (200 V)", "grid stopper inside the socket's pin circle, at pin 5 (layout)"
        if v == "330R 0.5W":
            return R1206, "330R 1 % 1206 (about 0.05 W)", "heater sense, heater potential"
        if "0.1%" in v:
            return R1206, f"{v.split()[0]} 0.1 % 25 ppm/K thin film 1206", ""
        if v.startswith(("280k", "536k")):
            return R1206, f"{v.split()[0]} 1206 (200 V)", "up to 80 V across it"
        if v.endswith("M") or v in ("3.3k 1206", "1.3k 0.25W", "330R 0.5W", "1.0k"):
            return R1206, f"{v.split()[0]} 1 % 1206", ""
        return R0805, f"{v.split()[0]} 1 % 0603", ""
    if sym in ("C", "C_Polarized"):
        if "630V" in v and "MKP" in v:
            return ("Capacitor_THT:C_Rect_L26.5mm_W8.5mm_P22.50mm_MKS4", "220n 630 V MKP, P 22.5 mm (WIMA MKP4 26.5 x 7 / Kemet R76 class)",
                    "body width <= 8.5 mm (layout)")
        if "630V" in v:
            return "Capacitor_SMD:C_1812_4532Metric", "100n 630 V X7R 1812", ""
        if "100u/100V" in v:
            return "Capacitor_THT:CP_Radial_D10.0mm_P5.00mm", "UPW2A101MPD (Nichicon, 105 C)", ""
        if v == "10u/100V 105C":
            return "Capacitor_THT:CP_Radial_D6.3mm_P2.50mm", "UPW2A100MED (Nichicon, 105 C)", ""
        if "X7S 1210" in v:
            return "Capacitor_SMD:C_1210_3225Metric", "GRM32EC72A106KE05 (Murata)", "about 30 % left at 72 V"
        if "/100V" in v:
            return "Capacitor_SMD:C_0805_2012Metric", f"{v.split('/')[0]} 100 V X7R / X7S 0805 (GRM21BC72A105 class for 1 uF)", ""
        if v.startswith("10u"):
            return "Capacitor_SMD:C_1206_3216Metric", f"{v} X7R 1206", ""
        if v.startswith(("220n", "330n")):
            return "Capacitor_SMD:C_0805_2012Metric", f"{v} 50 V X7R 0805 (C0G 1206 preferred)", ""
        return "Capacitor_SMD:C_0603_1608Metric", f"{v} 50 V X7R 0603", ""
    if sym in ("D", "D_Schottky", "D_Zener", "D_TVS"):
        table = {"UF4007": ("Diode_THT:D_DO-41_SOD81_P10.16mm_Horizontal", "UF4007"),
                 "RGP02-20E": ("Diode_THT:D_DO-41_SOD81_P10.16mm_Horizontal", "RGP02-20E-E3/54 (Vishay, 2 kV, 0.5 A, 300 ns)"),
                 "P6KE350CA": ("Diode_THT:D_DO-15_P10.16mm_Horizontal", "P6KE350CA (Littelfuse; VBR 332-368 V, VC 482 V at 1.24 A)"),
                 "S3M": ("Diode_SMD:D_SMC", "S3M-E3/57T (Vishay)"), "S1G": ("Diode_SMD:D_SMA", "S1G (1N4004 class)"),
                 "1N4148W": ("Diode_SMD:D_SOD-123", "1N4148W-7-F (Diodes Inc)"), "BAS416": ("Diode_SMD:D_SOD-323", "BAS416,115 (Nexperia)"),
                 "BZT52H": ("Diode_SMD:D_SOD-123F", "BZT52H-B36,115 (Nexperia)"), "BAT54": ("Diode_SMD:D_SOD-323", "BAT54J (Nexperia)"),
                 "BZX84C2V4": (SOT23, "BZX84-C2V4,215 (Nexperia)")}
        for k, (fp, mpn) in table.items():
            if v.startswith(k):
                return fp, mpn, ("1 cm2 cathode copper (150 K/W)" if k == "BZT52H" else "")
    if sym in ("MMBT3904", "MMBT3906", "MMBTA92", "MMBTA42"):
        return SOT23, {"MMBT3904": "MMBT3904 (Nexperia)", "MMBT3906": "MMBT3906 (Nexperia)", "MMBTA92": "MMBTA92 (300 V)",
                       "MMBTA42": "MMBTA42 (300 V)"}[v], ""
    raise KeyError(f"no footprint rule for {ref} {sym} {v}")


def write_parts():
    import csv
    rows = []
    for ref in sorted(PARTS, key=lambda r: (r[0], int("".join(ch for ch in r[1:] if ch.isdigit()) or 0))):
        sym, v = PARTS[ref]
        if sym == "BAT54S" and v and v.startswith("BAV199"):
            fp, mpn, note = SOT23, "BAV199,215 (Nexperia)", "low leakage"
        else:
            fp, mpn, note = footprint_for(ref, sym, v)
        rows.append((ref, sym, v, fp, mpn, note))
    with open(os.path.join(RB, "lib", "footprint_map.csv"), "w", newline="") as f:
        f.write("# generated by tools/sheets/draw_all.py (rev C); PLACEHOLDER in the name = not final\n")
        w = csv.writer(f)
        w.writerow(["refdes", "footprint", "value"])
        for r in rows:
            w.writerow([r[0], r[3], r[2]])
    groups = {}
    for ref, sym, v, fp, mpn, note in rows:
        groups.setdefault((v, fp, mpn, note), []).append(ref)
    os.makedirs(os.path.join(RB, "bom"), exist_ok=True)
    with open(os.path.join(RB, "bom", "tube_power_amp_revc_bom.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["refs", "qty", "value", "footprint", "candidate part", "note"])
        for (v, fp, mpn, note), refs in sorted(groups.items(), key=lambda kv: kv[1][0]):
            w.writerow([" ".join(refs), len(refs), v, fp, mpn, note])
    return len(rows), len(groups)


SHEETS = [("01_output_stage.kicad_sch", sheet01), ("02_bias.kicad_sch", sheet02),
          ("03_sense_ribbons.kicad_sch", sheet03)]


def main():
    seen = {}
    for f, fn in SHEETS:
        d = Drawer(f, "collect")
        fn(d)
        for n in d.nets:
            seen.setdefault(n, set()).add(f)
    glob = frozenset(n for n, fs in seen.items() if len(fs) > 1 and n not in POWER)
    nparts, nlines = write_parts()
    print(f"parts: {nparts}, BOM lines: {nlines}")
    total = 0
    for f, fn in SHEETS:
        d = Drawer(f, "draw", glob)
        fn(d)
        d.save()
        total += len(d.real)
    single = sorted(n for n, fs in seen.items() if len(fs) == 1)
    print(f"nets: {len(seen)}, global: {len(glob)}, symbols placed (units of a part counted once): {total}")


if __name__ == "__main__":
    main()
