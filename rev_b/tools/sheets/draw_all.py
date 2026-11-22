#!/usr/bin/env python3
"""Draw the five power amp rev B sheets (initial schematic 2026-11-21; second pass 2026-11-23), and
write lib/footprint_map.csv and bom/tube_power_amp_revb_bom.csv from the same part list.

Second pass: interfaces.md IF-1.2 and the bias decisions of 2026-11-22 (bias_supply.md
"Corrections" / "Proposed wording"): two-pole sense filter (47k / 220 nF twice), 72 V zener
string with 3.3k, BIAS_OK from two real monitors (VNC, -80 V rail) and +15 V present, over-current
comparator 220 mA +-5 % (0.1 % divider), BIAS_EN pump behind 1k, Schmitt inputs on the slow lines.

Sources (tube_amplifier_kicad, read only): docs/bias_supply.md and sim/bias_supply (bias supply,
cathode-current sense, over-current trip), docs/interfaces.md IF-1.2 (connectors, ribbons 6.1 /
6.3, safety lines 8, map 7.3), docs/grounding.md (AGND star at GND_PWR, DGND island, soft tie,
100 ohm crossings), sim/power_stage (1k screen resistors, grid stoppers) and SPECIFICATION.md
PA-1..PA-6, SAFE-1..SAFE-6. Rev A (the 2010 OUTPUT board) is the mechanical reference only.

Netlist-first drawing, as tube_preamp_kicad rev_b: every part on a grid, a wire stub and a label
on every pin (local label on one sheet, global label across sheets, a power symbol for the
rails). Exact for ERC and the netlist; a tidy layout pass comes later.

Grounds: GND = AGND, the local star at the GND_PWR tab (output stage, the whole bias circuit,
DAC, ADC, comparators, safety logic). GNDD = the DGND island (the two ribbon headers, the
expander, W09's BIAS_RTN tab), joined to GND by one soft tie (10 ohm || 100 nF) on sheet 05.
Logic lines cross between the two through 100 ohm.
Run from anywhere: python3 rev_b/tools/sheets/draw_all.py
"""
import math
import os
import sys

RB = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("P2K_BOARD", RB)
sys.path.insert(0, os.path.join(RB, "..", "tools", "p2k"))
from p2k.sch_builder import Sheet, lib  # noqa: E402
from p2k.sexpr import find, find_all  # noqa: E402

POWER = {"GND", "GNDD", "+5V", "+15V", "-15V"}
MULTI = {"EL34", "OPA4197xD", "LM2901", "74HC74", "74LVC2G17"}
PARTS = {}   # ref -> (symbol, value), filled in the collect pass
GRID = 2.54


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
        if ref.startswith(("V", "#")):
            if ref.startswith("V"):
                self.real.add(ref)
            return ref
        if sym in MULTI and ref in self.refmap:
            return self.refmap[ref]
        pre = ref[0]
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
    return d.part("Q_NPN", ref, c, r, {"B": b, "C": cc, "E": e}, value=v)


def PNP(d, ref, c, r, b, cc, e, v):
    return d.part("Q_PNP", ref, c, r, {"B": b, "C": cc, "E": e}, value=v)


def NMOS(d, ref, c, r, gate, drain, src="GND"):
    return d.part("2N7002", ref, c, r, {1: gate, 2: src, 3: drain}, value="2N7002")


TUBES = ((1, "V1", "DRV_A", "OT_A"), (2, "V2", "DRV_A", "OT_A"), (3, "V3", "DRV_B", "OT_B"), (4, "V4", "DRV_B", "OT_B"))


