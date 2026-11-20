#!/usr/bin/env python3
"""Run a Phase 4 check (p2k ipc356_diff or p2k gerber_roundtrip --check) with one OPEN USER
QUESTION made explicit: the C1-C6 drills (STATUS.md "Decisions").

The KiCad library footprints of C1-C6 have 1.0 mm drills, Proteus has 1.143 mm (45 mil). Both
shared checks fail on a KiCad drill smaller than the Proteus one unless p2k_config.py DRILL_SMALLER
records it as a decision. The user has not decided yet (DRILL_SMALLER entry, or Proteus drills on
those footprints), so no entry is made. Until then this wrapper

  - runs the shared tool unchanged and prints its output,
  - passes ONLY when the tool's errors are exactly the 12 expected drill errors (both pads of
    C1-C6, Proteus 1.143 mm, KiCad 1.0 mm) and nothing else - one error more, one less or one
    different fails,
  - fails when the tool passes (then the question is answered: set PENDING_DRILLS = False below
    or call the tool directly from tools/check_all.sh),
  - prints a PENDING line that tools/check_all.sh repeats in its summary.

Usage: python3 tools/phase4_checks.py ipc356_diff | gerber_roundtrip
(P2K_PCB / P2K_REPORTS as for the shared tools, e.g. for negative tests on a scratch board.)
"""
import csv
import math
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P2K = os.path.join(ROOT, "tools", "p2k", "bin", "p2k")

PENDING_DRILLS = False                # decided 2026-11-20: KiCad drills kept (DRILL_SMALLER in p2k_config.py)
PENDING_REFS = ("C1", "C2", "C3", "C4", "C5", "C6")
PROTEUS_DRILL, KICAD_DRILL = 1.143, 1.0


def pending_pads():
    """{(refdes, pin): (x, y)} of the C1-C6 pads, from the IPC reference (IPC frame, mm)."""
    pads = {}
    with open(os.path.join(ROOT, "reference", "ipc356_pads.csv"), newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r["kind"] == "pad" and r["refdes"] in PENDING_REFS:
                assert abs(float(r["drill"]) - PROTEUS_DRILL) < 1e-6, r
                pads[(r["refdes"], r["pin"])] = (float(r["x_mm"]), float(r["y_mm"]))
    assert len(pads) == 12, pads
    return pads


def run(args):
    r = subprocess.run([P2K, *args], cwd=ROOT, capture_output=True, text=True)
    sys.stdout.write(r.stdout)
    sys.stderr.write(r.stderr)
    return r.returncode, r.stdout


def ipc356_diff(pads):
    """-> (exit code, pending pads found, other errors)"""
    code, out = run(["ipc356_diff"])
    found, other = set(), []
    for line in out.splitlines():
        if not line.startswith("ipc356_diff: ERROR "):
            continue
        m = re.fullmatch(r"ipc356_diff: ERROR pad (\S+?)-(\S+): drill Proteus ([\d.]+), KiCad ([\d.]+) is smaller", line)
        # kicad-cli writes the IPC-D-356 drill in 0.0001 inch: 1.0 mm -> 1.0008
        if m and (m[1], m[2]) in pads and abs(float(m[3]) - PROTEUS_DRILL) < 1e-6 and abs(float(m[4]) - KICAD_DRILL) < 0.002 \
                and (m[1], m[2]) not in found:
            found.add((m[1], m[2]))
        else:
            other.append(line)
    return code, found, other


def gerber_roundtrip(pads):
    code, out = run(["gerber_roundtrip", "--check"])
    # the tool prints only the first 10 drill errors: read them all from its report
    reports = os.environ.get("P2K_REPORTS") or os.path.join(ROOT, "reports")
    found, other = set(), []
    for line in open(os.path.join(reports, "roundtrip", "roundtrip.txt"), encoding="utf-8"):
        line = line.strip()
        if not line.startswith("ERROR "):
            continue
        m = re.fullmatch(r"ERROR plated: drill at \(([-\d.]+), ([-\d.]+)\): Proteus ([\d.]+) mm, KiCad ([\d.]+) mm is smaller", line)
        key = None
        if m and abs(float(m[3]) - PROTEUS_DRILL) < 1e-6 and abs(float(m[4]) - KICAD_DRILL) < 1e-6:
            key = next((k for k, (x, y) in pads.items()
                        if math.hypot(x - float(m[1]), y - float(m[2])) < 0.01 and k not in found), None)
        if key:
            found.add(key)
        else:
            other.append(line)
    m = re.search(r"^roundtrip: FAILED \((\d+) unexplained clusters, (\d+) draws/flashes without copper in the other set, "
                  r"(\d+) drill mismatches\)$", out, re.M)
    if code != 0 and (not m or (int(m[1]), int(m[2]), int(m[3])) != (0, 0, len(found) + len(other))):
        other.append("summary line does not match the report: " + (m[0] if m else "no FAILED line"))
    return code, found, other


def main():
    tool = sys.argv[1] if len(sys.argv) == 2 else ""
    if tool not in ("ipc356_diff", "gerber_roundtrip"):
        sys.exit(__doc__)
    pads = pending_pads()
    code, found, other = (ipc356_diff if tool == "ipc356_diff" else gerber_roundtrip)(pads)
    tag = f"phase4_checks[{tool}]"
    if not PENDING_DRILLS:
        return code
    if code == 0:
        print(f"{tag}: FAILED - the tool passes, so the C1-C6 drill question is answered: set PENDING_DRILLS = False "
              "in tools/phase4_checks.py (and update STATUS.md)")
        return 1
    missing = sorted(set(pads) - found)
    if other or missing:
        for e in other:
            print(f"{tag}: not a pending C1-C6 drill error: {e}")
        if missing:
            print(f"{tag}: expected C1-C6 drill errors not reported: " + " ".join(f"{r}-{p}" for r, p in missing))
        print(f"{tag}: FAILED ({len(other)} other errors, {len(found)}/12 pending drill errors)")
        return 1
    print(f"{tag}: PENDING USER DECISION - the tool fails only on the 12 C1-C6 holes (KiCad 1.0 mm, Proteus 1.143 mm); "
          "everything else passes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
