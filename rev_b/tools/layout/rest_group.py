#!/usr/bin/env python3
"""Write the routing.json group "rest": every net of BOARD that is not a power / ground / HV-class net
(the leftover step of route_chain.sh routes them on any layer).
    python3 rev_b/tools/layout/rest_group.py BOARD.kicad_pcb routing.json"""
import json
import re
import sys

board, cfgp = sys.argv[1], sys.argv[2]
names = sorted(set(re.findall(r'\(net \d+ "([^"]*)"\)', open(board).read())) |
               set(re.findall(r'\(net "([^"]*)"\)', open(board).read())))
skip = {"GND", "GNDD", "+5V", "+15V", "-15V", "OT_A", "OT_B", "CL_A", "CL_B", "V_ANODE", "V_SCREEN",
        "DRV_A", "DRV_B", "G2_1", "G2_2", "G2_3", "G2_4", ""}
rest = [n for n in names if n.rsplit("/", 1)[-1] not in skip and not n.startswith("unconnected-")]
cfg = json.load(open(cfgp))
cfg["groups"]["rest"] = rest
json.dump(cfg, open(cfgp, "w"), indent=2)
print(f"rest: {len(rest)} nets")