# ------------------------------------------------------------------ sheet 01
def sheet01(d):
    d.text("01 Output stage: 4 octal sockets (solder side, as built; standard octal numbering), per-tube 220n coupling "
           "cap and 91k grid leak to its own bias (BIASn, sheet 03), 5.6k grid stopper, 1k 5 W flameproof screen "
           "resistor from V_SCREEN, 1 ohm cathode shunt with a power diode and a Kelvin tap (KELVn) to the sense amp (sheet 04).",
           0, -1.4, 2)
    d.text("Coupling cap 220 nF / 630 V film and grid leak 91k for all four types (decided 2026-11-23, V1 / V2): grid "
           "circuit 91k + 5.6k + 1k = 98 kOhm. 6550 DEVIATION: twice its 50 kOhm fixed-bias rating (Tung-Sol), accepted; "
           "covered by the cold-default bias, the firmware current loop and the hardware over-current trip. "
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
    C(d, "C101", 3, 1, "V_ANODE", "GND", "100n/630V")
    C(d, "C102", 3.8, 1, "V_SCREEN", "GND", "100n/630V")
    d.text("C101 / C102: local HF decoupling at the tabs (proposal; check with the HV supplies' output loop)", 2.6, 2.3)
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
    d.text("Pin 1 (g3 on EL34, NC on 6L6GC / KT88 / 6550) tied to pin 8 as built (PA-3). Pin 6 left free (internal "
           "on some types). UL taps of the 1650TA unused (VOX-10 / D7 reserved, not on this board).", 6, 8.2)
    d.text("Kelvin: each NetTie sits on its shunt's GND pad; KELVn runs as its own trace to the sense amp's reference "
           "(sheet 04) and K n as the signal trace; the shunt's current goes straight to the GND_PWR star.", 6, 8.7)


# ------------------------------------------------------------------ sheet 02
def sheet02(d):
    d.text("02 -80 V input, clean negative reference VNC (about -70.5 V, 72 V string), BIAS_OK monitors (VNC, -80 V rail, "
           "+15 V) and the BIAS_EN watchdog. docs/bias_supply.md (2026-11-22), rev_b/sim/bias_supply/monitors.py.", 0, -1.4, 2)
    d.part("Conn_01x02", "J201", 0, 1, {1: "M80_IN", 2: "GNDD"}, value="W09-b -80V / BIAS_RTN (4.8 mm tabs)")
    d.text("BIAS_RTN lands on the DGND island (grounding.md 4); the -80 V current returns mostly through GND_PWR. "
           "25 mA requested from the PSU, -80 V +-2 V, no hold-up required (interfaces.md 3.1)", 0, 2.2)
    R(d, "R201", 2, 1, "M80_IN", "M80", "10R 1W fusible wirewound", rot=90)
    d.part("D", "D201", 3, 2, {1: "GND", 2: "M80"}, value="S1G (reverse clamp)")
    CP(d, "C201", 4, 2, "GND", "M80", "100u/100V 105C")
    d.text("100 uF: the board's own hold-up behind the BIAS_OK timing (22-117 ms, 28-65 ms with the drawn monitors)", 2.6, 3.2)
    # zener reference
    R(d, "R202", 6, 1, "M80", "ZR", "3.3k 1206", rot=90)
    d.part("D_Zener", "D202", 7, 3, {1: "GND", 2: "Z1"}, value="BZT52H-B36 (2 %)")
    d.part("D_Zener", "D203", 7, 4.4, {1: "Z1", 2: "ZR"}, value="BZT52H-B36 (2 %)")
    d.text("72 V string (2x 36 V, 2 %, SOD123F on 1 cm2 cathode pads: 150 K/W, self-heating 13 K)", 7.4, 5.4)
    R(d, "R203", 8, 1, "ZR", "ZF", "100k", rot=90)
    d.part("D", "D204", 8, 2.4, {1: "ZR", 2: "ZF"}, value="1N4148W (speed-up)", rot=90)
    C(d, "C202", 9, 3, "ZF", "GND", "10u/100V X7S 1210")
    C(d, "C211", 9.8, 3, "ZF", "GND", "10u/100V X7S 1210")
    d.text("C202 / C211 ceramic, not electrolytic: the leakage of an electrolytic here (up to 3 uA) would shift VNC 0.3 V "
           "through the 100k", 8, 5.9)
    d.part("Q_PMOS", "Q201", 11, 1, {"G": "ZF", "D": "M80", "S": "VS1"}, value="BSP92P (250 V)")
    d.part("Q_PMOS", "Q202", 11, 3, {"G": "ZF", "D": "M80", "S": "VS2"}, value="BSP92P (250 V)")
    R(d, "R204", 12.5, 1, "VS1", "VNC", "10R", rot=90)
    R(d, "R205", 12.5, 3, "VS2", "VNC", "10R", rot=90)
    R(d, "R206", 14, 1, "VNC", "M80", "100k", rot=90)
    R(d, "R207", 14, 3, "GND", "VNC", "47k", rot=90)
    CP(d, "C203", 15, 2, "GND", "VNC", "10u/100V 105C")
    d.text("Two P-MOSFET followers in parallel: one open still regulates; both open -> VNC rises -> BIAS_OK low", 10, 4.4)
    # references
    R(d, "R208", 0, 6, "+15V", "VREF10", "1.0k", rot=90)
    d.part("LM4040DBZ-10", "U201", 1, 7, {1: "VREF10", 2: "GND", 3: "NC"}, value="LM4040A10 (10 V, 0.1 %)")
    C(d, "C204", 2, 7, "VREF10", "GND", "100n")
    R(d, "R209", 3, 6, "VREF10", "VREF5", "10k 0.1%", rot=0)
    R(d, "R210", 3, 8, "VREF5", "GND", "10k 0.1%", rot=0)
    C(d, "C205", 4, 7.6, "VREF5", "GND", "100n")
    d.text("VREF10 regulates down to +15 V = 11.5 V (1.0k, 1.3 mA of loads); LM4040 3.6 mA", 0, 9)
    # VNC monitor (unit A)
    R(d, "R211", 6, 6, "VNC", "MVA", "169k 0.1%", rot=90)
    R(d, "R212", 7, 6, "MVA", "MV", "234k 0.1%", rot=90)
    R(d, "R213", 8, 7, "MV", "VREF10", "29.4k 0.1%", rot=0)
    R(d, "R214", 9, 6, "MV", "MON_OV", "3.57M", rot=90)
    C(d, "C206", 7, 8, "MV", "GND", "10n")
    d.part("D", "D205", 8, 8.6, {1: "MV", 2: "GND"}, value="BAS416 (low leakage)", rot=90)
    d.part("LM2901", "U202", 11, 7, {5: "MV", 4: "VREF5", 2: "MON_OV"}, value="LM2901B", unit=1)
    R(d, "R215", 12.5, 6, "+15V", "MON_OV", "10k", rot=0)
    d.part("D", "D206", 13.5, 7, {1: "MON_FAULT", 2: "MON_OV"}, value="1N4148W", rot=90)
    d.text("VNC monitor: trip -63.0 V, release -64.5 V (0.1 % divider)", 6, 9.6)
    # rail monitor (unit B)
    R(d, "R216", 6, 10.5, "M80", "MR", "271k 0.1%", rot=90)
    R(d, "R217", 8, 11.5, "MR", "VREF10", "16.9k 0.1%", rot=0)
    R(d, "R218", 9, 10.5, "MR", "MON_OR", "7.32M", rot=90)
    C(d, "C207", 7, 12.5, "MR", "GND", "10n")
    d.part("D", "D207", 8, 13.1, {1: "MR", 2: "GND"}, value="BAS416 (low leakage)", rot=90)
    d.part("LM2901", "U202", 11, 11.5, {7: "MR", 6: "VREF5", 1: "MON_OR"}, value="LM2901B", unit=2)
    R(d, "R219", 12.5, 10.5, "+15V", "MON_OR", "10k", rot=0)
    d.part("D", "D208", 13.5, 11.5, {1: "MON_FAULT", 2: "MON_OR"}, value="1N4148W", rot=90)
    d.text("Rail monitor: trip -75.0 V, release -75.5 V (0.1 % divider)", 6, 14.1)
    # +15 V monitor (unit C)
    R(d, "R220", 15, 6, "+15V", "P15S", "42.2k", rot=90)
    R(d, "R221", 15, 8, "P15S", "GND", "10k", rot=90)
    C(d, "C208", 16, 8, "P15S", "GND", "100n")
    R(d, "R222", 15, 9.5, "VREF2V5", "PREF", "10k", rot=0)
    R(d, "R223", 16.5, 9.5, "PREF", "MON_O15", "2.37M", rot=0)
    d.part("LM2901", "U202", 18, 7.5, {11: "PREF", 10: "P15S", 13: "MON_O15"}, value="LM2901B", unit=3)
    R(d, "R224", 19.5, 6.5, "+15V", "MON_O15", "10k", rot=0)
    d.part("D", "D209", 20.5, 7.5, {1: "MON_FAULT", 2: "MON_O15"}, value="1N4148W", rot=90)
    d.text("+15 V present: trip 13.0 V, release 13.25 V, against VREF2V5 (from +5 V, independent of VREF10)", 15, 10.6)
    # combine
    R(d, "R225", 14.5, 13, "MON_FAULT", "GND", "100k", rot=90)
    d.part("LM2901", "U202", 18, 12.5, {9: "VREF5", 8: "MON_FAULT", 14: "OKH"}, value="LM2901B", unit=4)
    R(d, "R226", 19.5, 11.5, "+15V", "OKH", "22k", rot=0)
    R(d, "R227", 20.5, 13, "OKH", "GND", "10k", rot=90)
    R(d, "R232", 21.5, 12, "OKH", "BIAS_OK_PRE", "1k", rot=90)
    d.part("LM2901", "U202", 22, 7, {3: "+15V", 12: "GND"}, value="LM2901B", unit=5)
    C(d, "C209", 23, 7, "+15V", "GND", "100n")
    d.text("MON_FAULT (diode-OR, 13 V = fault) clamps every channel (sheet 03). BIAS_OK_PRE = no fault, pulled up from "
           "+15 V (22k / 10k: 4.5-4.9 V; +15 V missing = not OK) -> Schmitt buffer (sheet 04) -> BIAS_OK_A. "
           "Independent of BIAS_EN (interfaces.md 6.3, 8).", 14, 14.4)
    # watchdog
    R(d, "R228", 17, 1, "BIAS_EN_A", "GND", "100k", rot=90)
    R(d, "R229", 17.8, 1, "BIAS_EN_A", "WPS", "1k", rot=90)
    C(d, "C210", 18.6, 1, "WPS", "WP", "100n", rot=90)
    d.part("BAT54S", "D210", 19.5, 2, {1: "GND", 3: "WP", 2: "WST"}, value="BAT54S (pump)")
    C(d, "C212", 20.5, 3, "WST", "GND", "1u")
    R(d, "R230", 21.3, 3, "WST", "GND", "56k", rot=0)
    NMOS(d, "Q203", 22.3, 2, "WST", "CLAMP_WD")
    R(d, "R231", 23.3, 1, "+15V", "CLAMP_WD", "100k", rot=90)
    d.text("Watchdog: only a toggling BIAS_EN (5-15 kHz, 5 V) charges WST and turns Q203 on, releasing the clamps "
           "(CLAMP_WD low). Stopped high or low, card missing: cold in 76-131 ms. R229 1k limits the card's 74AHCT to "
           "3.8 mA peak (control board request >= 470 ohm); R230 56k (was 100k) for the 5 V drive.", 16, 4.4)


# ------------------------------------------------------------------ sheet 03
DACOUT = {1: 4, 2: 13, 3: 5, 4: 12}   # channel -> DAC7578 pin (VOUTA, VOUTB, VOUTC, VOUTD)
OPA = {1: (1, 3, 2, 1), 2: (2, 5, 6, 7), 3: (3, 10, 9, 8), 4: (4, 12, 13, 14)}   # unit, +, -, out


def sheet03(d):
    d.text("03 Bias DAC (I2C, power-on reset to zero) and four cold-by-default bias channels: Vg1 = VNC + Ic x 30k, "
           "Ic = Vdac / 1k. DAC 0 V = -71 V (cold), 2.5 V = -0.3 V (typical board). docs/bias_supply.md, sim/bias_supply.", 0, -1.4, 2)
    d.part("DAC7578xPW", "U301", 1, 3, {1: "GND", 2: "GND", 3: "+5V", 4: "DAC1", 13: "DAC2", 5: "DAC3", 12: "DAC4",
                                        6: "NC", 7: "NC", 10: "NC", 11: "NC", 8: "VREF2V5", 9: "DAC_CLR_N",
                                        14: "GND", 15: "I2C_SDA_A", 16: "I2C_SCL_A"},
           value="DAC7578SPW (12-bit x8, I2C 0x48)")
    C(d, "C301", 0, 1, "+5V", "GND", "100n")
    d.part("ADR4525", "U302", 1, 7, {2: "+5V", 4: "GND", 6: "VREF2V5", 1: "NC", 3: "NC", 5: "NC", 7: "NC", 8: "NC"},
           value="ADR4525 (2.5 V, low noise)")
    C(d, "C302", 0, 8, "+5V", "GND", "1u")
    C(d, "C303", 3, 8, "VREF2V5", "GND", "1u")
    R(d, "R301", 3, 1, "+5V", "DAC_CLR_N", "10k", rot=90)
    NMOS(d, "Q301", 3, 3, "CLAMP_WD", "DAC_CLR_N")
    d.text("DAC: ADDR0 = GND -> 0x48. ~CLR low while the watchdog clamps (CLAMP_WD high): the DAC returns to zero "
           "whenever BIAS_EN stops, so a restarted firmware must rewrite it. ~LDAC = GND. Outputs E-H unused. "
           "VREF2V5 also feeds the ADC (sheet 04).", 0, 9.6)
    d.part("OPA4197xD", "U303", 5, 9.5, {4: "+15V", 11: "-15V"}, value="OPA4197ID", unit=5)
    C(d, "C304", 6, 9, "+15V", "GND", "100n")
    C(d, "C305", 6.8, 9, "-15V", "GND", "100n")
    for n in range(1, 5):
        c0 = 5 + (n - 1) * 5.4
        r0 = 0.6
        d.text(f"Channel {n} (V{n})", c0, r0 - 0.2)
        R(d, f"R3{n}0", c0, r0 + 0.6, f"DAC{n}", f"FLT{n}", "10k", rot=90)
        C(d, f"C3{n}0", c0, r0 + 1.8, f"FLT{n}", "GND", "330n")
        R(d, f"R3{n}1", c0 + 0.8, r0 + 1.8, f"FLT{n}", "GND", "1M", rot=0)
        NMOS(d, f"Q3{n}0", c0, r0 + 3.2, "CLAMP_WD", f"FLT{n}")
        NMOS(d, f"Q3{n}1", c0 + 1.2, r0 + 3.2, "MON_FAULT", f"FLT{n}")
        u, ip, im, o = OPA[n]
        d.part("OPA4197xD", "U303", c0 + 2, r0 + 1.2, {ip: f"FLT{n}", im: f"E{n}", o: f"U{n}"}, value="OPA4197ID", unit=u)
        R(d, f"R3{n}2", c0 + 3.2, r0 + 0.6, f"U{n}", f"BQ{n}", "1k", rot=90)
        NPN(d, f"Q3{n}2", c0 + 3.2, r0 + 2, f"BQ{n}", f"C{n}", f"E{n}", "MMBT3904")
        R(d, f"R3{n}3", c0 + 3.2, r0 + 3.6, f"E{n}", "GND", "1k", rot=0)
        PNP(d, f"Q3{n}3", c0 + 1, r0 + 5, f"C{n}", f"C{n}", f"M2_{n}", "MMBTA92")
        R(d, f"R3{n}4", c0 + 1, r0 + 6.4, "+15V", f"M2_{n}", "1k", rot=0)
        PNP(d, f"Q3{n}4", c0 + 3, r0 + 5, f"C{n}", f"OUT{n}", f"M3_{n}", "MMBTA92")
        R(d, f"R3{n}5", c0 + 3, r0 + 6.4, "+15V", f"M3_{n}", "1k", rot=0)
        R(d, f"R3{n}6", c0 + 0.6, r0 + 8, f"OUT{n}", "VNC", "30k", rot=0)
        C(d, f"C3{n}1", c0 + 0.6, r0 + 9, f"OUT{n}", "VNC", "100n/100V", rot=90)
        NPN(d, f"Q3{n}5", c0 + 2.6, r0 + 8.4, f"OUT{n}", f"Q4C{n}", f"FE{n}", "MMBTA42")
        R(d, f"R3{n}7", c0 + 3.8, r0 + 7.8, "GND", f"Q4C{n}", "100R", rot=0)
        R(d, f"R3{n}8", c0 + 1.6, r0 + 10.2, f"FE{n}", f"PM{n}", "22k", rot=0)
        R(d, f"R3{n}9", c0 + 1.6, r0 + 11.2, f"PM{n}", "M80", "22k", rot=0)
        C(d, f"C3{n}2", c0 + 2.8, r0 + 11.2, f"PM{n}", "GND", "1u/100V")
        R(d, f"R3{n}A", c0 + 3.6, r0 + 10.2, f"FE{n}", f"BIAS{n}", "1k", rot=0)
        C(d, f"C3{n}3", c0 + 4.4, r0 + 11.2, f"BIAS{n}", "GND", "1u/100V")
    d.text("Per channel: DAC -> 10k / 330n (48 Hz), 1M pull-down (DAC high-Z = cold), two clamps (watchdog, VNC "
           "monitors: MON_FAULT); op amp + NPN: Ic = Vdac / 1k; PNP mirror at +15 V (300 V parts) sources Ic into OUT; "
           "30k || 100n to VNC; 300 V NPN follower, 2x 22k (midpoint filtered) to -80 V, 1k / 1u to BIASn.", 5, 13.4)


# ------------------------------------------------------------------ sheet 04
SENSE = {1: (1, 3, 2, 1), 2: (2, 5, 6, 7), 3: (3, 10, 9, 8), 4: (4, 12, 13, 14)}
CMP = {1: (1, 5, 4, 2), 2: (2, 7, 6, 1), 3: (3, 11, 10, 13), 4: (4, 9, 8, 14)}   # unit, +, -, out


def sheet04(d):
    d.text("04 Cathode-current sense (10 V/A, 0-2.5 V = 0-250 mA), 8-channel I2C ADC, per-tube over-current "
           "comparators (2.2 V = 220 mA) and the over-current latch. docs/bias_supply.md, sim/bias_supply.", 0, -1.4, 2)
    d.part("OPA4197xD", "U401", 1, 9.5, {4: "+15V", 11: "-15V"}, value="OPA4197ID", unit=5)
    C(d, "C401", 2, 9, "+15V", "GND", "100n")
    C(d, "C402", 2.8, 9, "-15V", "GND", "100n")
    for n in range(1, 5):
        r0 = 0.4 + (n - 1) * 2.1
        d.text(f"Tube {n}", 0, r0 - 0.1)
        R(d, f"R4{n}0", 0.5, r0 + 0.6, f"K{n}", f"A1_{n}", "10k", rot=90)
        C(d, f"C4{n}0", 1.5, r0 + 1.2, f"A1_{n}", f"KELV{n}", "10n")
        R(d, f"R4{n}1", 2.5, r0 + 0.6, f"A1_{n}", f"A2_{n}", "47k", rot=90)
        R(d, f"R4{n}2", 3.7, r0 + 0.6, f"A2_{n}", f"A3_{n}", "47k", rot=90)
        C(d, f"C4{n}3", 3.1, r0 + 1.2, f"A2_{n}", f"KELV{n}", "220n")
        C(d, f"C4{n}1", 4.6, r0 + 1.2, f"A3_{n}", f"KELV{n}", "220n")
        u, ip, im, o = SENSE[n]
        d.part("OPA4197xD", "U401", 6, r0 + 0.8, {ip: f"A3_{n}", im: f"FB{n}", o: f"Y{n}"}, value="OPA4197ID", unit=u)
        R(d, f"R4{n}3", 7.4, r0 + 0.2, f"Y{n}", f"FB{n}", "9.09k 0.1%", rot=90)
        R(d, f"R4{n}4", 7.4, r0 + 1.4, f"FB{n}", f"KELV{n}", "1.01k 0.1%", rot=90)
        R(d, f"R4{n}5", 8.8, r0 + 0.6, f"Y{n}", f"ISNS{n}", "1k", rot=90)
        C(d, f"C4{n}2", 9.8, r0 + 1.2, f"ISNS{n}", "GND", "100n")
        d.part("BAT54S", f"D4{n}0", 10.8, r0 + 1.0, {1: "GND", 2: "+5V", 3: f"ISNS{n}"}, value="BAV199 (ADC clamp, low leakage)")
        u, ip, im, o = CMP[n]
        d.part("LM2901", "U403", 13, r0 + 0.8, {ip: "VOC", im: f"ISNS{n}", o: "OC_ANY_N"}, value="LM2901B", unit=u)
    d.text("Filter (decided 2026-11-22, PA-4): 10k / 10n, then two real poles 47k / 220n twice (5.3 and 40 Hz, -3 dB "
           "5.0 Hz), gain 10.0 (9.09k / 1.01k 0.1 %): 10 V/A. Trip 25 ms after a step to 400 mA, 45-50 ms after a mirror short; "
           "13 mA pp ripple at 82 Hz full overdrive (bias_supply.md). 1R shunt 1 %, 50 ppm/K.", 0, 9.1 + 1.8)
    d.part("LM2901", "U403", 13, 9.5, {3: "+15V", 12: "GND"}, value="LM2901B", unit=5)
    C(d, "C403", 14, 9.5, "+15V", "GND", "100n")
    R(d, "R401", 15, 7.5, "VREF10", "VOC", "39k 0.1%", rot=90)
    R(d, "R402", 16, 8.5, "VOC", "GND", "11k 0.1%", rot=0)
    C(d, "C404", 17, 8.5, "VOC", "GND", "100n")
    d.text("VOC = 10 V x 11 / 50 = 2.20 V = 220 mA average (SAFE-2), +-2.4 % worst case (README)", 15, 9.6)
    # over-current latch
    R(d, "R403", 16, 1, "+5V", "OC_ANY_N", "100k", rot=90)
    C(d, "C405", 17, 2, "OC_ANY_N", "GND", "1u")
    d.part("74LVC2G17", "U405", 17.5, 3.4, {1: "OC_ANY_N", 6: "OC_ANY_S"}, value="74LVC2G17 (Schmitt)", unit=1)
    d.part("74LVC2G17", "U405", 17.5, 4.6, {3: "BIAS_OK_PRE", 4: "BIAS_OK_A"}, value="74LVC2G17 (Schmitt)", unit=2)
    d.part("74LVC2G17", "U405", 16.5, 5.6, {5: "+5V", 2: "GND"}, value="74LVC2G17 (Schmitt)", unit=3)
    C(d, "C411", 17.5, 5.4, "+5V", "GND", "100n")
    d.part("74HC74", "U404", 19, 2, {1: "OC_ANY_S", 2: "OC_ANY_S", 3: "OC_CLR_A", 4: "+5V", 5: "OC_OK", 6: "NC"},
           value="74HC74", unit=1)
    d.part("74HC74", "U404", 19, 5, {13: "+5V", 12: "GND", 11: "GND", 10: "+5V", 9: "NC", 8: "NC"}, value="74HC74", unit=2)
    d.part("74HC74", "U404", 22, 2, {14: "+5V", 7: "GND"}, value="74HC74", unit=3)
    C(d, "C406", 23, 2, "+5V", "GND", "100n")
    R(d, "R404", 21, 4.5, "OC_CLR_A", "GND", "100k", rot=0)
    d.text("Schmitt buffer U405: the slow RC edge of OC_ANY_N and the comparator-driven BIAS_OK_PRE into CMOS inputs. "
           "Latch: any comparator low -> ~R low -> OC_OK = 0 (tripped). Power-on: 100k / 1u holds ~R low about "
           "70 ms -> starts tripped. OC_CLR rising edge clocks D = OC_ANY_N: clears only if no comparator is "
           "tripped. OC_OK -> HV_PERMIT (both switches) and OC_TRIP_N (sheet 05).", 15, 6.4)
    # ADC
    d.part("ADS7828", "U402", 19, 10, {1: "ISNS1", 2: "ISNS2", 3: "ISNS3", 4: "ISNS4", 5: "VNC_ADC", 6: "M80_ADC",
                                       7: "P15_ADC", 8: "GND", 9: "GND", 10: "VREF2V5", 11: "GND", 12: "+5V",
                                       13: "+5V", 14: "I2C_SCL_A", 15: "I2C_SDA_A", 16: "+5V"},
           value="ADS7828E (12-bit x8, I2C 0x4B)")
    C(d, "C407", 22, 9, "+5V", "GND", "100n")
    R(d, "R405", 15, 12, "VNC", "VNC_ADC", "909k", rot=90)
    R(d, "R406", 15, 13.2, "VNC_ADC", "VREF10", "100k", rot=90)
    C(d, "C408", 16, 13, "VNC_ADC", "GND", "100n")
    R(d, "R407", 17, 12, "M80", "M80_ADC", "909k", rot=90)
    R(d, "R408", 17, 13.2, "M80_ADC", "VREF10", "100k", rot=90)
    C(d, "C409", 18, 13, "M80_ADC", "GND", "100n")
    R(d, "R409", 23, 12, "+15V", "P15_ADC", "100k", rot=90)
    R(d, "R410", 23, 13.2, "P15_ADC", "GND", "18k", rot=90)
    C(d, "C410", 24, 13, "P15_ADC", "GND", "100n")
    d.text("ADC (A0 = A1 = 1 -> 0x4B), reference VREF2V5 (shared with the DAC): CH0-3 tube currents, CH4 VNC "
           "(V = (CH4 - 9.09) / 0.0909), CH5 -80 V (same scaling), CH6 +15 V (x 118 / 18), CH7 spare (GND).", 15, 14.4)


# ------------------------------------------------------------------ sheet 05
def sheet05(d):
    d.text("05 Control and safety: template ribbon (W14-b) and bias ribbon (W15-b) on the DGND island, soft tie, "
           "MCP23S17 (map interfaces.md 7.3), 100 ohm crossings, heater warm-up timer, HV_PERMIT logic and current "
           "loop (W16-a). interfaces.md 6.1, 6.3, 8; grounding.md 4.", 0, -1.4, 2)
    d.part("Conn_02x07_Odd_Even", "J501", 0, 2, {1: "+5V", 2: "GNDD", 3: "+15V", 4: "GNDD", 5: "-15V", 6: "GNDD",
                                                  7: "SPI_SCK", 8: "GNDD", 9: "SPI_MOSI", 10: "SPI_MISO",
                                                  11: "SPI_CS_N", 12: "MUTE_ALL_N", 13: "RESET_N", 14: "GNDD"},
           value="W14-b CONTROL (template 2x7)")
    for i, n in enumerate(("+5V", "+15V", "-15V", "GNDD")):
        d.flag(n, 2, 4 + i * 0.6)
    R(d, "R501", 3, 1, "RESET_N", "+5V", "10k", rot=90)
    R(d, "R502", 3, 3, "MUTE_ALL_N", "GNDD", "100k", rot=90)
    d.text("MUTE_ALL_N: terminated, unused (6.3)", 2.6, 3.9)
    # soft tie and bulk decoupling
    R(d, "R503", 0, 7, "GNDD", "GND", "10R", rot=90)
    C(d, "C501", 1, 7, "GNDD", "GND", "100n", rot=90)
    d.text("Soft tie GNDD - GND (AGND star), the only DGND-AGND join", 0, 7.8)
    CP(d, "C502", 3, 7, "+15V", "GND", "10u/25V")
    CP(d, "C503", 4, 7, "GND", "-15V", "10u/25V")
    CP(d, "C504", 5, 7, "+5V", "GND", "10u/10V")
    d.text("Bulk decoupling on AGND (the loads are on AGND; their return goes through GND_PWR)", 3, 8.3)
    # expander
    d.part("MCP23S17x-x-SS", "U501", 7, 3, {9: "+5V", 10: "GNDD", 11: "SPI_CS_N", 12: "SPI_SCK", 13: "SPI_MOSI",
                                            14: "SPI_MISO", 15: "GNDD", 16: "GNDD", 17: "GNDD", 18: "RESET_N",
                                            19: "NC", 20: "NC", 21: "EX_OC_CLR", 22: "EX_HV_REQ", 23: "NC", 24: "NC",
                                            25: "NC", 26: "NC", 27: "NC", 28: "NC", 1: "NC", 2: "NC", 3: "NC",
                                            4: "NC", 5: "NC", 6: "NC", 7: "NC", 8: "NC"},
           value="MCP23S17-E/SS (addr 000)")
    C(d, "C505", 7, 0, "+5V", "GNDD", "100n")
    R(d, "R504", 10, 2, "EX_OC_CLR", "GNDD", "100k", rot=0)
    R(d, "R505", 10, 3, "EX_HV_REQ", "GNDD", "100k", rot=0)
    R(d, "R506", 11.5, 2, "EX_OC_CLR", "OC_CLR_A", "100R", rot=90)
    R(d, "R507", 11.5, 3, "EX_HV_REQ", "HV_REQ_A", "100R", rot=90)
    R(d, "R508", 12.5, 4, "HV_REQ_A", "GND", "100k", rot=0)
    d.text("GPA0 OC_CLR, GPA1 HV_PERMIT_REQ (7.3); GPA2-5 reserved MODE_* (D7, NC). Required, not optional: "
           "they are the only source of OC_CLR and HV_PERMIT_REQ.", 7, 6.7)
    # bias ribbon
    d.part("Conn_02x05_Odd_Even", "J502", 0, 10, {1: "GNDD", 2: "I2C_SCL", 3: "GNDD", 4: "I2C_SDA", 5: "GNDD",
                                                   6: "BIAS_EN", 7: "BIAS_OK", 8: "OC_TRIP_N", 9: "HV_PERMIT_MON",
                                                   10: "GNDD"}, value="W15-b BIAS (2x5)")
    R(d, "R509", 3, 9, "+5V", "I2C_SCL", "4.7k", rot=90)
    R(d, "R510", 4, 9, "+5V", "I2C_SDA", "4.7k", rot=90)
    R(d, "R511", 5, 10, "I2C_SCL", "I2C_SCL_A", "100R", rot=90)
    R(d, "R512", 5, 11, "I2C_SDA", "I2C_SDA_A", "100R", rot=90)
    R(d, "R513", 5, 12, "BIAS_EN", "BIAS_EN_A", "100R", rot=90)
    R(d, "R514", 5, 13, "BIAS_OK_A", "BIAS_OK", "100R", rot=90)
    R(d, "R515", 5, 14, "OC_OK", "OC_TRIP_N", "100R", rot=90)
    R(d, "R516", 5, 15, "HV_MON_A", "HV_PERMIT_MON", "100R", rot=90)
    d.text("DGND side | AGND side (100 ohm crossings, grounding.md 4). I2C 5 V, 100 kHz, 4.7k pull-ups here. "
           "Card-side pull-downs on BIAS_OK / OC_TRIP_N (missing = not OK / tripped).", 3, 16.2)
    # heater warm-up timer
    d.text("Warm-up timer (WARM_OK about 30 s after the heater voltage appears). Isolated sense: the heaters float "
           "and may sit at +90 V (elevated reference option); AC or DC heater (PRE-4 open).", 14, 0.2)
    R(d, "R517", 14, 1, "HTR1", "HS_AC1", "330R 0.5W", rot=90)
    d.part("D_Bridge_+AA-", "D501", 15.5, 2, {2: "HS_AC1", 3: "HTR2", 1: "HS_P", 4: "HS_N"}, value="MB1S")
    d.part("D_Zener", "D502", 17, 1, {1: "HS_P", 2: "HS_Z"}, value="BZX84C2V4", rot=90)
    d.part("PC817", "U502", 18.5, 2, {1: "HS_Z", 2: "HS_N", 4: "HEAT_ABS", 3: "GND"}, value="PC817 (heater present)")
    R(d, "R518", 20, 1, "+5V", "HEAT_ABS", "10k", rot=90)
    C(d, "C506", 20.8, 2, "HEAT_ABS", "GND", "100n")
    C(d, "C507", 14, 4, "+5V", "POR_W", "1u")
    R(d, "R519", 15, 4.5, "POR_W", "GND", "100k", rot=0)
    d.part("D_Schottky", "D503", 17, 4, {2: "HEAT_ABS", 1: "WARM_CLR"}, value="BAT54", rot=0)
    d.part("D_Schottky", "D504", 17, 5, {2: "POR_W", 1: "WARM_CLR"}, value="BAT54", rot=0)
    R(d, "R520", 18.5, 5, "WARM_CLR", "GND", "100k", rot=90)
    d.part("74HC4060", "U503", 21, 5, {12: "WARM_CLR", 11: "OSC_RS", 10: "OSC_RT", 9: "OSC_CT", 3: "WARM_OK",
                                       16: "+5V", 8: "GND", 1: "NC", 2: "NC", 4: "NC", 5: "NC", 6: "NC", 7: "NC",
                                       13: "NC", 14: "NC", 15: "NC"}, value="74HC4060")
    R(d, "R521", 24, 4, "OSC_RS", "OSC_X", "220k", rot=90)
    R(d, "R522", 24, 5, "OSC_RT", "OSC_X", "100k", rot=90)
    C(d, "C508", 24, 6, "OSC_CT", "OSC_X", "15n", rot=90)
    d.part("D", "D505", 24, 7.2, {2: "WARM_OK", 1: "OSC_RS"}, value="1N4148W (stop at Q14)", rot=90)
    C(d, "C509", 22.5, 3, "+5V", "GND", "100n")
    d.text("f = 1 / (2.5 x 100k x 15n) = 267 Hz; Q14 high after 8192 counts = 31 s, then D505 stops the oscillator "
           "(WARM_OK latched until the heater goes or +5 V restarts). Cleared while the heater is absent and by the "
           "power-on pulse (C507 / R519).", 14, 8.2)
    # HV_PERMIT logic
    d.part("74LVC1G11", "U504", 8, 10, {1: "BIAS_OK_A", 3: "OC_OK", 6: "WARM_OK", 4: "PERMIT3", 5: "+5V", 2: "GND"},
           value="74LVC1G11")
    d.part("74LVC1G08", "U505", 10.5, 10, {1: "PERMIT3", 2: "HV_REQ_A", 4: "PERMIT_DRV", 5: "+5V", 3: "GND"},
           value="74LVC1G08")
    C(d, "C510", 8, 12, "+5V", "GND", "100n")
    C(d, "C511", 9, 12, "+5V", "GND", "100n")
    R(d, "R523", 12, 10, "PERMIT_DRV", "HS_NB", "4.7k", rot=90)
    R(d, "R524", 12.6, 11.2, "HS_NB", "GND", "10k", rot=0)
    NPN(d, "Q501", 14, 10.5, "HS_NB", "HS_NC", "GND", "MMBT3904")
    R(d, "R525", 15, 9.5, "HS_NC", "HS_PB", "4.7k", rot=0)
    R(d, "R526", 15.8, 8.8, "+15V", "HS_PB", "10k", rot=90)
    PNP(d, "Q502", 17, 9.8, "HS_PB", "LOOP_HI", "+15V", "MMBT3906")
    R(d, "R527", 18.5, 10, "LOOP_HI", "LOOP_R", "1.3k 0.25W", rot=90)
    d.part("PC817", "U506", 20, 11, {1: "LOOP_R", 2: "HVP_P", 4: "+5V", 3: "HV_MON_A"}, value="PC817 (loop monitor)")
    R(d, "R528", 21.5, 12, "HV_MON_A", "GND", "10k", rot=0)
    d.part("Conn_01x02", "J503", 23, 11, {1: "HVP_P", 2: "HVP_N"}, value="W16-a HV_PERMIT+ / HV_PERMIT- (Lock-2.54)")
    d.part("D", "D506", 22, 13.4, {1: "HVP_P", 2: "HVP_N"}, value="1N4148W (reverse)", rot=90)
    NPN(d, "Q503", 18, 13.8, "LS_B", "HVP_N", "GND", "MMBT3904")
    R(d, "R529", 16.5, 13.8, "OC_OK", "LS_B", "4.7k", rot=90)
    R(d, "R530", 17, 15, "LS_B", "GND", "10k", rot=0)
    d.text("HV_PERMIT = BIAS_OK AND OC_OK AND WARM_OK AND HV_PERMIT_REQ (high-side switch Q502), and OC_OK alone on "
           "the low-side switch Q503: one shorted transistor can't give a permit. Loop: +15 V - Q502 - 1.3k - "
           "monitor LED - W16 - the HV supplies' opto LED - W16 - Q503 - GND: 9.4 mA. No current = HV off.", 8, 17.0)


# ------------------------------------------------------------------ footprints and BOM
LOC = "tube_power_amp_revb:"
R0805, R1206 = "Resistor_SMD:R_0805_2012Metric", "Resistor_SMD:R_1206_3216Metric"
AX0207 = "Resistor_THT:R_Axial_DIN0207_L6.3mm_D2.5mm_P10.16mm_Horizontal"
SOT23 = "Package_TO_SOT_SMD:SOT-23"
SYMFP = {   # symbol -> (footprint, candidate part, note)
    "EL34": (LOC + "Valve_Octal_Belton_PCD17.20mm", "Belton octal PCB socket (as rev A)", "solder side, as built"),
    "2N7002": (SOT23, "2N7002,215 (Nexperia)", ""),
    "BAT54S": (SOT23, "BAT54S,215 (Nexperia)", ""),
    "Q_PMOS": ("Package_TO_SOT_SMD:SOT-223-3_TabPin2", "BSP92P H6327 (Infineon)", "250 V"),
    "NetTie_2": ("NetTie:NetTie-2_SMD_Pad0.5mm", "", "Kelvin tap at the shunt pad"),
    "DAC7578xPW": ("Package_SO:TSSOP-16_4.4x5mm_P0.65mm", "DAC7578SPW (TI)", "power-on reset to zero: confirm in the datasheet"),
    "ADR4525": ("Package_SO:SOIC-8_3.9x4.9mm_P1.27mm", "ADR4525BRZ (ADI)", ""),
    "ADS7828": ("Package_SO:TSSOP-16_4.4x5mm_P0.65mm", "ADS7828E (TI)", "-40 to 85 C: keep it at the cool end"),
    "OPA4197xD": ("Package_SO:SOIC-14_3.9x8.7mm_P1.27mm", "OPA4197IDR (TI)", ""),
    "LM2901": ("Package_SO:SOIC-14_3.9x8.7mm_P1.27mm", "LM2901BIDR (TI, -40 to 125 C)", "orderable suffix to confirm"),
    "LM4040DBZ-10": (SOT23, "LM4040A10IDBZR (TI)", "10 V only in I grade (-40 to 85 C)"),
    "74HC74": ("Package_SO:SOIC-14_3.9x8.7mm_P1.27mm", "74HC74D (Nexperia)", ""),
    "74HC4060": ("Package_SO:SOIC-16_3.9x9.9mm_P1.27mm", "74HC4060D (Nexperia)", ""),
    "74LVC1G11": ("Package_TO_SOT_SMD:SOT-363_SC-70-6", "74LVC1G11GW (Nexperia)", ""),
    "74LVC1G08": ("Package_TO_SOT_SMD:SOT-353_SC-70-5", "74LVC1G08GW (Nexperia)", ""),
    "74LVC2G17": ("Package_TO_SOT_SMD:SOT-363_SC-70-6", "74LVC2G17GW (Nexperia)", ""),
    "PC817": ("Package_DIP:DIP-4_W7.62mm", "PC817X1NSZ1B (Sharp)", "THT for the heater-side isolation"),
    "MCP23S17x-x-SS": ("Package_SO:SSOP-28_5.3x10.2mm_P0.65mm", "MCP23S17-E/SS (Microchip)", ""),
    "D_Bridge_+AA-": ("Package_TO_SOT_SMD:TO-269AA", "MB1S (onsemi)", ""),
    "Conn_02x07_Odd_Even": ("Connector_IDC:IDC-Header_2x07_P2.54mm_Vertical", "61201421621 (Wurth)", "shrouded, keyed"),
    "Conn_02x05_Odd_Even": ("Connector_IDC:IDC-Header_2x05_P2.54mm_Vertical", "61201021621 (Wurth)", "shrouded, keyed"),
}
CONN = {"J101": (LOC + "BladeTab_x2_P5.00mm_Drill1.4mm_PLACEHOLDER", "4.8 mm PCB blade tabs", "PLACEHOLDER footprint"),
        "J102": (LOC + "BladeTab_x1_P5.00mm_Drill1.4mm_PLACEHOLDER", "4.8 mm PCB blade tab", "PLACEHOLDER footprint"),
        "J103": (LOC + "BladeTab_x2_P5.00mm_Drill1.4mm_PLACEHOLDER", "6.3 mm PCB blade tabs", "PLACEHOLDER footprint; 6.4 A"),
        "J104": (LOC + "BladeTab_x3_P5.00mm_Drill1.4mm_PLACEHOLDER", "4.8 mm PCB blade tabs", "PLACEHOLDER footprint; anode nets"),
        "J105": ("Connector_Molex:Molex_Mini-Fit_Jr_5566-06A_2x03_P4.20mm_Vertical", "Molex 39-28-1063 class (Mini-Fit Jr 5566-06A; order code to confirm)",
                 "600 V AC/DC; housing 39-01-2060, terminals 39-00-0039; circuit 6 N/C"),
        "J201": (LOC + "BladeTab_x2_P5.00mm_Drill1.4mm_PLACEHOLDER", "4.8 mm PCB blade tabs", "PLACEHOLDER footprint"),
        "J503": ("Connector_Molex:Molex_KK-254_AE-6410-02A_1x02_P2.54mm_Vertical", "22-27-2021 (Molex KK-254)", "")}


def footprint_for(ref, sym, v):
    v = v or ""
    if sym.startswith("Conn"):
        return CONN.get(ref) or SYMFP[sym]
    if sym in SYMFP:
        return SYMFP[sym]
    if sym == "R":
        if "5W" in v:
            return LOC + "R_Axial_Power_L25.0mm_W6.4mm_P30.00mm", "1k 5 W flameproof metal oxide (as rev A)", ""
        if "fusible" in v:
            return ("Resistor_THT:R_Axial_DIN0309_L9.0mm_D3.2mm_P12.70mm_Horizontal", "CRF251-4 / CRF110 10R (Yageo Vitrohm)",
                    "fusible wirewound; inrush of C201 (8 A peak, 0.32 J) to confirm")
        if v.startswith("1R"):
            return "Resistor_SMD:R_2512_6332Metric", "1R 1 W 1 % 50 ppm/K metal strip (2512)", ""
        if ref[2:3] == "1" and ref[1] == "1" and len(ref) == 4 and ref[3] in "01" and ref[2] in "1234":
            pass
        if v in ("91k", "5.6k"):
            return AX0207, "metal film 0.6 W 350 V", "grid circuit"
        if "0.1%" in v:
            return R1206, f"{v.split()[0]} 0.1 % 25 ppm/K thin film 1206", ""
        if v.endswith("M") or v in ("3.3k 1206", "1.3k 0.25W", "330R 0.5W", "1.0k"):
            return R1206, f"{v.split()[0]} 1 % 1206", ""
        return R0805, f"{v.split()[0]} 1 % 0805", ""
    if sym in ("C", "C_Polarized"):
        if "630V" in v and "MKP" in v:
            return ("Capacitor_THT:C_Rect_L26.5mm_W10.5mm_P22.50mm_MKS4", "220n 630 V MKP, P 22.5 mm (WIMA MKP4 / Kemet R76 class)",
                    "")
        if "630V" in v:
            return "Capacitor_SMD:C_1812_4532Metric", "100n 630 V X7R 1812", ""
        if "100u/100V" in v:
            return "Capacitor_THT:CP_Radial_D10.0mm_P5.00mm", "UPW2A101MPD (Nichicon, 105 C)", ""
        if v == "10u/100V 105C":
            return "Capacitor_THT:CP_Radial_D6.3mm_P2.50mm", "UPW2A100MED (Nichicon, 105 C)", ""
        if "X7S 1210" in v:
            return "Capacitor_SMD:C_1210_3225Metric", "GRM32EC72A106KE05 (Murata)", "about 30 % left at 72 V"
        if "/100V" in v:
            return "Capacitor_SMD:C_1210_3225Metric", f"{v.split('/')[0]} 100 V X7R 1210", ""
        if v.startswith("10u"):
            return "Capacitor_SMD:C_1206_3216Metric", f"{v} X7R 1206", ""
        if v.startswith(("220n", "330n")):
            return "Capacitor_SMD:C_0805_2012Metric", f"{v} 50 V X7R 0805 (C0G 1206 preferred)", ""
        return "Capacitor_SMD:C_0805_2012Metric", f"{v} 50 V X7R 0805", ""
    if sym in ("D", "D_Schottky", "D_Zener", "D_TVS"):
        table = {"UF4007": ("Diode_THT:D_DO-41_SOD81_P10.16mm_Horizontal", "UF4007"),
                 "RGP02-20E": ("Diode_THT:D_DO-41_SOD81_P12.70mm_Horizontal", "RGP02-20E-E3/54 (Vishay, 2 kV, 0.5 A, 300 ns)"),
                 "P6KE350CA": ("Diode_THT:D_DO-15_P12.70mm_Horizontal", "P6KE350CA (Littelfuse; VBR 332-368 V, VC 482 V at 1.24 A)"),
                 "S3M": ("Diode_SMD:D_SMC", "S3M-E3/57T (Vishay)"), "S1G": ("Diode_SMD:D_SMA", "S1G (1N4004 class)"),
                 "1N4148W": ("Diode_SMD:D_SOD-123", "1N4148W-7-F (Diodes Inc)"), "BAS416": ("Diode_SMD:D_SOD-323", "BAS416,115 (Nexperia)"),
                 "BZT52H": ("Diode_SMD:D_SOD-123F", "BZT52H-B36,115 (Nexperia)"), "BAT54": ("Diode_SMD:D_SOD-323", "BAT54J (Nexperia)"),
                 "BZX84C2V4": (SOT23, "BZX84-C2V4,215 (Nexperia)")}
        for k, (fp, mpn) in table.items():
            if v.startswith(k):
                return fp, mpn, ("1 cm2 cathode copper (150 K/W)" if k == "BZT52H" else "")
    if sym in ("Q_NPN", "Q_PNP"):
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
        f.write("# generated by tools/sheets/draw_all.py (second pass); PLACEHOLDER in the name = not final\n")
        w = csv.writer(f)
        w.writerow(["refdes", "footprint", "value"])
        for r in rows:
            w.writerow([r[0], r[3], r[2]])
    groups = {}
    for ref, sym, v, fp, mpn, note in rows:
        groups.setdefault((v, fp, mpn, note), []).append(ref)
    os.makedirs(os.path.join(RB, "bom"), exist_ok=True)
    with open(os.path.join(RB, "bom", "tube_power_amp_revb_bom.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["refs", "qty", "value", "footprint", "candidate part", "note"])
        for (v, fp, mpn, note), refs in sorted(groups.items(), key=lambda kv: kv[1][0]):
            w.writerow([" ".join(refs), len(refs), v, fp, mpn, note])
    return len(rows), len(groups)


SHEETS = [("01_output_stage.kicad_sch", sheet01), ("02_bias_reference.kicad_sch", sheet02),
          ("03_bias_channels.kicad_sch", sheet03), ("04_current_sense.kicad_sch", sheet04),
          ("05_control_safety.kicad_sch", sheet05)]


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
