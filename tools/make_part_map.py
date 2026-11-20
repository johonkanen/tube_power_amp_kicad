#!/usr/bin/env python3
"""Generate lib/part_map.csv: refdes -> PDF page, symbol, value, Proteus device and package.

Sources (STATUS.md "Phase 1 preparation"):
  refdes   reference/ipc356_pads.json (`refdes` = KiCad name, `refdes_proteus` = Proteus name),
           plus OFF_BOARD (drawn in the PDF, no layout part, no IPC pads)
  value    schematic value from ROOT.DSN in source/OUTPUT.pdsprj (= the PDF), read with the
           FULL refdes set (IPC refdes + OFF_BOARD; a subset makes lyt_parts misattribute records)
  device, package   layout record in ROOT.LYT (OFF_BOARD parts have none)
  sheet    PDF page whose text layer has the refdes; PAGE_OVERRIDES for the ambiguous ones
  lib_id   SYMBOL_BY_DEVICE (Proteus device -> lib/tube_power_amp.kicad_sym symbol)

C5 is a workaround for p2k candidate 1 (STATUS.md): its value and device are `10µ/400V` with a
Latin-1 µ, which p2k.pdsprj drops (dsn_values -> None, lyt_parts misses the record). The value
is the PDF text; device and package are read from the ROOT.LYT bytes by hand (LATIN1_PARTS).

  tools/make_part_map.py           write lib/part_map.csv
  tools/make_part_map.py --check   fail if lib/part_map.csv is not up to date
"""
import csv
import io
import json
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "p2k"))  # proteus2kicad
from p2k import board, pdftext, pdsprj  # noqa: E402

PRJ = board.path("source", "OUTPUT.pdsprj")
PDF = board.path("source", "schematic_pdf", "OUTPUT.PDF")
OUT = board.path("lib", "part_map.csv")
LIB = board.config().PROJECT

C, CP, R = "C", "C_Polarized", "R"
SYMBOL_BY_DEVICE = {
    "22N XICON": C, "HITEMP100U100V": CP, "10µ/400V": CP,
    "MINRES100K": R, "1K/5W": R, "METALFILM1K": R,
    "1N4001": "D", "1N5933B": "D_Zener",
    "TIPL760": "TIPL760", "MPSA92": "MPSA92",
    "EL34": "EL34",
    "TERMINAL": "PIN", "PIN": "PIN",
}

# Parts drawn in the PDF (sheet 1) without a layout part / IPC pads: symbols excluded from the
# board; Phase 2 needs them in OFF_BOARD_PARTS. Proteus refdes -> (KiCad refdes, lib symbol, device).
OFF_BOARD = {
    "OT": ("OT", "OT_1650TA", "1650TA"),              # Hammond 1650TA output transformer (model TRAN2P5S)
    "VA'": ("VA_PRIME", "PIN_OFFBOARD", "TERMINAL"),  # OT centre-tap terminal (anode supply), no pad
}

# p2k candidate 1: parts whose Latin-1 strings p2k.pdsprj cannot read (bytes checked in ROOT.LYT:
# "C5" 0x08 "10\xb5/400V" 0x08 "10\xb5/400V" ... "RAD ELEC R5 D10", nets OTGND / B-).
LATIN1_PARTS = {
    "C5": {"value": "10µ/400V", "device": "10µ/400V", "package": "RAD ELEC R5 D10"},
}

# Refdes whose PDF text-layer hits are ambiguous (resolved on the page renders):
PAGE_OVERRIDES = {
    "+6": 1,    # page 2 has the net terminal "HT +6" (R17 / VCC), not the part
    "VS'": 2,   # the part (R19 divider input); page 1 "VS'" is the net terminal of STANDBY / R13-R16
}

FIELDS = ["refdes", "sheet", "lib_id", "value", "device", "package", "proteus_refdes", "off_board"]


