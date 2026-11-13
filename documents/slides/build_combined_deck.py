"""Build the combined design review deck from the combined SDD.

The deck shows the same figures as ``documents/sdd/Railway_Sim_SDD.md``:
it calls ``build_sdd.build()`` and lays out, for the system, the
architecture, software architecture, representative interaction,
deployment, concepts and decisions, then for each module its overview,
use case diagrams, use case descriptions, architecture (component view),
class diagrams and one sequence diagram per use case.

Tall diagrams are split across slides at the emptiest row (Deck.diagram).
Every slide of a module names its presenter in the speaker notes.

Run from the repository root:  python documents/slides/build_combined_deck.py
"""

from __future__ import annotations

import math
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image
from pptx.util import Inches, Pt

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "sdd"))

import build_sdd  # noqa: E402
from build_decks import (INK, MUTED, NAVY, PAPER, SPLIT, WHITE,  # noqa: E402
                         Deck, FONT)

OUT = HERE / "design_review_combined.pptx"
FOOTER = "Track Overflow \u00b7 Design Review \u00b7 2026-10-22"

# Figures left out of the deck: shown as text on the description slides.
SKIP = {"03_use-case-descriptions.png"}
# Sequence diagrams whose use case is not stated in their caption.
SD_FOR_UC = {"05_sequence-advance-one-simulation-step.png": 1}
# Smallest scale, displayed size over source size on a 1920-wide
# projector, at which a diagram's text stays readable.
READABLE = 0.5

UC_HEADING = re.compile(
    r"^#####\s+(?:UC-(?:TM-)?(\d+)[:\s]+|Use case (\d+)\s*[\u2014-]\s*)(.*)$")

OVERVIEW = {
    "CTC Office": [
        "The dispatcher's console for the Green and Red Lines; one process "
        "on the host PC",
        "Creates every train and its ID, and releases it from the yard (D022)",
        "Dispatches by hand, or runs the loaded schedule automatically (D020)",
        "Every step: route, authority and suggested speed for each train's "
        "block and the next",
        ("Knows trains only from occupancy; a failed block reads occupied", 1),
        "Closes blocks and sets switches in maintenance mode",
        "Commands the shared clock: run, pause, 1x and 10x (D017)",
    ],
    "Track Controller (SW)": [
        "Runs every wayside controller of the Green Line, on the host PC",
        ("Six waysides by default; set when the line is loaded", 1),
        "Each wayside: its territory from the layout and its own Boolean PLC "
        "program",
        "Write, load, run and commit PLC programs in the window",
        "Scans once per tick: switches, signals, crossings, and speed and "
        "authority on each track circuit",
        "Reports occupancy, read-back and readiness to the CTC Office; sends "
        "nothing while not ready",
    ],
    "Track Controller (HW)": [
        "Runs every wayside controller of the Red Line (D021)",
        "Each wayside: its own territory database and its own Boolean PLC "
        "program",
        "Knows blocks, never trains: everything it exchanges is keyed by "
        "block",
        "Core on a Raspberry Pi 5; window on the PC; one USB cable (D027)",
        "Every statement compiled twice and run on two channels, compared "
        "every scan",
        ("Orange \u00abplanned\u00bb = designed, not built: the read-only "
         "vital PLC block", 1),
    ],
    "Track Model": [
        "Simulates the physical track of the Green and Red Lines from the "
        "layout files",
        "Places trains from the Train Model's block and offset; derives "
        "occupancy",
        "Carries each block's speed and authority on its track circuit; "
        "beacons; the signal light ahead",
        "Applies switch, signal and crossing commands and reports their "
        "actual state",
        "Stations: ticket sales to the CTC Office, boarding; temperature and "
        "track heaters",
        "Murphy injects broken rail, track circuit and power failures",
    ],
    "Train Model": [
        "Physics of every train: power, grade, rolling resistance and brakes "
        "give its motion",
        "Five-car Bombardier Flexity 2; passengers change its mass",
        "Doors, lights, cabin temperature and announcements follow the "
        "Train Controller",
        "Passes the track circuit and beacon on to the Train Controller",
        "Reports each train's block and offset to the Track Model",
        "Murphy injects engine, signal pickup and brake failures; passengers "
        "pull the emergency brake",
    ],
    "Train Controller (SW and HW)": [
        "The vital on-board controller of each train: one code base, SW "
        "(Green) and HW on a Pi (Red)",
        "PI speed law to traction power, 0 to 480 kW; Manual and Automatic",
        "Commanded speed is the only cap; service brake at authority 0; no "
        "traction under braking",
        "Infers engine, brake and signal pickup failures; latches the "
        "emergency brake",
        "Doors, lights, cabin temperature and station announcements",
        "The engineer commissions Kp and Ki before a train may move",
    ],
}


