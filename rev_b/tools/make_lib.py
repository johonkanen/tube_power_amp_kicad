#!/usr/bin/env python3
"""Build lib/tube_power_amp_revb.kicad_sym from KiCad's standard symbol libraries: the symbols the
rev B sheets use, flattened (KiCad's derived 'extends' symbols resolved, since a schematic's
lib_symbols needs them whole). The one change to a stock symbol: the EL34's pins 1, 3 and 8 are
passive (PASSIVE below)."""
import copy
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "..", "tools", "p2k"))
from p2k.sexpr import Sym, find, find_all, load, save  # noqa: E402

KICAD = os.environ.get("KICAD_SYMBOLS", "/mnt/c/Program Files/KiCad/10.0/share/kicad/symbols")
WANT = [
    ("Device", "R"), ("Device", "C"), ("Device", "C_Polarized"), ("Device", "D"), ("Device", "D_Zener"),
    ("Device", "D_Schottky"), ("Transistor_BJT", "MMBT3904"), ("Transistor_BJT", "MMBT3906"), ("Transistor_BJT", "MMBTA92"), ("Transistor_BJT", "MMBTA42"), ("Transistor_FET", "Q_PMOS_GDS"),
    ("Device", "NetTie_2"), ("Device", "Fuse"), ("Device", "D_Bridge_+AA-"),
    ("Valve", "EL34"), ("Transistor_FET", "2N7002"), ("Diode", "BAT54S"),
    ("Analog_DAC", "DAC7578xPW"), ("Reference_Voltage", "ADR4525"), ("Analog_ADC", "ADS7828"), ("Amplifier_Operational", "OPA4197xD"),
    ("Comparator", "LM2901"), ("Diode", "BAV99"), ("74xGxx", "74LVC2G17"), ("Reference_Voltage", "LM4040DBZ-10"),
    ("74xx", "74HC74"), ("74xx", "74HC4060"), ("74xGxx", "74LVC1G11"), ("74xGxx", "74LVC1G08"),
    ("Isolator", "PC817"), ("Interface_Expansion", "MCP23S17x-x-SS"),
    ("Connector_Generic", "Conn_02x07_Odd_Even"), ("Connector_Generic", "Conn_02x05_Odd_Even"),
    ("Connector_Generic", "Conn_01x01"), ("Connector_Generic", "Conn_01x02"), ("Connector_Generic", "Conn_01x03"),
    ("Connector_Generic", "Conn_01x05"), ("Connector", "TestPoint"), ("Connector_Generic", "Conn_02x03_Top_Bottom"), ("Device", "D_TVS"),
    ("power", "GND"), ("power", "GNDD"), ("power", "+5V"), ("power", "+15V"), ("power", "-15V"), ("power", "PWR_FLAG"),
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
    save(os.path.join(HERE, "lib", "tube_power_amp_revb.kicad_sym"), lib)
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
