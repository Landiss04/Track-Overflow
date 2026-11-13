"""Build the design review template deck and its Deck class.

The combined design review deck is build_combined_deck.py, which uses
the Deck class from here.

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
SPLIT = {"sd01_load_database": 2, "sd02_load_program": 2}


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
        # Leave room for the section label, and shrink a long title to fit.
        title_w = SLIDE_W - 2 * MARGIN - (Inches(4.0) if section else 0)
        size = max(18, min(28, int(title_w / Inches(1) / (0.0075 * max(
            1, len(title))))))
        self._text(slide, MARGIN, Inches(0.12), title_w,
                   Inches(0.75), title, size=size, color=WHITE, bold=True,
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
        "Use case descriptions, Architecture, Class diagrams, Sequence "
        "diagrams; system architecture, deployment and concepts are drawn "
        "once, for the system",
        "Diagrams: PlantUML with documents/uml/style.iuml, rendered to "
        "PNG at 150 dpi",
        ("Designed-but-not-built elements are orange and marked "
         "\u00abplanned\u00bb", 1),
        "Requirement IDs as in the SRS (REQ-FUNC-049); rubric items as "
        "6.0 to 6.9",
        "Use case descriptions on their own slides, in one block after the "
        "use case diagram, so a presenter can skip past them",
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


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    build_template()