@dataclass
class UseCase:
    number: int
    title: str
    rows: list[tuple[str, str]] = field(default_factory=list)

    def field(self, *names: str) -> str:
        for key, value in self.rows:
            if key.lower().rstrip(":") in names:
                return value
        return ""


def chapters(text: str) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    current = None
    for line in text.split("\n"):
        m = re.match(r"^### 5\.\d+ (.*)$", line)
        if m:
            current = m.group(1)
            out[current] = []
        elif line.startswith("## 6. "):
            current = None
        elif current:
            out[current].append(line)
    return out


def table_rows(lines: list[str]) -> list[list[str]]:
    rows = []
    for line in lines:
        s = line.strip()
        if not s.startswith("|") or re.fullmatch(r"\|[\s:|-]+\|", s):
            continue
        cells = [build_sdd.plain(c) for c in s.strip("|").split("|")]
        rows.append(cells)
    return rows


def use_cases(lines: list[str]) -> list[UseCase]:
    found: list[UseCase] = []
    i = 0
    while i < len(lines):
        m = UC_HEADING.match(lines[i])
        if not m:
            i += 1
            continue
        number = int(m.group(1) or m.group(2))
        title = build_sdd.plain(m.group(3))
        j = i + 1
        while j < len(lines) and not re.match(r"^#{1,5} ", lines[j]):
            j += 1
        body = lines[i + 1:j]
        uc = UseCase(number, title)
        rows = [r for r in table_rows(body) if len(r) == 2 and any(r)]
        if rows:
            uc.rows = [(k, v) for k, v in rows if k]
        else:
            text = " ".join(l.strip() for l in body
                            if l.strip() and not l.lstrip().startswith(("![", "*Figure")))
            parts = re.split(r"\*\*([^*]+?):\*\*", text)
            uc.rows = [(parts[k].strip(), build_sdd.plain(parts[k + 1]))
                       for k in range(1, len(parts) - 1, 2)]
        found.append(uc)
        i = j
    if found:
        return found
    # The Track Model: one table, one row per use case.
    for k, line in enumerate(lines):
        if line.strip().startswith("| ID | Use case"):
            j = k
            while j < len(lines) and lines[j].strip().startswith("|"):
                j += 1
            rows = table_rows(lines[k:j])
            header, body = rows[0], rows[1:]
            for r in body:
                m = re.match(r"UC-(\d+)", r[0])
                if m:
                    found.append(UseCase(int(m.group(1)), r[1],
                                         list(zip(header[2:], r[2:]))))
            break
    return found


def uc_of(fig: dict) -> int | None:
    name = Path(fig["path"]).name
    if name in SD_FOR_UC:
        return SD_FOR_UC[name]
    m = UC_HEADING.match("##### " + fig["heading"])
    if m:
        return int(m.group(1) or m.group(2))
    m = re.search(r"\(UC-?(\d+)\)", fig["caption"]) or re.match(
        r"SD-(\d+)\b", fig["caption"])
    return int(m.group(1)) if m else None


QUADRANTS = ((0, 0, 0.55, 0.55), (0.45, 0, 1, 0.55),
             (0, 0.45, 0.55, 1), (0.45, 0.45, 1, 1))
HALVES = ((0, 0, 1, 0.53), (0, 0.47, 1, 1))
SIDES = ((0, 0, 0.53, 1), (0.47, 0, 1, 1))


