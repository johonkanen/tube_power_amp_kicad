#!/usr/bin/env python3
"""Generate lib/tube_power_amp.kicad_sym, the project symbol library (helpers: p2k.symgen).

Pin numbers equal the Proteus/IPC pin ids (STATUS.md "Phase 1 preparation"). All part symbols
are copied from the KiCad 10 standard library (flattened, pins renumbered where needed); the
Proteus pin definitions in ROOT.DSN ($PINSHORT name/number of the device symbols) agree:
  EL34 (8-PIN BELTON OCTAL pinout)  G3=1 H2=2 A=3 G2=4 G1=5 H1=7 K=8; pin 6 has no net
  TIPL760 (TO220)                   B=1 C=2 E=3   (= KiCad Q_NPN_BCE)
  MPSA92 (TO92)                     E=1 B=2 C=3   (= KiCad Q_PNP_EBC)
  1N4001 / 1N5933B                  A, K
  C5 / C6 (electrolytic)            +, -
Off-board (drawn in the PDF, no pads; symbols excluded from the board): OT (1650TA, Proteus pin
names P1 CT P2 S1-S5) and the VA' terminal. No power symbols: the IPC has no =POWER nets.

Run:  tools/gen_symbols.py           (needs the AppImage mount for the std libs)
      tools/gen_symbols.py --check   (fail if lib/tube_power_amp.kicad_sym is not up to date)
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "p2k"))  # proteus2kicad
from p2k.symgen import *  # noqa: E402,F401,F403
from p2k.symgen import _pin, run  # noqa: E402

def add_pins(sym, unit, pins):
    """Append pins [(number, name, type, x, y, rot)] to body `unit` (e.g. '_1_1') of a std symbol."""
    body = next(s for s in find_all(sym, "symbol") if s[1].endswith(unit))
    for num, name, etype, x, y, rot in pins:
        body.append(_pin(num, name, etype, x, y, rot))
    return sym


def el34():
    # KiCad Valve:EL34 already has the octal numbers (unit 1: 1 3 4 5 8, unit 2 = heater: 2 7);
    # names -> the Proteus names; heater and cathode passive (KiCad: power_in, which ERC would
    # report as undriven on the resistor-only cathode / heater nets); anode passive too (KiCad:
    # output; the tubes work in parallel pairs, U8 || U9 and U6 || U7, and ERC reports two
    # connected outputs as a pin_to_pin error); pin 6 (no net in the IPC, unused on the EL34) is
    # a PASSIVE pin on unit 1 that gets a no-connect flag in the sheet script. Not a no_connect
    # type pin: KiCad 10 keeps a no_connect pin in its own unconnected-(...) net even when a wire
    # joins it (ERC only warns no_connect_connected), so compare_netlists could not see a pin 6
    # wired by mistake (STATUS.md "Phase 4"). A wired passive pin is in the wire's net.
    sym = from_std("Valve", "EL34", "EL34", "U", desc="EL34 power pentode, octal; Proteus pin ids "
                   "G3=1 H2=2 A=3 G2=4 G1=5 (6 = no connection) H1=7 K=8; unit 2 = heater",
                   pins={"1": "1", "2": "2", "3": "3", "4": "4", "5": "5", "7": "7", "8": "8"},
                   names={"1": "G3", "2": "H2", "3": "A", "4": "G2", "5": "G1", "7": "H1", "8": "K"},
                   pin_types={"2": PAS, "3": PAS, "7": PAS, "8": PAS})
    return add_pins(sym, "_1_1", [("6", "NC", PAS, 2.54, -8.89, 90)])


def build():
    syms = [
        from_std("Device", "R", "R", "R", "R"),
        from_std("Device", "C", "C", "C", "C"),
        from_std("Device", "C_Polarized", "C_Polarized", "C", "C", desc="Polarized capacitor, Proteus pins +/-",
                 pins={"1": "+", "2": "-"}, names={"+": "+", "-": "-"}),
        from_std("Device", "D", "D", "D", desc="Diode, Proteus pins A/K", pins={"1": "K", "2": "A"}),
        from_std("Device", "D_Zener", "D_Zener", "D", desc="Zener diode, Proteus pins A/K", pins={"1": "K", "2": "A"}),
        from_std("Transistor_BJT", "TIP41", "TIPL760", "Q", "TIPL760",
                 desc="NPN power transistor TO-220 (TIPL760), Proteus ids 1=B 2=C 3=E"),
        from_std("Transistor_BJT", "MPSA92", "MPSA92", "Q", "MPSA92",
                 desc="PNP high-voltage transistor TO-92, Proteus ids 1=E 2=B 3=C"),
        el34(),
        from_std("Connector", "TestPoint", "PIN", "J", "PIN",
                 desc="Proteus TERMINAL / PIN: one pad (package C-120-60)"),
    ]
    va = from_std("Connector", "TestPoint", "PIN_OFFBOARD", "J", "TERMINAL",
                  desc="Proteus terminal drawn in the schematic without a pad (excluded from board)")
    set_flag(va, "on_board", False)
    syms.append(va)
    syms.append(box("OT_1650TA", "OT", [("P1", "P1", PAS), None, ("CT", "CT", PAS), None, ("P2", "P2", PAS)],
                    [("S1", "S1", PAS), ("S2", "S2", PAS), ("S3", "S3", PAS), ("S4", "S4", PAS), ("S5", "S5", PAS)],
                    value="1650TA", on_board=False,
                    desc="Hammond 1650TA output transformer (off-board; Proteus pins P1 CT P2, secondary S1-S5)"))
    return syms


if __name__ == "__main__":
    if "--force-regenerate" not in sys.argv:
        sys.exit("gen_symbols: FROZEN (generation stopped 2026-11-20, STATUS.md): the committed KiCad files are the "
                 "source; running this would overwrite KiCad edits. Pass --force-regenerate only to "
                 "reproduce the historical output in a scratch clone.")
    sys.argv.remove("--force-regenerate")
    sys.exit(run(build))