def build():
    ipc = json.load(open(board.path("reference", "ipc356_pads.json")))
    kicad = {}
    for p in ipc["pads"]:
        if p["kind"] == "pad":
            kicad[p["refdes_proteus"]] = p["refdes"]
    for ref in OFF_BOARD:
        assert ref not in kicad, f"OFF_BOARD part {ref} has IPC pads"
        kicad[ref] = OFF_BOARD[ref][0]
    refs = set(kicad)
    values = pdsprj.dsn_values(PRJ, refs)
    parts = pdsprj.lyt_parts(PRJ, refs)
    pages = pdftext.refdes_pages(pdftext.pdf_words(PDF), refs)
    errors = []
    rows = []
    for ref in sorted(refs):
        page = PAGE_OVERRIDES.get(ref)
        if page is None:
            if len(pages[ref]) != 1:
                errors.append(f"{ref}: PDF pages {pages[ref]} (add to PAGE_OVERRIDES)")
                continue
            page = pages[ref][0]
        elif page not in pages[ref]:
            errors.append(f"{ref}: PAGE_OVERRIDES page {page} not among the PDF hits {pages[ref]}")
        if ref in LATIN1_PARTS:
            fix = LATIN1_PARTS[ref]
            if values.get(ref) not in (None, fix["value"]) or (ref in parts and parts[ref]["device"] != fix["device"]):
                errors.append(f"{ref}: pdsprj now reads {values.get(ref)!r} / {parts.get(ref)}: drop LATIN1_PARTS")
            value, dev, pkg = fix["value"], fix["device"], fix["package"]
        elif ref in OFF_BOARD:
            if ref in parts:
                errors.append(f"{ref}: OFF_BOARD part has a layout record")
            value, dev, pkg = values.get(ref), OFF_BOARD[ref][2], ""
        else:
            value, dev, pkg = values.get(ref), parts[ref]["device"], parts[ref]["package"]
        if not value:
            errors.append(f"{ref}: no schematic value")
            continue
        if ref in OFF_BOARD:
            sym = OFF_BOARD[ref][1]
        elif dev in SYMBOL_BY_DEVICE:
            sym = SYMBOL_BY_DEVICE[dev]
        else:
            errors.append(f"{ref}: no symbol for Proteus device {dev!r}")
            continue
        rows.append({"refdes": kicad[ref], "sheet": page, "lib_id": f"{LIB}:{sym}", "value": value,
                     "device": dev, "package": pkg, "proteus_refdes": ref if ref != kicad[ref] else "",
                     "off_board": "yes" if ref in OFF_BOARD else ""})
    for ref in sorted(set(PAGE_OVERRIDES) - refs):
        errors.append(f"PAGE_OVERRIDES: {ref} is not a refdes")
    if errors:
        sys.exit("make_part_map:\n  " + "\n  ".join(errors))
    key = lambda r: (r["sheet"], [(0, int(t), "") if t.isdigit() else (1, 0, t)
                                  for t in re.findall(r"\d+|\D+", r["refdes"])])
    rows.sort(key=key)
    buf = io.StringIO()
    buf.write("# Generated by tools/make_part_map.py - do not edit. sheet = Proteus PDF page;"
              " value = schematic value (ROOT.DSN; C5 from the PDF); device/package = Proteus layout record;"
              " off_board = drawn in the PDF, no pads (symbol excluded from board)\n")
    w = csv.DictWriter(buf, fieldnames=FIELDS, lineterminator="\n")
    w.writeheader()
    w.writerows(rows)
    return buf.getvalue(), rows


def main():
    text, rows = build()
    rel = os.path.relpath(OUT, board.root())
    per = {}
    for r in rows:
        per[r["sheet"]] = per.get(r["sheet"], 0) + 1
    summary = f"{len(rows)} parts ({sum(not r['off_board'] for r in rows)} on the board); per sheet " + \
        " ".join(f"{s}:{n}" for s, n in sorted(per.items()))
    if "--check" in sys.argv:
        if not os.path.exists(OUT) or open(OUT, encoding="utf-8").read() != text:
            print(f"make_part_map: {rel} is out of date, run tools/make_part_map.py")
            return 1
        print(f"make_part_map: {rel} up to date, {summary}")
        return 0
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    open(OUT, "w", encoding="utf-8").write(text)
    print(f"wrote {rel}: {summary}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