class CombinedDeck(Deck):
    def use_case(self, uc: UseCase, label: str, section: str, notes: str):
        """A two-column description table, split over slides if long."""
        rows = [(k, v.replace("**", "")) for k, v in uc.rows if v]
        chars = 108

        def lines(row: tuple[str, str]) -> int:
            return sum(max(1, math.ceil(len(p) / chars))
                       for p in row[1].split("\n")) + 0.3

        pages, page, used = [], [], 0.0
        for row in rows:
            n = lines(row)
            if page and used + n > 20:
                pages.append(page)
                page, used = [], 0.0
            page.append(row)
            used += n
        pages.append(page)
        for index, page in enumerate(pages, 1):
            title = f"{label} {uc.title}"
            if len(pages) > 1:
                title += f" ({index} of {len(pages)})"
            slide = self._chrome(title, section)
            slide.notes_slide.notes_text_frame.text = notes
            left, top, width, _ = self._body_box()
            shape = slide.shapes.add_table(len(page), 2, left, top, width,
                                           Inches(0.35) * len(page))
            table = shape.table
            table.columns[0].width = Inches(2.3)
            table.columns[1].width = width - Inches(2.3)
            for r, (key, value) in enumerate(page):
                self._fill(table.cell(r, 0), key, 16, WHITE, True, NAVY)
                self._fill(table.cell(r, 1), value, 16, INK, False,
                           PAPER if r % 2 == 0 else WHITE)

    def _fill(self, cell, text, size, color, bold, fill):
        cell.fill.solid()
        cell.fill.fore_color.rgb = fill
        cell.margin_left = cell.margin_right = Inches(0.08)
        cell.margin_top = cell.margin_bottom = Inches(0.03)
        frame = cell.text_frame
        frame.word_wrap = True
        for i, para_text in enumerate(text.split("\n")):
            para = frame.paragraphs[0] if i == 0 else frame.add_paragraph()
            run = para.add_run()
            run.text = para_text.strip()
            run.font.size = Pt(size)
            run.font.color.rgb = color
            run.font.bold = bold
            run.font.name = FONT

    def figure(self, fig: dict, title: str, section: str, notes: str,
               full: bool = False):
        """One figure, laid out so its text stays readable.

        Split into horizontal strips until the figure is drawn at least
        READABLE of its own size on a 1920-wide projector; if width is
        what limits it, show it whole and then in four close-ups.
        """
        path = build_sdd.DOCS / fig["path"]
        if path.stem in SPLIT:
            self.diagram(title, path, section=section, notes=notes, full=full,
                         parts=SPLIT[path.stem])
            return
        with Image.open(path) as picture:
            w, h = picture.size
        body_w, body_h = 1786, 860

        def scale(region: tuple) -> float:
            rw, rh = (region[2] - region[0]) * w, (region[3] - region[1]) * h
            return min(body_w / rw, body_h / rh)

        if fig["viewpoint"] != "Interaction":
            # Boxes must not be cut: whole, then overlapping close-ups.
            self.diagram(title, path, section=section, notes=notes,
                         full=full, parts=1)
            if scale((0, 0, 1, 1)) < READABLE:
                self._close_ups(fig, title, section, notes, scale)
            return
        # A tall, narrow figure fills a fraction of the slide's width
        # whatever its resolution: split it by shape as well.
        least = max(1, min(4, int(h / w * body_w / body_h / 1.3)))
        for parts in range(least, 5):
            if min(body_w / w, body_h * parts / h) >= READABLE:
                self.diagram(title, path, section=section, notes=notes,
                             full=full, parts=parts)
                return
        self.diagram(title, path, section=section, notes=notes, full=full,
                     parts=1)
        self._close_ups(fig, title, section, notes, scale)

    def _close_ups(self, fig, title, section, notes, scale):
        regions = next((r for r in (HALVES, SIDES, QUADRANTS)
                        if scale(r[0]) >= READABLE), QUADRANTS)
        self.zoom(fig, title, section, "Close-up of the previous slide. "
                  + notes, regions)

    def whole(self, fig: dict, title: str, section: str, notes: str,
              full: bool = True):
        self.diagram(title, build_sdd.DOCS / fig["path"], section=section,
                     notes=notes, full=full, parts=1)

    def zoom(self, fig: dict, title: str, section: str, notes: str,
             regions: tuple = QUADRANTS):
        """The figure in close-up: one slide per region, in reading order."""
        path = build_sdd.DOCS / fig["path"]
        for k, region in enumerate(regions, 1):
            self.diagram(f"{title} (detail {k} of {len(regions)})", path,
                         section=section, notes=notes, full=True, crop=region,
                         parts=1)


