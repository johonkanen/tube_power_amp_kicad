#!/usr/bin/env python3
"""Compact listing of a DRC JSON (build/check/drc.json by default): type, rule, the two items.
   python3 rev_b/tools/layout/drc_list.py [drc.json] [TYPE ...]"""
import json
import re
import sys

args = sys.argv[1:]
path = args.pop(0) if args and args[0].endswith(".json") else "build/check/drc.json"
d = json.load(open(path))
want = set(args)


def short(s):
    s = re.sub(r"/0\d [^/\]]*/", "", s)
    return s[:70]


for v in d["violations"] + d.get("unconnected_items", []):
    if want and v["type"] not in want:
        continue
    rule = re.search(r"\((rule '[^']*'|netclass '[^']*')[^)]*actual ([\d.]+)", v["description"])
    print(v["type"], rule.group(0)[:70] if rule else "", "|", " / ".join(short(i["description"]) for i in v["items"]))
