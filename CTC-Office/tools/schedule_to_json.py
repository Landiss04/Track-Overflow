"""Convert the course schedule workbook to JSON.

Reads ``documents/Project_Information/Schedule v4.xlsx`` (one sheet per
line, one "Train N Arrival Time at Station" column per train) and writes
``utils/schedule_v4.json``. Uses only the standard library: an .xlsx is
a zip of XML.

Output, per line and per train, is the ordered list of timed stops::

    {"block_id": "2", "station": "PIONEER", "arrival_s": 60}

Times are seconds after the schedule start, when Train 1 leaves the
first timed block (backend units, ``truth/conventions/units.md``). IDs
are strings (``truth/conventions/identifiers.md``). Values are copied
as the workbook gives them; anything that disagrees with the track
layout files is reported as a warning, never corrected.

Dwell time is not copied: the workbook's 60 s dwell conflicts with
decision D007 (45 s), and dwell is train behaviour, not schedule data.

Run from the repository root::

    python CTC-Office/tools/schedule_to_json.py
"""

from __future__ import annotations

import json
import re
import sys
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
SOURCE = REPO / "documents" / "Project_Information" / "Schedule v4.xlsx"
OUTPUT = REPO / "utils" / "schedule_v4.json"
LAYOUT_FILES = {
    "Green": REPO / "TrackModel" / "green_line.json",
    "Red": REPO / "TrackModel" / "red_line.json",
}

_MAIN = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
_DOC_REL = (
    "http://schemas.openxmlformats.org/officeDocument/2006/relationships")
_PKG_REL = "http://schemas.openxmlformats.org/package/2006/relationships"
_NS = {"m": _MAIN}

SECONDS_PER_DAY = 86_400
_TRAIN_HEADER = re.compile(r"Train (\d+) Arrival Time at Station")
# Workbook tags that are not station names.
_NOT_NAMES = {"STATION", "UNDERGROUND", "UNDERDROUND"}

Grid = dict[tuple[str, int], str]


def read_sheets(path: Path) -> dict[str, Grid]:
    """Cell values of every sheet, keyed by sheet then (col, row)."""
    with zipfile.ZipFile(path) as book:
        shared: list[str] = []
        if "xl/sharedStrings.xml" in book.namelist():
            strings = ET.fromstring(book.read("xl/sharedStrings.xml"))
            shared = [
                "".join(t.text or "" for t in item.iter(f"{{{_MAIN}}}t"))
                for item in strings.findall("m:si", _NS)
            ]
        workbook = ET.fromstring(book.read("xl/workbook.xml"))
        rels = ET.fromstring(book.read("xl/_rels/workbook.xml.rels"))
        targets = {
            rel.get("Id"): rel.get("Target", "")
            for rel in rels.iter(f"{{{_PKG_REL}}}Relationship")
        }
        sheets: dict[str, Grid] = {}
        sheet_list = workbook.find("m:sheets", _NS)
        for sheet in [] if sheet_list is None else sheet_list:
            target = targets[sheet.get(f"{{{_DOC_REL}}}id")]
            xml = ET.fromstring(
                book.read("xl/" + target.lstrip("/").removeprefix("xl/")))
            grid: Grid = {}
            data = xml.find("m:sheetData", _NS)
            for row in [] if data is None else data:
                for cell in row:
                    value = cell.find("m:v", _NS)
                    if value is None or value.text is None:
                        continue
                    text = value.text
                    if cell.get("t") == "s":
                        text = shared[int(text)]
                    match = re.match(r"([A-Z]+)(\d+)", cell.get("r", ""))
                    if match:
                        grid[(match.group(1), int(match.group(2)))] = text
            sheets[sheet.get("name", "")] = grid
    return sheets


def station_name(infrastructure: str) -> str | None:
    """The station name in an Infrastructure cell, or None."""
    parts = [p.strip() for p in re.split(r"[;:]", infrastructure)]
    names = [p for p in parts if p and p.upper() not in _NOT_NAMES]
    return " ".join(names[0].split()) if names else None