def system_part(deck: CombinedDeck, figs: list[dict]) -> None:
    by_section = {}
    for f in figs:
        by_section.setdefault(f["section"], []).append(f)
    deck.section("The system", "Architecture, software architecture, "
                 "interaction, deployment and the concepts every module "
                 "relies on")
    deck.whole(by_section["3.1"][0], "System architecture", "System",
                "Presenter: Ivan. Five modules; the Track Controller and Train "
                "Controller each have a SW variant (Green Line) and a HW "
                "variant on a Raspberry Pi (Red Line). Commands go down from "
                "the CTC Office through the waysides and the track to the "
                "train; status comes back up. The Track Model also sends the "
                "signal ahead to the Train Controller and ticket sales to the "
                "CTC Office. In the running system every arrow passes through "
                "the central harness (D005).")
    deck.zoom(by_section["3.1"][0], "System architecture", "System",
              "Close-up of the system architecture, in reading order.")
    one, two = by_section["3.2"]
    deck.whole(one, "Software architecture (1 of 2): harness and processes",
                "System", "Presenter: Braden. One executable: with no "
                "arguments it is the central harness; with --module it is one "
                "module process. The harness supervises the seven module "
                "processes, paces the ticks, maps every edge (SystemEdges) and "
                "keeps the roster of trains. Each module process holds its "
                "module and a ModuleLink to the harness: newline JSON over a "
                "local socket.", full=True)
    deck.zoom(one, "Software architecture (1 of 2)", "System",
              "Close-up: the harness above, the module processes below.",
              HALVES)
    deck.whole(two, "Software architecture (2 of 2): contracts and "
                "implementations", "System", "Presenter: Braden. Each module "
                "owns its boundary types and its Protocol; each variant "
                "implements it. The HW hosts hold a remote proxy that relays "
                "the harness's steps over USB to the module's core on the Pi, "
                "behind PiLinkServer. No module imports another's types: the "
                "harness's edge functions translate.", full=True)
    deck.zoom(two, "Software architecture (2 of 2)", "System",
              "Close-up of the module contracts and their implementations.",
              HALVES)
    deck.whole(by_section["3.5"][0], "Representative interaction: movement "
                "authority", "System", "Presenter: Braden. Ticks k to k+5. "
                "Every module steps on the outputs of the tick before, so the "
                "CTC Office's suggestion reaches the wayside on the next tick, "
                "the track circuit on the one after, and the train controller "
                "a few ticks after the decision. The harness waits for every "
                "reply before the next tick (D017).", full=True)
    deck.zoom(by_section["3.5"][0], "Representative interaction", "System",
              "Close-up: the first ticks, then the last.", HALVES)
    deck.whole(by_section["3.6"][0], "Deployment", "System",
                "Presenter: Braden. One Windows 11 PC runs the executable as "
                "the harness and once per module. Data files: the line "
                "layouts, the schedule, the wayside databases and PLC "
                "programs, the event log. Two Raspberry Pi 5 boards, one per "
                "HW variant, each linked to its host process by one USB cable "
                "as a USB serial device, found by its product name (D027).",
                full=True)
    deck.zoom(by_section["3.6"][0], "Deployment", "System",
              "Close-up of the deployment, in reading order.")

    deck.bullets("Route", [
        "The blocks a train runs from the yard to its stations and back "
        "(D020, D022)",
        "The CTC Office plans it: shortest route on the graph of blocks and "
        "switch legs",
        ("Never turns a train back; goes round closed, failed and blocked "
         "blocks; no detour over 2x", 1),
        "Never sent whole: speed and authority for the train's block and "
        "the next",
        "The waysides' PLC programs set the switches; the CTC Office only "
        "in maintenance mode",
        ("Authority stops before a switch not yet set for the route", 1),
        "The Track Model never routes: a train follows the rails as the "
        "switches lie",
    ], section="System concepts")
    deck.bullets("Authority", [
        "Blocks ahead of the train's block it may still enter; 0 = stop "
        "(D013)",
        "CTC Office: computes it, never into an occupied, closed or "
        "another train's block",
        "Track Controller: AUTH_n passes it down block n's circuit or sends "
        "0; speed is ANDed with it",
        "Track Model: holds it as the block's track circuit; a failed "
        "circuit carries 0 and 0",
        "Train Controller: uses the count as given; at 0 it targets 0 and "
        "brakes while moving",
        ("A drop to 0 from 2 or more blocks reads as a signal pickup "
         "failure", 1),
    ], section="System concepts")
    deck.table("Distribution of wayside controllers", ["Line", "Variant",
                                                      "Runs on", "Waysides"], [
        ["Green", "Track Controller SW", "Host PC",
         "6 by default; 2 up to one per block"],
        ["Red", "Track Controller HW", "Raspberry Pi 5 over USB",
         "3 proposed: 1\u201324 + 73\u201376, 25\u201345 + 67\u201372, "
         "46\u201366"],
        ["Rule", "A wayside owns a contiguous run of blocks and its devices",
         "", "A switch stays inside one wayside"],
        ["Rule", "A line runs only when every wayside on it is ready", "",
         "Otherwise the line holds fail-safe"],
        ["Rule", "No other module depends on the split", "",
         "Every I/O is keyed by block"],
    ], [1.2, 5.0, 2.6, 3.6], section="System concepts", size=15)
    deck.bullets("Simulation timing", [
        "One clock, in the harness (D017); time from 05:00:00, unwrapped",
        "Fixed dt = 0.1 s (D006): 1x = 10 ticks/s, 10x = 100 ticks/s, same "
        "results",
        "Each module steps on the outputs of the tick before",
        "The harness waits for every reply; pauses and names a module "
        "late by about 1 s",
        "Pause, 1x and 10x are the CTC Office's commands",
        "HW variants at 10x: USB round trip + scan under 10 ms",
    ], section="System concepts")
    deck.bullets("Vitality", [
        "Channels are non-vital (REQ-INTF-021); Track and Train Controllers "
        "are vital",
        "Wayside: the OS only holds the PLC program; every protection is "
        "PLC code",
        ("Read-only vital block after the user's program \u00abplanned, "
         "pending Harry\u00bb", 1),
        ("HW: two compilers, two interpreters, compared every scan", 1),
        ("Fail-safe: signals red, crossings active, speed and authority 0", 1),
        "Train: inputs validated all or nothing; failures latch the "
        "emergency brake",
        ("No traction under braking; no power until the gains are set", 1),
        "System: a failure reads as occupancy; no two trains share a block",
    ], section="System concepts", size=22)
    deck.code("Wayside language", (
        "// a comment\n"
        "VAR_IN  OCC_12 OCC_13 SWREV_12\n"
        "VAR_IN  CTCSW_12 CTCREV_12\n"
        "VAR_OUT SW_12\n"
        "\n"
        "LOCK_12 := OCC_12 OR OCC_13\n"
        "WANT_12 := CTCSW_12 AND CTCREV_12\n"
        "SW_12   := (LOCK_12 AND SWREV_12)\n"
        "           OR (NOT LOCK_12 AND WANT_12)"),
        ["Boolean only: NOT, AND, XOR, OR, 0, 1, parentheses",
         "Runs top to bottom once per tick; an unset name reads 0",
         "Speed crosses as five bits (SPD_n_0..4 in, CMD_n_0..4 out)",
         "Errors reported with line numbers; unknown I/O refused",
         "Shared by both variants; the names still differ"],
        section="System concepts")
    deck.bullets("Hardware/software interface", [
        "Same Protocol and the same I/O in both variants: the harness "
        "cannot tell them apart (D021)",
        "Each HW core on its own Raspberry Pi 5; its window on the PC",
        "One USB cable: the Pi is a USB serial (CDC-ACM) device, Windows' "
        "own driver (D027)",
        ("Found by its USB product name, never a fixed COM number", 1),
        "The harness's newline JSON, relayed by the host process, which "
        "owns the port",
        "The Pi journals every request, so a restarted Pi rebuilds its "
        "state",
        "A lost Pi: the harness pauses the clock and names the module",
    ], section="System concepts")
    deck.table("System design decisions", ["", "Decision", "Outcome"], [
        ["4.1", "Interface contract", "Each module's own types and Protocol; "
         "the harness maps every edge (D005)"],
        ["4.2", "Boundary data", "Frozen dataclasses, SI units, authority in "
         "blocks (D002, D013)"],
        ["4.3", "Contract enforcement", "Each module tests its contract; a "
         "shared CI job is open"],
        ["4.4", "Stand-ins", "Each module's test UI in its own process; "
         "harness stubs (D010, D018)"],
        ["4.5", "Ownership", "Each module owns its types; one owner per "
         "contract shard"],
        ["4.6", "Input validation", "Reject the whole tick before anything "
         "changes"],
        ["4.7", "Decision log", "The truth branch; proposals promoted by a "
         "person"],
    ], [0.7, 3.0, 8.7], section="System", size=15)


