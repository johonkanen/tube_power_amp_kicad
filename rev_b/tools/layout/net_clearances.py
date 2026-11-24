#!/usr/bin/env python3
"""Write build/layout/net_clearances.json for KiCadRoutingTools (--net-clearances): every net of a
non-default class with the clearance the router must keep from it. The plate nets get their INNER value
(3.2 mm: they run on In2 only); their exposed pads are fenced by 6.3 mm keep-outs drawn by hv_copper.py.
    python3 rev_b/tools/layout/net_clearances.py BOARD.kicad_pcb OUT.json"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import placement as PL  # noqa: E402

VAL = {"HV1250": 3.2, "HV450": 2.5, "BIAS80": 0.6, "HTR": 0.25}
txt = open(sys.argv[1]).read()
names = set(re.findall(r'\(net \d+ "([^"]*)"\)', txt)) | set(re.findall(r'\(net "([^"]*)"\)', txt))
out = {}
for cls, nets in PL.CLASS_NETS.items():
    if cls in VAL:
        for n in names:
            if n.rsplit("/", 1)[-1] in nets:
                out[n] = VAL[cls]
json.dump(out, open(sys.argv[2], "w"), indent=1)
print(f"{sys.argv[2]}: {len(out)} nets")