def _header(grid: Grid, text: str) -> str:
    return next(col for (col, row), value in grid.items()
                if row == 1 and value == text)


def convert_sheet(line: str, grid: Grid) -> dict[str, Any]:
    """One line's trains and their timed stops."""
    block_col = _header(grid, "Block Number")
    infra_col = _header(grid, "Infrastructure")
    train_cols = sorted(
        ((int(m.group(1)), col) for (col, row), value in grid.items()
         if row == 1 and (m := _TRAIN_HEADER.fullmatch(value.strip()))),
    )
    first_col = train_cols[0][1]
    stop_rows = sorted(row for (col, row) in grid
                       if col == first_col and row > 1)
    trains = []
    for number, col in train_cols:
        stops = []
        for row in stop_rows:
            if (col, row) not in grid:
                continue
            stops.append({
                "block_id": str(int(float(grid[(block_col, row)]))),
                "station": station_name(grid.get((infra_col, row), "")),
                "arrival_s": round(float(grid[(col, row)])
                                   * SECONDS_PER_DAY),
            })
        trains.append({"train_id": str(number), "stops": stops})
    return {"line": line, "trains": trains}


def _headway_s(lines: list[dict[str, Any]]) -> int | None:
    gaps = {
        b["stops"][0]["arrival_s"] - a["stops"][0]["arrival_s"]
        for line in lines
        for a, b in zip(line["trains"], line["trains"][1:])
    }
    return gaps.pop() if len(gaps) == 1 else None


def check_against_layout(lines: list[dict[str, Any]]) -> list[str]:
    """Warnings where the schedule disagrees with the layout files."""
    warnings = []
    for line in lines:
        with open(LAYOUT_FILES[line["line"]], encoding="utf-8") as layout:
            infrastructure = {
                str(b["block_number"]): b.get("infrastructure") or {}
                for b in json.load(layout)["blocks"]
            }
        stops = line["trains"][0]["stops"]
        # The first timed block is the departure point, not a station.
        for index, stop in enumerate(stops):
            block = stop["block_id"]
            if block not in infrastructure:
                warnings.append(
                    f"{line['line']} block {block}: not in the layout")
                continue
            layout_has_station = "station" in infrastructure[block]
            layout_name = infrastructure[block].get("station")
            if index and not layout_has_station:
                warnings.append(
                    f"{line['line']} block {block}: timed stop, but the "
                    "layout has no station on this block")
            elif stop["station"] and layout_name not in (
                    None, stop["station"]):
                warnings.append(
                    f"{line['line']} block {block}: station "
                    f"{stop['station']!r}, layout says {layout_name!r}")
        for a, b in zip(stops, stops[1:]):
            gap = b["arrival_s"] - a["arrival_s"]
            if gap < 0 or gap > 15 * 60:
                warnings.append(
                    f"{line['line']} block {a['block_id']} -> "
                    f"{b['block_id']}: {gap} s between stops")
    return warnings


def convert(source: Path = SOURCE) -> tuple[dict[str, Any], list[str]]:
    """The schedule document and any layout warnings."""
    sheets = read_sheets(source)
    lines = []
    for sheet_name, grid in sheets.items():
        line = sheet_name.split()[0]          # "Green Line Schedule"
        lines.append(convert_sheet(line, grid))
    document = {
        "source": source.relative_to(REPO).as_posix(),
        "time_unit": "s",
        "time_origin": "schedule start; Train 1 is at its first stop at 0",
        "headway_s": _headway_s(lines),
        "lines": lines,
    }
    return document, check_against_layout(lines)


def main() -> int:
    """Write the JSON and print any warnings."""
    document, warnings = convert()
    with open(OUTPUT, "w", encoding="utf-8", newline="\n") as out:
        json.dump(document, out, indent=2)
        out.write("\n")
    for line in document["lines"]:
        print(f"{line['line']}: {len(line['trains'])} trains, "
              f"{len(line['trains'][0]['stops'])} timed stops each")
    for warning in warnings:
        print("WARNING:", warning, file=sys.stderr)
    print(f"wrote {OUTPUT.relative_to(REPO).as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