def uc_label(module: str, number: int) -> str:
    """A use case's ID as its module writes it."""
    if module == "Train Model":
        return "UC-TM-%02d" % number
    if module in ("Track Model", "Train Controller (SW and HW)"):
        return "UC %d:" % number
    return "UC-%02d" % number


def module_part(deck: CombinedDeck, chapter: dict, figs: list[dict],
                ucs: list[UseCase]) -> None:
    title, owner = chapter["title"], chapter["owner"]
    presenter = f"Presenter: {owner}. "
    deck.section(title, f"{owner} \u00b7 SDD Section {chapter['number']}")
    deck.bullets(f"{title}: what it does", OVERVIEW[title],
                 section=title)
    figs = [f for f in figs if Path(f["path"]).name not in SKIP]
    descriptions = {uc.number: uc for uc in ucs}

    for f in figs:
        if f["viewpoint"] == "Context":
            deck.figure(f, f["caption"], f"{title} \u00b7 Use cases",
                        presenter + (f["note"] or f"{len(ucs)} use cases."))
    for uc in ucs:
        summary = uc.field("description", "main success scenario")
        deck.use_case(uc, uc_label(title, uc.number),
                      f"{title} \u00b7 Use case descriptions",
                      presenter + "Use case description; skip if short on "
                      "time. " + summary)
    for f in figs:
        if f["viewpoint"] == "Composition":
            deck.figure(f, f["caption"], f"{title} \u00b7 Architecture",
                        presenter + (f["note"] or "The module's parts and "
                                     "how they depend on each other."))
    for f in figs:
        if f["viewpoint"] in ("Logical", "Interface", "State dynamics"):
            deck.figure(f, f["caption"], f"{title} \u00b7 Class diagrams",
                        presenter + (f["note"] or f["caption"] + "."))
    sds = [f for f in figs if f["viewpoint"] == "Interaction"]
    mapped = sorted((f for f in sds if uc_of(f) is not None),
                    key=lambda f: (uc_of(f), f["number"] if Path(f["path"]).name
                                   not in SD_FOR_UC else 0))
    for f in mapped + [f for f in sds if uc_of(f) is None]:
        n = uc_of(f)
        uc = descriptions.get(n) if n is not None else None
        name = f["caption"]
        if uc and not re.match(r"SD-\d+", name):
            what = re.sub(r"^Sequence diagram:\s*", "", name)
            name = f"{uc_label(title, n)} {uc.title}"
            if what.lower() not in uc.title.lower():
                name += f": {what}"
        notes = presenter + (f"Use case: {uc.title}. "
                             + uc.field("description", "main success scenario")
                             if uc else "") + (" " + f["note"] if f["note"] else "")
        deck.figure(f, name, f"{title} \u00b7 Sequence diagrams", notes.strip())


