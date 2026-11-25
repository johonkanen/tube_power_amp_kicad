#!/usr/bin/env python3
"""Board-local footprints for the power amp rev C (lib/tube_power_amp_revc.pretty) and the
project's fp-lib-table. Rev C keeps rev B's mechanics, so the footprints are copied unchanged from
rev_b/lib/tube_power_amp_revb.pretty (generated there by rev_b/tools/make_footprints.py: the octal
socket with the pin-circle courtyard, the 5 W resistors, the blade tabs). Everything else comes from
KiCad's stock libraries.
Run: python3 rev_c/tools/make_footprints.py
"""
import os
import shutil

RC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(RC, "..", "rev_b", "lib", "tube_power_amp_revb.pretty")
OUT = os.path.join(RC, "lib", "tube_power_amp_revc.pretty")


def main():
    os.makedirs(OUT, exist_ok=True)
    for f in sorted(os.listdir(SRC)):
        shutil.copy(os.path.join(SRC, f), os.path.join(OUT, f))
    open(os.path.join(RC, "kicad", "fp-lib-table"), "w").write(
        '(fp_lib_table\n\t(version 7)\n\t(lib (name "tube_power_amp_revc")(type "KiCad")'
        '(uri "${KIPRJMOD}/../lib/tube_power_amp_revc.pretty")(options "")'
        '(descr "rev C board-local footprints, copied from rev B (tools/make_footprints.py)"))\n)\n')
    print(sorted(os.listdir(OUT)))


if __name__ == "__main__":
    main()
