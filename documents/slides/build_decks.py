"""Build the design review decks: the shared template and the Track Ctrl HW deck.

Run from the repository root:  python documents/slides/build_decks.py
Needs python-pptx and Pillow. Diagrams are read from documents/uml/.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from PIL import Image
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Emu, Inches, Pt

ROOT = Path(__file__).resolve().parents[2]
UML = ROOT / "documents" / "uml" / "track_ctrl_hw"
OUT = ROOT / "documents" / "slides"

NAVY = RGBColor(0x1F, 0x3A, 0x5F)
INK = RGBColor(0x22, 0x2B, 0x36)
MUTED = RGBColor(0x5B, 0x67, 0x75)
LIGHT = RGBColor(0xD9, 0xE2, 0xEC)
PAPER = RGBColor(0xF7, 0xF9, 0xFC)
PLANNED = RGBColor(0xC2, 0x6A, 0x00)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
FONT = "Segoe UI"
MONO = "Consolas"

SLIDE_W = Inches(13.333)
SLIDE_H = Inches(7.5)
MARGIN = Inches(0.45)
TITLE_H = Inches(0.95)
FOOTER_H = Inches(0.35)
# Sequence diagrams too detailed to read on one slide.
SPLIT = {"sd05_tick": 2, "sd01_load_database": 2, "sd02_load_program": 2}


class Deck:
    """A 16:9 deck in the team style: navy title bar, white body, footer."""

    def __init__(self, footer: str) -> None:
        self.prs = Presentation()
        self.prs.slide_width = SLIDE_W
        self.prs.slide_height = SLIDE_H
        self.blank = self.prs.slide_layouts[6]
        self.footer = footer
        self.number = 0
        self._scratch = Path(tempfile.mkdtemp(prefix="deck_"))

    # -- building blocks -------------------------------------------------

    def _text(self, slide, left, top, width, height, text, size=18,
              color=INK, bold=False, font=FONT, align=PP_ALIGN.LEFT,
              anchor=MSO_ANCHOR.TOP):
        box = slide.shapes.add_textbox(left, top, width, height)
        frame = box.text_frame
        frame.word_wrap = True
        frame.vertical_anchor = anchor
        frame.margin_left = frame.margin_right = Inches(0.05)
        lines = text if isinstance(text, list) else [text]
        for i, line in enumerate(lines):
            para = frame.paragraphs[0] if i == 0 else frame.add_paragraph()
            para.alignment = align
            run = para.add_run()
            run.text = line
            run.font.size = Pt(size)
            run.font.color.rgb = color
            run.font.bold = bold
            run.font.name = font
        return box

    def _chrome(self, title: str, section: str = "", footer: bool = True):
        self.number += 1
        slide = self.prs.slides.add_slide(self.blank)
        bar = slide.shapes.add_shape(
            MSO_SHAPE.RECTANGLE, 0, 0, SLIDE_W, TITLE_H)
        bar.fill.solid()
        bar.fill.fore_color.rgb = NAVY
        bar.line.fill.background()
        self._text(slide, MARGIN, Inches(0.12), SLIDE_W - 2 * MARGIN,
                   Inches(0.75), title, size=28, color=WHITE, bold=True,
                   anchor=MSO_ANCHOR.MIDDLE)
        if section:
            self._text(slide, SLIDE_W - Inches(4.2), Inches(0.12),
                       Inches(3.8), Inches(0.75), section, size=12,
                       color=LIGHT, align=PP_ALIGN.RIGHT,
                       anchor=MSO_ANCHOR.MIDDLE)
        if footer:
            self._text(slide, MARGIN, SLIDE_H - FOOTER_H, Inches(9),
                       FOOTER_H, self.footer, size=10, color=MUTED)
        self._text(slide, SLIDE_W - Inches(1.5), SLIDE_H - FOOTER_H,
                   Inches(1.05), FOOTER_H, str(self.number), size=10,
                   color=MUTED, align=PP_ALIGN.RIGHT)
        return slide

    def _body_box(self):
        top = TITLE_H + Inches(0.25)
        return (MARGIN, top, SLIDE_W - 2 * MARGIN,
                SLIDE_H - top - FOOTER_H - Inches(0.1))

    # -- slide types -----------------------------------------------------

    def title(self, title: str, subtitle: str, byline: str):
        self.number += 1
        slide = self.prs.slides.add_slide(self.blank)
        bg = slide.shapes.add_shape(
            MSO_SHAPE.RECTANGLE, 0, 0, SLIDE_W, SLIDE_H)
        bg.fill.solid()
        bg.fill.fore_color.rgb = NAVY
        bg.line.fill.background()
        self._text(slide, Inches(0.9), Inches(2.3), Inches(11.5),
                   Inches(1.2), title, size=44, color=WHITE, bold=True)
        self._text(slide, Inches(0.9), Inches(3.5), Inches(11.5),
                   Inches(0.8), subtitle, size=24, color=LIGHT)
        self._text(slide, Inches(0.9), Inches(5.6), Inches(11.5),
                   Inches(0.6), byline, size=16, color=LIGHT)
        return slide

    def section(self, title: str, subtitle: str = ""):
        self.number += 1
        slide = self.prs.slides.add_slide(self.blank)
        bg = slide.shapes.add_shape(
            MSO_SHAPE.RECTANGLE, 0, 0, SLIDE_W, SLIDE_H)
        bg.fill.solid()
        bg.fill.fore_color.rgb = PAPER
        bg.line.fill.background()
        rule = slide.shapes.add_shape(
            MSO_SHAPE.RECTANGLE, Inches(0.9), Inches(3.55), Inches(1.4),
            Inches(0.08))
        rule.fill.solid()
        rule.fill.fore_color.rgb = NAVY
        rule.line.fill.background()
        self._text(slide, Inches(0.9), Inches(2.4), Inches(11.5),
                   Inches(1.1), title, size=40, color=NAVY, bold=True)
        if subtitle:
            self._text(slide, Inches(0.9), Inches(3.8), Inches(11.5),
                       Inches(1.0), subtitle, size=20, color=MUTED)
        return slide

    def bullets(self, title: str, items: list, section: str = "",
                size: int = 24):
        """``items``: strings, or (text, level) tuples for sub-points."""
        slide = self._chrome(title, section)
        left, top, width, height = self._body_box()
        box = slide.shapes.add_textbox(left, top, width, height)
        frame = box.text_frame
        frame.word_wrap = True
        for i, item in enumerate(items):
            text, level = item if isinstance(item, tuple) else (item, 0)
            para = frame.paragraphs[0] if i == 0 else frame.add_paragraph()
            para.space_after = Pt(8 if level == 0 else 4)
            run = para.add_run()
            run.text = ("\u2022  " if level == 0 else "\u2013  ") + text
            run.font.size = Pt(size if level == 0 else size - 3)
            run.font.color.rgb = INK if level == 0 else MUTED
            run.font.name = FONT
            para.level = level
        return slide

    def diagram(self, title: str, image: Path, section: str = "",
                caption: str = "", crop: tuple | None = None,
                full: bool = False, blank: tuple = (), notes: str = "",
                parts: int | None = None):
        """One diagram, fitted; a tall one is split across slides.

        ``crop`` keeps a region given as (left, top, right, bottom)
        fractions; ``blank`` whites out regions given the same way, to
        hide fragments of neighbouring boxes. ``full`` fills the slide
        below the title bar, with no footer or caption. ``parts`` forces
        the number of slides instead of choosing it from the shape.
        """
        if crop is not None:
            with Image.open(image) as picture:
                w, h = picture.size
                picture = picture.convert("RGB")
                for region in blank:
                    picture.paste((255, 255, 255), (
                        int(region[0] * w), int(region[1] * h),
                        int(region[2] * w), int(region[3] * h)))
                box = (int(crop[0] * w), int(crop[1] * h),
                       int(crop[2] * w), int(crop[3] * h))
                path = self._scratch / (
                    f"{image.stem}_{'_'.join(map(str, box))}.png")
                picture.crop(box).save(path)
            image = path
        with Image.open(image) as picture:
            w_px, h_px = picture.size
        parts = parts or max(1, round(h_px / w_px / 0.9))
        if parts == 1:
            return self._picture(title, image, section, caption, full, notes)
        for index, piece in enumerate(self._slices(image, parts), start=1):
            self._picture(f"{title} ({index} of {parts})", piece, section,
                          caption if index == parts else "", full, notes)

    def _slices(self, image: Path, parts: int) -> list[Path]:
        # Cut where a row holds the least ink, so no message is split.
        with Image.open(image) as picture:
            grey = picture.convert("L")
            w, h = grey.size
            pixels = grey.load()

            def ink(y: int) -> int:
                return sum(1 for x in range(0, w, 2) if pixels[x, y] < 200)

            cuts = [0]
            for k in range(1, parts):
                target = h * k // parts
                window = range(target - h // 8, target + h // 8)
                cuts.append(min(window, key=lambda y: (ink(y),
                                                       abs(y - target))))
            cuts.append(h)
            pieces = []
            for k in range(parts):
                path = self._scratch / f"{image.stem}_{k + 1}.png"
                picture.crop((0, cuts[k], w, cuts[k + 1])).save(path)
                pieces.append(path)
        return pieces

    def _picture(self, title: str, image: Path, section: str,
                 caption: str, full: bool = False, notes: str = ""):
        slide = self._chrome(title, section, footer=not full)
        if notes:
            slide.notes_slide.notes_text_frame.text = notes
        left, width = MARGIN, SLIDE_W - 2 * MARGIN
        if full:
            top, caption = TITLE_H, ""
            height = SLIDE_H - top - Inches(0.12)
        else:
            top = TITLE_H + Inches(0.12)
            height = SLIDE_H - top - FOOTER_H - Inches(0.1)
        if caption:
            height -= Inches(0.45)
        with Image.open(image) as picture:
            w_px, h_px = picture.size
        scale = min(width / w_px, height / h_px)
        w, h = int(w_px * scale), int(h_px * scale)
        slide.shapes.add_picture(
            str(image), left + (width - w) // 2, top + (height - h) // 2,
            Emu(w), Emu(h))
        if caption:
            self._text(slide, left, top + height + Inches(0.05), width,
                       Inches(0.4), caption, size=13, color=MUTED,
                       align=PP_ALIGN.CENTER)
        return slide

    def table(self, title: str, header: list[str], rows: list[list[str]],
              widths: list[float], section: str = "", size: int = 16):
        slide = self._chrome(title, section)
        left, top, width, _ = self._body_box()
        shape = slide.shapes.add_table(
            len(rows) + 1, len(header), left, top, width,
            Inches(0.4) * (len(rows) + 1))
        table = shape.table
        for col, inches in enumerate(widths):
            table.columns[col].width = Inches(inches)
        for col, text in enumerate(header):
            self._cell(table.cell(0, col), text, size, WHITE, True, NAVY)
        for r, row in enumerate(rows, start=1):
            fill = PAPER if r % 2 else WHITE
            for col, text in enumerate(row):
                self._cell(table.cell(r, col), text, size, INK, False, fill)
        return slide

    def _cell(self, cell, text, size, color, bold, fill):
        cell.fill.solid()
        cell.fill.fore_color.rgb = fill
        cell.margin_left = cell.margin_right = Inches(0.08)
        cell.margin_top = cell.margin_bottom = Inches(0.04)
        frame = cell.text_frame
        frame.word_wrap = True
        para = frame.paragraphs[0]
        run = para.add_run()
        run.text = text
        run.font.size = Pt(size)
        run.font.color.rgb = color
        run.font.bold = bold
        run.font.name = FONT

    def code(self, title: str, code: str, notes: list[str],
             section: str = ""):
        slide = self._chrome(title, section)
        left, top, width, height = self._body_box()
        code_w = int(width * 0.56)
        panel = slide.shapes.add_shape(
            MSO_SHAPE.RECTANGLE, left, top, code_w, height)
        panel.fill.solid()
        panel.fill.fore_color.rgb = PAPER
        panel.line.color.rgb = LIGHT
        self._text(slide, left + Inches(0.15), top + Inches(0.1),
                   code_w - Inches(0.3), height - Inches(0.2),
                   code.splitlines(), size=17, font=MONO)
        note_left = left + code_w + Inches(0.3)
        box = slide.shapes.add_textbox(
            note_left, top, width - code_w - Inches(0.3), height)
        frame = box.text_frame
        frame.word_wrap = True
        for i, note in enumerate(notes):
            para = frame.paragraphs[0] if i == 0 else frame.add_paragraph()
            para.space_after = Pt(8)
            run = para.add_run()
            run.text = "\u2022  " + note
            run.font.size = Pt(19)
            run.font.color.rgb = INK
            run.font.name = FONT
        return slide

    def save(self, path: Path) -> None:
        self.prs.save(str(path))
        print("saved", path.relative_to(ROOT), f"({self.number} slides)")


def build_template() -> None:
    deck = Deck("Track Overflow \u00b7 Design Review \u00b7 <your module>")
    deck.title("<Module name>", "Design review", "<Name> \u00b7 Track Overflow "
               "\u00b7 2026-10-22")
    deck.section("Style guide for these slides",
                 "Copy this deck, or call build_decks.py's Deck class, so the "
                 "decks combine cleanly.")
    deck.bullets("How to keep the decks consistent", [
        "16:9, Segoe UI; navy title bar, white body, footer with module "
        "and slide number",
        "One idea per slide; a diagram slide holds one diagram, centred, "
        "with an optional one-line caption",
        "Section dividers in this order: Overview, Use cases, "
        "Architecture, Class diagrams, Sequence diagrams, Deployment, "
        "System concepts, Open items",
        "Diagrams: PlantUML with documents/uml/style.iuml, rendered to "
        "PNG at 150 dpi",
        ("Designed-but-not-built elements are orange and marked "
         "\u00abplanned\u00bb", 1),
        "Requirement IDs as in the SRS (REQ-FUNC-049); rubric items as "
        "6.0 to 6.9",
        "No use case descriptions on slides (the professor asked us to "
        "leave them out)",
    ], section="Template")
    deck.table("Table slide", ["Column", "Column", "Column"], [
        ["Navy header row", "Alternate row shading", "16 pt text"],
        ["Keep tables under 12 rows", "Split longer ones", ""],
    ], [4.1, 4.1, 4.1], section="Template")
    deck.code("Code slide", "VAR_IN  OCC_1..20\nVAR_OUT AUTH_1..20\n"
              "AUTH_2 := NOT (OCC_1 OR OCC_3)",
              ["Monospace on a light panel", "Notes on the right"],
              section="Template")
    deck.diagram("Diagram slide", UML / "uc_track_ctrl_hw.png",
                 section="Template", caption="Optional one-line caption")
    deck.save(OUT / "design_review_template.pptx")


def build_track_ctrl_hw() -> None:
    deck = Deck("Track Overflow \u00b7 Design Review \u00b7 Track Controller "
                "(HW) \u00b7 Braden")
    deck.title("Track Controller (HW)", "Design review",
               "Braden \u00b7 Track Overflow \u00b7 2026-10-22")

    deck.section("Overview")
    deck.bullets("What the hardware Track Controller does", [
        "Runs every wayside controller of the Red Line (Green: software "
        "variant)",
        "Each wayside: its own territory database and its own Boolean PLC "
        "program",
        "Knows blocks, never trains: everything it exchanges is keyed by "
        "block",
        ("A failure (broken rail, circuit, power) reaches it as an occupied "
         "block", 1),
        "Core on a Raspberry Pi 5; window on the PC; linked by one USB "
        "cable",
        "Stepped once per tick by the central harness, like every module",
        ("Orange \u00abplanned\u00bb = designed, not built yet: the PC/Pi "
         "split and the vital block", 1),
    ], section="Overview")
    deck.table("Requirements coverage", ["Rubric", "Requirement", "SRS",
                                         "Use cases"], [
        ["6.0", "Receive suggested speed and authority from the CTC",
         "FUNC-049", "UC-08, UC-14"],
        ["6.1", "Move switches by PLC execution", "FUNC-052",
         "UC-07, UC-11"],
        ["6.2", "Set traffic lights by PLC execution", "FUNC-053",
         "UC-07, UC-12"],
        ["6.3", "Receive train presence from the Track Model", "FUNC-054",
         "UC-10"],
        ["6.4", "Send track occupancy to the CTC", "FUNC-055",
         "UC-15, UC-06"],
        ["6.5", "Railway crossing lights and gates", "FUNC-056", "UC-13"],
        ["6.6", "PLC language based only on Boolean variables", "FUNC-051",
         "UC-02, UC-07"],
        ["6.7", "Load PLC file", "FUNC-050", "UC-02"],
        ["6.8", "Maintenance mode: set a switch position", "FUNC-057",
         "UC-09, UC-11"],
        ["6.9", "Safety-critical architecture", "FUNC-058", "UC-07, UC-16"],
        ["9.0", "Sub-system user interface", "INTF-001.4", "UC-01 to UC-06"],
    ], [1.0, 6.2, 1.8, 3.4], section="Overview", size=15)

    deck.section("Use cases")
    deck.diagram("Use case diagram", UML / "uc_track_ctrl_hw.png",
                 section="Use cases",
                 caption="Programmer actions are every control of the "
                 "window; the scan cycle runs once per tick",
                 notes="16 use cases. UC-01 to UC-06 are every control of "
                 "the window (Programmer). UC-07 Run scan cycle runs once per "
                 "tick, driven by the harness, and includes UC-08 to UC-15: "
                 "inputs from the CTC Office and Track Model, commands to the "
                 "Track Model, the report to the CTC. UC-16 Hold fail-safe "
                 "extends the scan. Together they cover rubric 6.0 to 6.9 and "
                 "9.0.")

    deck.section("Architecture")
    deck.diagram("Software architecture", UML / "architecture.png",
                 section="Architecture",
                 notes="Layers: presentation and host-side communication on "
                 "the PC; control, PLC engine and Pi-side communication on "
                 "the Pi; the contract (interface, wire format, errors) is "
                 "shared by both. Orange = planned: the PC/Pi split.")
    deck.diagram("Software architecture: host PC", UML / "architecture.png",
                 section="Architecture", crop=(0, 0, 0.405, 0.59),
                 blank=((0.336, 0.42, 1, 1),),
                 notes="PC side. The QML window talks only to "
                 "TrackControllerState. Harness ticks and window requests "
                 "both go through RemoteTrackController, which forwards them "
                 "over USB serial through PiSerialLink.")
    deck.diagram("Software architecture: Raspberry Pi and shared code",
                 UML / "architecture.png", section="Architecture",
                 crop=(0.336, 0.42, 1, 1),
                 notes="Pi side. PiLinkServer receives each request and calls "
                 "HwTrackController, which scans every Wayside. Each "
                 "statement is compiled twice and run on two channels; the "
                 "vital block runs after the user's program (planned). "
                 "interface.py and wire.py are used on both sides.")
    deck.bullets("Architecture: design choices", [
        "One interface, three users: harness, window and test UI call only "
        "the TrackController Protocol",
        ("step, snapshot, load_territory, load_program, reset", 1),
        "RemoteTrackController implements the same Protocol on the PC and "
        "forwards each call to the Pi",
        ("The window and the harness endpoint do not change when the core "
         "moves", 1),
        "Core is Qt-free: runs on the Pi in plain Python; 74 unit tests run "
        "headless",
        "Validate, then change: a bad tick is rejected before any state "
        "changes",
        "Two channels: every statement compiled twice, by different "
        "algorithms, run every scan",
    ], section="Architecture")

    deck.section("Class diagrams")
    deck.diagram("Core classes (Raspberry Pi): control",
                 UML / "class_core_control.png", section="Class diagrams",
                 notes="HwTrackController implements the TrackController "
                 "Protocol and owns one Wayside per database, all on one "
                 "line. Wayside.scan builds the input image, runs the "
                 "programs, compares the channels, drives the outputs and "
                 "builds the CTC report. Every error derives from "
                 "TrackControllerError. PiLinkServer is planned.")
    deck.diagram("Core classes (Raspberry Pi): PLC engine",
                 UML / "class_core_plc.png", section="Class diagrams",
                 notes="compile_program turns source into an immutable "
                 "Program. Each Statement holds a tree (channel A) and "
                 "postfix code (channel B); scan_a and scan_b must agree. "
                 "check_program verifies every name against the wayside's "
                 "I/O. vital_source (planned) generates the read-only block.")
    deck.diagram("Boundary types: inputs and outputs",
                 UML / "class_boundary_io.png", section="Class diagrams",
                 full=True,
                 notes="What crosses the boundary each tick. In: from the "
                 "CTC Office closures, maintenance switch commands and "
                 "per-block suggestions; from the Track Model occupancy and "
                 "read-back. Out: track circuits and switch, signal and "
                 "crossing commands to the Track Model; one CtcReport per "
                 "wayside. The CTC keys blocks by BlockRef, the Track Model "
                 "by BlockKey.")
    deck.diagram("Boundary types: territory",
                 UML / "class_boundary_territory.png",
                 section="Class diagrams", full=True,
                 notes="A wayside's territory, from its database: blocks "
                 "with length and speed limit, switches (point, normal and "
                 "reverse ends), crossings. BlockKey is line, section, "
                 "number; BlockRef is line and number, the CTC's form "
                 "(Red:15).")
    deck.diagram("Boundary types: snapshot for the window",
                 UML / "class_boundary_snapshot.png",
                 section="Class diagrams", full=True,
                 notes="Read-only state for the window, from snapshot(), "
                 "with no side effects: per wayside its program, scan "
                 "health (scans, overruns, channel agreement), switch states "
                 "and last report.")
    deck.diagram("Host-side classes (PC): presentation",
                 UML / "class_host_ui.png", section="Class diagrams",
                 caption="QML only binds to TrackControllerState and calls "
                 "its slots; rows update in place every 100 ms at most",
                 notes="TrackControllerState is the QML bridge: slots for "
                 "the window's actions, properties QML binds to. It turns "
                 "snapshots into rows through views, display and schematic, "
                 "and updates five RowsModels in place, at most every 100 ms.")
    deck.diagram("Host-side classes (PC): link to the Pi",
                 UML / "class_host_link.png", section="Class diagrams",
                 caption="RemoteTrackController has the same Protocol as "
                 "HwTrackController; each call is one request over USB",
                 notes="Planned. RemoteTrackController implements the same "
                 "Protocol as HwTrackController, so neither the window nor "
                 "the harness endpoint changes. PiSerialLink sends each call "
                 "as one newline-JSON request over USB serial (D027); "
                 "HarnessEndpoint answers the harness's ticks.")

    deck.section("Sequence diagrams")
    for name, title, notes in (
        ("sd05_tick", "SD-05 One tick through the central harness",
         "One tick: the harness maps the CTC Office's and Track Model's "
         "previous outputs into this module's inputs; the PC relays the step "
         "to the Pi; every wayside scans; the outputs go back. An invalid "
         "input rejects the whole tick. At 10x, USB round trip plus scan "
         "must stay under 10 ms."),
        ("sd06_scan_cycle", "SD-06 Scan cycle of one wayside",
         "One wayside's scan. It holds fail-safe if any wayside is not ready, "
         "it has no program, or a channel fault is latched. Otherwise: build "
         "the input image, run the user program on channels A and B, "
         "compare, run the vital block the same way (planned), then drive "
         "the outputs. The CTC report is built every scan."),
        ("sd01_load_database", "SD-01 Load wayside database",
         "The PC parses the file and rejects a bad one before sending it; "
         "the Pi checks the line and that no other wayside owns its blocks. "
         "A replaced wayside keeps its program if the program still fits."),
        ("sd02_load_program", "SD-02 Load PLC program",
         "Compiled twice and checked against the wayside's I/O, on the Pi. "
         "Any error refuses the program and lists every problem with its "
         "line number; the old program keeps running. A new program holds "
         "fail-safe until its first scan."),
        ("sd03_monitor", "SD-03 Select wayside and monitor",
         "The window takes a snapshot, converts it to rows in display units "
         "and updates the tables in place. A 100 ms timer refreshes when "
         "ticks have advanced. Zoom and Fit are QML only."),
        ("sd04_details_and_report", "SD-04 PLC details and last report",
         "Two read-only dialogs over values from the last refresh. New PLC "
         "in the details dialog starts SD-02."),
        ("sd07_maintenance_switch", "SD-07 Maintenance switch command",
         "The CTC Office's command reaches the program as the CTCSW and "
         "CTCREV inputs; the program obeys unless a train holds the switch. "
         "The Track Model's read-back goes into the CTC report. When "
         "maintenance ends, the program routes the switch again."),
    ):
        deck.diagram(title, UML / f"{name}.png", section="Sequence diagrams",
                     notes=notes, parts=SPLIT.get(name))

    deck.section("Deployment")
    deck.diagram("Deployment", UML / "deployment.png", section="Deployment",
                 notes="One Windows PC runs the executable; the harness "
                 "spawns one process per module. The Track Ctrl HW process "
                 "shows the window and owns the COM port to a Raspberry Pi 5 "
                 "in USB device mode, which runs every Red Line wayside. The "
                 "test UI is not deployed. Open item: powering the Pi 5.")

    deck.section("System concepts", "Track Controller's part of the joint "
                 "concepts, with Harry and Landis")
    deck.bullets("Distribution of wayside controllers", [
        "One variant per line: HW runs the Red Line, SW the Green Line "
        "(D021)",
        "A wayside owns a contiguous run of blocks and every switch, signal "
        "and crossing on them",
        "One Raspberry Pi 5 runs every Red Line wayside",
        "A line runs only when every wayside on it is ready",
        ("Ready: a person has loaded the database and the PLC program, and "
         "the channels agree", 1),
        ("Not ready anywhere on the line: the whole line holds fail-safe "
         "and the CTC dispatches nothing", 1),
        "Red Line boundaries: to be chosen; a switch must lie inside one "
        "wayside",
    ], section="System concepts")
    deck.bullets("Authority, as the wayside handles it", [
        "Authority = blocks ahead the train may still enter; 0 = stop (D013)",
        "CTC Office computes it along the route and suggests it per block",
        "The program's AUTH_n passes the CTC count down block n's track "
        "circuit, or sends 0",
        ("Withheld for a closed block, a switch not where commanded, an "
         "occupied neighbour", 1),
        "Speed travels with it as five bits, capped at the block's limit",
        "Track Model delivers both to the train in the block, then clears "
        "them",
    ], section="System concepts")
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
         "Speed crosses in and out as five bits (SPD_n_0..4, CMD_n_0..4)",
         "Every error reported with its line number; a program naming I/O "
         "its wayside lacks is refused",
         "Shared with the SW variant; the names still differ"],
        section="System concepts")
    deck.bullets("Vitality", [
        "The OS only holds and parses the PLC program: every decision is "
        "PLC code",
        "Read-only vital block after the user's program \u00abplanned\u00bb",
        ("Generated per territory; can only make outputs more restrictive", 1),
        "Diverse execution: two compilers, two interpreters, compared every "
        "scan",
        "Diverse implementations: HW and SW share a language, not code",
        "Fail-safe outputs: signals red, crossings active, speed and "
        "authority 0, switches stay",
        "Inputs checked whole before anything changes; a failure reads as "
        "occupancy",
    ], section="System concepts")
    deck.bullets("Hardware/software interface", [
        "Same TrackController Protocol and the same I/O in both variants "
        "(D021)",
        "Pi 5 in USB device mode: a standard USB serial (CDC-ACM) device "
        "(D027)",
        ("Windows' built-in driver: no installation, no admin rights", 1),
        ("Found by its USB identity, never a fixed COM number", 1),
        "Messages: the harness's newline JSON, with request ID and tick",
        "The PC process owns the COM port and relays harness messages to "
        "the Pi",
        "10x: 100 ticks per second, so USB round trip + scan < 10 ms",
    ], section="System concepts")

    deck.section("Open items")
    deck.table("Open items", ["#", "Item", "Owner"], [
        ["1", "Read-only vital PLC block: assumed, to confirm for both "
         "variants", "Braden, Harry"],
        ["2", "Manual switch at the wayside in maintenance (rubric 6.8); "
         "assumed CTC only", "Braden, Harry"],
        ["3", "Red Line wayside boundaries, databases and programs",
         "Braden"],
        ["4", "USB message framing; the Pi's identification", "Kevin, Braden"],
        ["5", "Pi 5 power through its USB-C port", "Braden, Kevin"],
        ["6", "Measure USB round trip + scan against the 10 ms budget",
         "Braden"],
        ["7", "PLC names differ between the variants (REQ-INTF-009)",
         "Braden, Harry"],
        ["8", "Aspect values: lower case here, upper case system-wide",
         "Braden"],
    ], [0.6, 9.2, 2.6], section="Open items", size=16)
    deck.save(OUT / "design_review_track_ctrl_hw.pptx")


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    build_template()
    build_track_ctrl_hw()