def main() -> int:
    built = build_sdd.build()
    figs = [{"number": f.number, "caption": f.caption,
             "path": build_sdd.doc_rel(f.path), "chapter": f.chapter,
             "section": f.section, "heading": f.heading, "note": f.note,
             "viewpoint": build_sdd.viewpoint(f)} for f in built.figures]
    blocks = chapters(built.text)

    deck = CombinedDeck(FOOTER)
    deck.title("Railway Simulation", "Design review: system and module design",
               "Team 3, Track Overflow \u00b7 ECE 1140 \u00b7 2026-10-22")
    deck.bullets("Agenda", [
        "The system: architecture, software architecture, interaction, "
        "deployment",
        "System-wide concepts: route, authority, wayside distribution, "
        "timing, vitality, language, HW/SW",
        "Each module: use cases, descriptions, architecture, classes, one "
        "sequence diagram per use case",
        ("CTC Office \u00b7 Track Controller SW \u00b7 Track Controller HW "
         "\u00b7 Track Model \u00b7 Train Model \u00b7 Train Controller", 1),
        "Open items",
    ], section="Overview")
    system_part(deck, [f for f in figs if f["chapter"] == "System"])
    for chapter in built.chapters:
        ucs = use_cases(blocks[chapter["title"]])
        module_part(deck, chapter,
                    [f for f in figs if f["chapter"] == chapter["title"]], ucs)
        print(f"  {chapter['title']}: {len(ucs)} use cases")

    deck.section("Open items")
    deck.table("Open items", ["Item", "Owner"], [
        ["Read-only vital PLC block; move the SW supervisor into PLC code",
         "Harry"],
        ["One PLC language with identical names in both variants", "Harry, "
         "Braden"],
        ["Red Line wayside territories (three proposed)", "Braden"],
        ["Power for a Pi 5 through the USB-C port that carries the link",
         "Braden, Jonathan, Ivan"],
        ["HW at 10x: USB round trip + scan under 10 ms", "Braden, Jonathan, "
         "Ivan"],
        ["Train Controller Protocol and typed inputs", "Jonathan, Ivan"],
        ["A shared CI job for every module's contract tests", "Team"],
        ["Fourth signal aspect: SUPER_GREEN vs SUPER GREEN", "Deni, "
         "Jonathan"],
    ], [9.4, 3.0], section="Open items", size=16)
    deck.save(OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
