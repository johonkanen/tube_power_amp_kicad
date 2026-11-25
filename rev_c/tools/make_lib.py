#!/usr/bin/env python3
"""Build lib/tube_power_amp_revc.kicad_sym from KiCad's standard symbol libraries: the symbols the
rev C sheets use, flattened (KiCad's derived 'extends' symbols resolved, since a schematic's
lib_symbols needs them whole). The one change to a stock symbol: the EL34's pins 1, 3 and 8 are
passive (PASSIVE below)."""
import copy
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "..", "tools", "p2k"))
from p2k.sexpr import Sym, find, find_all, load, parse, save  # noqa: E402

KICAD = os.environ.get("KICAD_SYMBOLS", "/mnt/c/Program Files/KiCad/10.0/share/kicad/symbols")
WANT = [
    ("Device", "R"), ("Device", "C"), ("Device", "C_Polarized"), ("Device", "D"), ("Device", "D_TVS"),
    ("Device", "NetTie_2"), ("Valve", "EL34"),
    ("Analog_DAC", "DAC7578xPW"), ("Reference_Voltage", "ADR4525"), ("Analog_ADC", "ADS1115IDGS"),
    ("Connector_Generic", "Conn_02x07_Odd_Even"), ("Connector_Generic", "Conn_02x05_Odd_Even"),
    ("Connector_Generic", "Conn_01x01"), ("Connector_Generic", "Conn_01x02"), ("Connector_Generic", "Conn_01x03"),
    ("Connector", "TestPoint"), ("Connector_Generic", "Conn_02x03_Top_Bottom"),
    ("power", "GND"), ("power", "GNDD"), ("power", "+5V"), ("power", "+15V"), ("power", "PWR_FLAG"),
]
_cache = {}


def library(name):
    if name not in _cache:
        _cache[name] = {s[1]: s for s in find_all(load(os.path.join(KICAD, name + ".kicad_sym")), "symbol")}
    return _cache[name]


def flat(libname, name):
    s = copy.deepcopy(library(libname)[name])
    ext = find(s, "extends")
    if not ext:
        return s
    base = flat(libname, ext[1])
    out = copy.deepcopy(base)
    out[1] = name
    for sub in find_all(out, "symbol"):
        sub[1] = sub[1].replace(ext[1] + "_", name + "_", 1)
    props = {p[1]: p for p in find_all(s, "property")}
    for i, c in enumerate(out):
        if isinstance(c, list) and c and c[0] == "property" and c[1] in props:
            out[i] = props.pop(c[1])
    for p in props.values():
        out.insert(2, p)
    return out


def _pin(kind, x, y, ang, name, num, length=2.54, hide=False):
    return (f'(pin {kind} line (at {x} {y} {ang}) (length {length}){" (hide yes)" if hide else ""} '
            f'(name "{name}" (effects (font (size 1.27 1.27)))) (number "{num}" (effects (font (size 1.27 1.27)))))')


def opa462():
    """TI OPA462 (180 V op amp, 8-pin HSOIC PowerPAD DDA). Pins from the datasheet SBOS803A section 5:
    1 E/D Com, 2 -IN, 3 +IN, 4 V-, 5 Status Flag (open drain, active low, referenced to E/D Com),
    6 OUT, 7 V+, 8 E/D. The PowerPAD is internally connected to V- and must be soldered: pin 9 here,
    the exposed pad of KiCad's TI_SO-PowerPAD-8 footprint. Not in KiCad's stock libraries."""
    body = ('(polyline (pts (xy -5.08 7.62) (xy -5.08 -7.62) (xy 7.62 0) (xy -5.08 7.62)) '
            '(stroke (width 0.254) (type default)) (fill (type background)))')
    pins = [_pin("input", -7.62, 2.54, 0, "+", 3), _pin("input", -7.62, -2.54, 0, "-", 2),
            _pin("output", 10.16, 0, 180, "~", 6),
            _pin("power_in", 0, 7.62, 270, "V+", 7, length=3.81), _pin("power_in", -2.54, -10.16, 90, "V-", 4, length=3.81),
            _pin("passive", 0, -10.16, 90, "EP", 9, length=4.83),
            _pin("input", 2.54, -10.16, 90, "E/D", 8, length=5.33), _pin("passive", 5.08, -10.16, 90, "E/D Com", 1, length=6.35),
            _pin("open_collector", 5.08, 7.62, 270, "FLAG", 5, length=6.35)]
    txt = ('(symbol "OPA462" (pin_names (offset 0.254)) (exclude_from_sim no) (in_bom yes) (on_board yes) '
           '(property "Reference" "U" (at 0 10.16 0) (effects (font (size 1.27 1.27)))) '
           '(property "Value" "OPA462" (at 0 -13.97 0) (effects (font (size 1.27 1.27)))) '
           '(property "Footprint" "Package_SO:TI_SO-PowerPAD-8_ThermalVias" (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes))) '
           '(property "Datasheet" "https://www.ti.com/lit/gpn/opa462" (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes))) '
           '(property "Description" "180 V, 6.5 MHz high-voltage op amp, SO-8 PowerPAD (pad = V-)" (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes))) '
           f'(symbol "OPA462_0_1" {body}) (symbol "OPA462_1_1" {" ".join(pins)}))')
    return parse(txt)


PASSIVE = {"EL34": ("1", "3", "8")}   # anode / cathode / g3: tubes in parallel on one net (OT_A, OT_B)
#                                  and a resistor-driven cathode; stock types (output, power_in) fail ERC


def patched(libname, name):
    s = flat(libname, name)
    for sub in find_all(s, "symbol"):
        for p in find_all(sub, "pin"):
            if str(find(p, "number")[1]) in PASSIVE.get(name, ()):
                p[1] = Sym("passive")
    return s


def main():
    lib = [Sym("kicad_symbol_lib"), [Sym("version"), 20251024], [Sym("generator"), "make_lib"],
           [Sym("generator_version"), "10.0"]]
    for libname, name in WANT:
        lib.append(patched(libname, name))
    lib.append(opa462())
    save(os.path.join(HERE, "lib", "tube_power_amp_revc.kicad_sym"), lib)
    for libname, name in WANT:
        s = flat(libname, name)
        pins = []
        for sub in find_all(s, "symbol"):
            for p in find_all(sub, "pin"):
                num, nm = find(p, "number"), find(p, "name")
                pins.append(f"{num[1]}={nm[1]}" if num and nm else "?")
        print(f"{name}: " + " ".join(pins))


if __name__ == "__main__":
    main()
