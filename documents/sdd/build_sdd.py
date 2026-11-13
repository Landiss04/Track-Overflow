"""Build the combined Software Design Description.

Reads the system frame (``sdd_frame.md``), the system-wide concepts
(``system_concepts.md``) and every module's own SDD contribution, and
writes ``Railway_Sim_SDD.md`` beside this script. The module files are
read, never edited: each module chapter is a list of slices of its
owner's file, with headings renumbered, image and link paths rewritten,
system-level figures dropped (they appear once, in Section 3) and every
figure numbered once for the whole document.

The run fails when an image is missing, when one image would appear
twice, or when a slice's anchor is not found, so a change in a module
file cannot silently drop content.

Run from anywhere::

    python documents/sdd/build_sdd.py

``build()`` returns the document's structure; the slide builder uses it,
so the deck and the SDD show the same figures.
"""

from __future__ import annotations

import json
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import quote, unquote

HERE = Path(__file__).resolve().parent
DOCS = HERE.parent
REPO = DOCS.parent
OUT = HERE / "Railway_Sim_SDD.md"
MANIFEST = HERE / "sdd_figures.json"
TM_PNG = DOCS / "uml" / "train-model-uml(2)(1)-png"

# Module figures replaced by the one system figure in Section 3. They
# are left in their owners' folders; Section 6.3 lists them.
SUPERSEDED = {
    "uml/track_model/01_architecture.png": "3.1 System context (system architecture)",
    "uml/track_model/15_composition.png": "3.2 Software architecture",
    "uml/track_model/18_seq_authority.png": "3.5 Representative interaction",
    "uml/track_model/14_deployment.png": "3.6 Deployment",
    "sdd-figures/train-controller/01-system-architecture.png": "3.1 System context (system architecture)",
    "uml/ctc_office/deployment.png": "3.6 Deployment",
    "uml/track_ctrl_sw/deployment.png": "3.6 Deployment",
    "uml/train-model-uml(2)(1)-png/21_deployment.png": "3.6 Deployment",
}


@dataclass
class Part:
    """One slice of a module file, which becomes one numbered subsection.

    Attributes:
        title: The subsection's heading, or None for a prelude with no
            heading of its own.
        start: Text the slice's first line starts with.
        end: Text the line after the slice starts with; None for the
            end of the file.
        aliases: How the module file refers to this slice ("Appendix D",
            "004-interface"); replaced by the new section number.
        keep_start: Keep the start line (when it is text, not a heading).
    """

    title: str | None
    start: str
    end: str | None
    aliases: tuple[str, ...] = ()
    keep_start: bool = False


@dataclass
class Chapter:
    title: str
    owner: str
    src: str
    parts: list[Part]
    # Exact-text replacements applied to the module file before slicing.
    replace: list[tuple[str, str]] = field(default_factory=list)
    # Regex replacements applied to each line.
    line_subs: list[tuple[str, str]] = field(default_factory=list)
    # Lines matching any of these are dropped.
    drop: list[str] = field(default_factory=list)
    # Train Model placeholders: "TM-3" -> images (empty list drops it).
    placeholders: dict[str, list[str]] = field(default_factory=dict)
    # Images appended at the end of the subsection whose heading
    # starts with the key.
    append: dict[str, list[str]] = field(default_factory=dict)
    # References to places outside the chapter: text -> replacement.
    refs: dict[str, str] = field(default_factory=dict)


def tm(name: str) -> str:
    rel = str((TM_PNG / f"{name}.png").relative_to(DOCS)).replace("\\", "/")
    return quote(rel, safe="/.-_")


TEMPLATE_DROP = [
    r"^\s*-?\s*\*\*Viewpoint:\*\*",
    r"^\s*-?\s*\*\*Representation:\*\*",
]

CHAPTERS = [
    Chapter(
        "CTC Office", "Landis", "sdd/ctc_office.md",
        [
            Part(None, "| | |", "## Revision history", keep_start=True),
            Part("Scope", "## 1. Scope", "## 2. "),
            Part("Requirements coverage", "## 2. ", "## 3. "),
            Part("Use cases", "## 3. ", "## 4. "),
            Part("CTC Office architecture (component view)", "## 4. ", "## 5. ",
                 aliases=("Section 4",)),
            Part("Interface", "## 5. ", "## 6. "),
            Part("Class diagrams", "## 6. ", "## 7. "),
            Part("Sequence diagrams", "## 7. ", "## 8. "),
            Part("Open items", "## 9. ", "## Appendix A"),
        ],
    ),
    Chapter(
        "Track Controller (SW)", "Harry Tye", "sdd/track_ctrl_sw.md",
        [
            Part(None, "| | |", "## 1. ", keep_start=True),
            Part("Scope", "## 1. ", "## 2. "),
            Part("Requirements coverage", "## 2. ", "## 3. "),
            Part("Use cases", "## 3. ", "## 4. "),
            Part("Track Controller (SW) architecture (component view)", "## 4. ", "## 5. "),
            Part("Class diagrams", "## 5. ", "## 6. "),
            Part("Sequence diagrams", "## 6. ", "## 7. "),
            Part("Open items", "## 8. ", None),
        ],
    ),
    Chapter(
        "Track Controller (HW)", "Braden Bosilovich", "sdd/track_ctrl_hw.md",
        [
            Part(None, "| | |", "## 1. ", keep_start=True),
            Part("Scope", "## 1. ", "## 2. "),
            Part("Requirements coverage", "## 2. ", "## 3. "),
            Part("Use cases", "## 3. ", "## 4. "),
            Part("Track Controller (HW) architecture (component view)", "## 4. ", "## 5. "),
            Part("Class diagrams", "## 5. ", "## 6. "),
            Part("Sequence diagrams", "## 6. ", "## 7. "),
            Part("Open items", "## 8. ", None),
        ],
        refs={"Section 7": "Section 3.6"},
    ),
    Chapter(
        "Track Model", "Deni Ephraim", "sdd/track_model.md",
        [
            Part("Stakeholder concerns", "### 2.1 ", "### 2.2 "),
            Part("Use cases", "### B. ", "### C. ", aliases=("Appendix B",)),
            Part("Track Model architecture (component view)", "#### C.1 ", "#### C.2 ",
                 aliases=("Appendix C.1", "Appendix C")),
            Part("Boundary types", "### 003-logical", "### 004-interface",
                 aliases=("003-logical",)),
            Part("Class diagrams", "#### C.2 ", "#### C.3 ", aliases=("Appendix C.2",)),
            Part("Interface", "### 004-interface", "### 005-interaction",
                 aliases=("004-interface",)),
            Part("Interface dictionary", "### G. ", "### H. ", aliases=("Appendix G",)),
            Part("Data design", "#### C.3 ", "#### C.4 ", aliases=("Appendix C.3",)),
            Part("Algorithms", "#### C.4 ", "#### C.5 ", aliases=("Appendix C.4",)),
            Part("User interface", "#### C.5 ", "#### C.6 ", aliases=("Appendix C.5",)),
            Part("Test interface", "#### C.6 ", "### D. ", aliases=("Appendix C.6",)),
            Part("Sequence diagrams", "### D. ", "### E. ", aliases=("Appendix D",)),
            Part("State machine", "### E. ", "### F. ", aliases=("Appendix E",)),
            Part("Design decisions", "## 4. Decisions", "## 5. ", aliases=("Section 4",)),
            Part("Requirements traceability", "### H. ", None, aliases=("Appendix H",)),
        ],
        drop=TEMPLATE_DROP,
        refs={"Appendix A": "Section 3.7", "Appendix F": "Section 3.6",
              "Appendix A.1": "Section 3.7.1", "Appendix A.2": "Section 3.7.2",
              "Appendix A.3": "Section 3.7.3", "Appendix A.4": "Section 3.7.6",
              "Appendix A.5": "Section 3.7.4", "Appendix A.6": "Section 3.7.5",
              "Appendix A.7": "Section 3.7.7", "Section 3": "Section 3"},
    ),
    Chapter(
        "Train Model", "Kevin Schillinger", "Railway_Sim_SDD_Train_Model.md",
        [
            Part("Scope", "### 1.2 ", "### 1.3 "),
            Part("Stakeholder concerns", "### 2.1 ", "### 2.2 "),
            Part("Train Model in the system", "### 001-context", "### 002-composition"),
            Part("Use cases", "### 006-use-cases", "### 007-deployment"),
            Part("Train Model architecture (component view)", "### 002-composition",
                 "### 003-logical"),
            Part("Class diagrams", "### 003-logical", "### 004-interface"),
            Part("Interface", "### 004-interface", "### 005-interaction"),
            Part("Interaction: one simulation tick", "### 005-interaction",
                 "### 006-use-cases"),
            Part("Design decisions", "## 4. Decisions", "### 4.9 ", aliases=("section 4",)),
            Part("Review items and deferred work", "### 4.9 ", "## 5. ",
                 aliases=("section 4.9",)),
            Part("Requirements traceability", "### A. ", "### B. ", aliases=("Appendix A",)),
            Part("Verification references", "### D. ", "*End of Train Model",
                 aliases=("Appendix D",)),
        ],
        drop=TEMPLATE_DROP,
        placeholders={
            "TM-1": [],
            "TM-2": [],
            "TM-3": [tm("04_class")],
            "TM-4": [tm("05_sequence-advance-one-simulation-step"),
                     tm("11_sequence-report-state-to-train-controller"),
                     tm("14_sequence-report-position-to-track-model")],
            "TM-5": [tm("01_use-case"), tm("02_use-cases-by-role"),
                     tm("03_use-case-descriptions")],
            "TM-6": [],
        },
        append={
            "UC-TM-01": [tm("15_sequence-validate-step-inputs"),
                         tm("16_sequence-compute-train-motion"),
                         tm("17_sequence-update-passengers"),
                         tm("18_sequence-detect-block-change"),
                         tm("19_sequence-update-cabin-temperature"),
                         tm("20_sequence-publish-outputs")],
            "UC-TM-02": [tm("06_sequence-view-train-status"),
                         tm("07_sequence-view-announcement")],
            "UC-TM-03": [tm("12_sequence-apply-controller-commands")],
            "UC-TM-04": [tm("13_sequence-receive-track-data")],
            "UC-TM-05": [tm("09_sequence-board-and-disembark-passengers")],
            "UC-TM-06": [tm("08_sequence-pull-passenger-emergency-brake")],
            "UC-TM-07": [tm("10_sequence-inject-clear-failure")],
        },
        refs={"Appendix C": "Section 6.1", "Appendix B": "Section 6.2"},
    ),
    Chapter(
        "Train Controller (SW and HW)", "Jonathan Tsang, Ivan Zheng",
        "Railway_Sim_SDD_Train_Controller.md",
        [
            Part("Scope", "One module and one code base", "### 1.3 ", keep_start=True),
            Part("Stakeholder concerns", "### 2.1 ", "### 2.2 "),
            Part("Train Controller in the system", "  In the simulation the harness maps",
                 "### 002-composition", keep_start=True, aliases=("001-context",)),
            Part("Use cases", "### Appendix E", None, aliases=("Appendix E",)),
            Part("Train Controller architecture (component view)",
                 "  **Train Controller** internal parts", "### 003-logical",
                 keep_start=True, aliases=("002-composition",)),
            Part("Class diagrams", "### 003-logical", "### 004-interface",
                 aliases=("003-logical",)),
            Part("Interface", "### 004-interface", "### 005-interaction",
                 aliases=("004-interface", "004-\ninterface")),
            Part("Interaction: one tick", "### 005-interaction", "## 4. Decisions",
                 aliases=("005-interaction",)),
            Part("Speed law and safety path", "### Appendix A", "### Appendix B",
                 aliases=("Appendix A",)),
            Part("Failure inference", "### Appendix B", "### Appendix C",
                 aliases=("Appendix B",)),
            Part("Automatic behaviour", "### Appendix C", "### Appendix D",
                 aliases=("Appendix C",)),
            Part("Design decisions", "## 4. Decisions", "### 4.9 ",
                 aliases=("§4.1", "§4.4", "§4.6")),
            Part("Open items", "### 4.9 ", "## 5. ", aliases=("§4.9",)),
        ],
        replace=[
            ("**Train Controller:** one module and one code base",
             "One module and one code base"),
            ("  **Train Controller** — the controller's part. Steps before the\n"
             "  Track Model are the CTC Office's and Track Controller's, to be\n"
             "  detailed in their blocks at the merge.",
             "  The controller's part. The whole chain, from the CTC Office to the\n"
             "  train, is the representative interaction in Section 3.5."),
            ("Each decision below is system-wide. **[TEAM]** marks the outcome the\n"
             "team records at the merge; the **Train Controller** lines give this\n"
             "module's facts so the outcome can be written without asking us.",
             "The module's position on each system decision of Section 4."),
            ("The module's part in the system architecture topics; the system-wide\n"
             "text is the team's.", ""),
        ],
        line_subs=[
            (r"\*\*\[TEAM\]\*\*\s*", ""),
            (r"^(\s*)\*\*Train Controller\*\*:?\s*(—\s*)?", r"\1"),
            (r"\*\*Train Controller:\*\*\s*", ""),
            (r"^(- \*\*ID:\*\*) D-00(\d) —\s*$", r"\1 system decision 4.\2"),
            (r"^(- \*\*Outcome:\*\*)\s*$", r"\1 as recorded for the system in Section 4."),
        ],
        drop=TEMPLATE_DROP,
        refs={"Appendix D": "Section 3.7"},
    ),
]

IMAGE = re.compile(r"!\[([^\]]*)\]\(([^)\s]+)\)")
LINK = re.compile(r"(?<!!)\[([^\]]*)\]\(([^)\s#]+)(#[^)\s]*)?\)")
HEADING = re.compile(r"^(#{1,6})\s+(.*)$")
OLD_NUMBER = re.compile(
    r"^(?:Appendix [A-H]\s*[—-]\s*|[A-H](?:\.\d+)*\.?\s+|\d+(?:\.\d+)*\.?\s+"
    r"|\d{3}-[a-z-]+\s*[—-]\s*)")
FIG_LABEL = re.compile(r"^Figure (TM-\d+|\d+)\.\s*")
PLACEHOLDER_CAPTION = re.compile(r"^\*\*Figure (TM-\d+)\.\s*(.*?)\*\*\s*$")


class BuildError(Exception):
    pass


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig").replace("\r\n", "\n")


def doc_rel(path: Path) -> str:
    """Path relative to documents/, with forward slashes."""
    return str(path.resolve().relative_to(DOCS)).replace("\\", "/")


def out_link(path: Path) -> str:
    """Path from the output file to ``path``, URL-quoted for Markdown."""
    text = os.path.relpath(path.resolve(), HERE).replace("\\", "/")
    return quote(text, safe="/.-_")


def slice_lines(lines: list[str], part: Part, src: str) -> list[str]:
    try:
        i = next(n for n, l in enumerate(lines) if l.startswith(part.start))
    except StopIteration:
        raise BuildError(f"{src}: start anchor not found: {part.start!r}")
    if part.end is None:
        j = len(lines)
    else:
        try:
            j = next(n for n in range(i + 1, len(lines)) if lines[n].startswith(part.end))
        except StopIteration:
            raise BuildError(f"{src}: end anchor not found after {part.start!r}: {part.end!r}")
    body = lines[i:j] if part.keep_start else lines[i + 1:j]
    return [l for l in body if l.strip() != "---"]


def drop_lines(lines: list[str], patterns: list[str]) -> list[str]:
    """Drop matching lines, and the rest of a wrapped label paragraph."""
    out: list[str] = []
    dropping = False
    for l in lines:
        if any(re.search(p, l) for p in patterns):
            dropping = True
            continue
        if dropping and l.strip() and not re.match(r"\s*([#|!>*-]|\d+\.)", l):
            continue
        dropping = False
        out.append(l)
    return out


def shift_headings(lines: list[str], target: int) -> list[str]:
    levels = [len(m.group(1)) for l in lines if (m := HEADING.match(l))]
    if not levels:
        return lines
    delta = target - min(levels)
    out = []
    for l in lines:
        m = HEADING.match(l)
        if m:
            text = OLD_NUMBER.sub("", m.group(2))
            level = min(6, len(m.group(1)) + delta)
            out.append("#" * level + " " + text)
        else:
            out.append(l)
    return out


def alt_for(path: str) -> str:
    stem = Path(unquote(path)).stem
    stem = re.sub(r"^\d+_", "", stem)
    if stem.startswith("sequence-"):
        return "Sequence diagram: " + stem[len("sequence-"):].replace("-", " ")
    names = {"use-case": "Use case diagram", "use-cases-by-role": "Use cases by role",
             "use-case-descriptions": "Use case descriptions", "class": "Class diagram"}
    return names.get(stem, stem.replace("-", " "))


def expand_placeholders(lines: list[str], chapter: Chapter) -> list[str]:
    out: list[str] = []
    i = 0
    while i < len(lines):
        m = PLACEHOLDER_CAPTION.match(lines[i].strip())
        if m and m.group(1) in chapter.placeholders:
            label, caption = m.group(1), m.group(2).rstrip(".")
            j = i + 1
            while j < len(lines) and not lines[j].strip():
                j += 1
            while j < len(lines) and lines[j].lstrip().startswith(">"):
                j += 1
            for n, img in enumerate(chapter.placeholders[label]):
                alt = f"Figure {label}. {caption}" if n == 0 else alt_for(img)
                out += [f"![{alt}]({img})", ""]
            i = j
            continue
        out.append(lines[i])
        i += 1
    return out


def append_images(lines: list[str], chapter: Chapter) -> list[str]:
    for key, imgs in chapter.append.items():
        idx = next((n for n, l in enumerate(lines)
                    if (m := HEADING.match(l)) and m.group(2).startswith(key)), None)
        if idx is None:
            raise BuildError(f"{chapter.src}: no heading starting {key!r} to append to")
        level = len(HEADING.match(lines[idx]).group(1))
        end = next((n for n in range(idx + 1, len(lines))
                    if (m := HEADING.match(lines[n])) and len(m.group(1)) <= level), len(lines))
        block = [""] + [x for img in imgs for x in (f"![{alt_for(img)}]({img})", "")]
        lines = lines[:end] + block + lines[end:]
    return lines


@dataclass
class Figure:
    number: int
    caption: str
    path: Path
    chapter: str
    section: str
    section_title: str
    owner: str
    heading: str = ""
    note: str = ""


@dataclass
class Built:
    text: str
    figures: list[Figure]
    chapters: list[dict]


GENERIC = {"use case diagram", "software architecture", "deployment", "class diagram",
           "use cases by role", "use case descriptions", "boundary types"}

SYSTEM_VIEWPOINTS = {"001-context": "Context", "002-composition": "Composition",
                     "005-interaction": "Interaction", "006-deployment": "Deployment"}


def viewpoint(fig: Figure) -> str:
    c, s = fig.caption.lower(), fig.section_title.lower()
    for key, name in SYSTEM_VIEWPOINTS.items():
        if s.startswith(key):
            return name
    if "sequence" in c or c.startswith("sd-") or "interaction" in s or "sequence" in s:
        return "Interaction"
    if "use case" in c or "use cases" in c or s == "use cases":
        return "Context"
    if "state" in c and "machine" in c or "state machine" in s:
        return "State dynamics"
    if "architecture" in c or "component" in c or "architecture" in s:
        return "Composition"
    if "deployment" in c:
        return "Deployment"
    if "protocol" in c or s.startswith("interface"):
        return "Interface"
    return "Logical"


def plain(text: str) -> str:
    """Markdown inline markup removed, for slide text and notes."""
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", text)
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    text = re.sub(r"(?<![\w*])\*([^*]+)\*(?![\w*])", r"\1", text)
    text = text.replace("`", "").replace("<br>", "\n")
    return re.sub(r"[ \t]+", " ", text).strip()


def note_after(lines: list[str], i: int) -> str:
    """The paragraph that explains the image at ``lines[i]``, if any."""
    j = i + 1
    while j < len(lines) and (not lines[j].strip() or IMAGE.search(lines[j])):
        j += 1
    para = []
    while j < len(lines) and lines[j].strip():
        s = lines[j].strip()
        if s.startswith(("|", "#", "![")):
            break
        para.append(s)
        j += 1
    text = plain(" ".join(para))
    if len(text) < 40 or text.endswith(":"):
        return ""
    return text if len(text) <= 900 else text[:897].rsplit(" ", 1)[0] + "..."


def process_images(lines: list[str], src_dir: Path, figures: list[Figure],
                   used: dict[Path, str], where: str, chapter: str, owner: str,
                   section: str, section_title: str, errors: list[str],
                   uc_titles: dict[str, str] | None = None) -> list[str]:
    """Rewrite image lines: new path, global number, caption below."""
    out: list[str] = []
    old_labels: dict[str, int] = {}
    heading = section_title
    for i, l in enumerate(lines):
        hm = HEADING.match(l)
        if hm:
            heading = hm.group(2)
        m = IMAGE.search(l)
        if not m:
            out.append(l)
            continue
        alt, target = m.group(1), m.group(2)
        path = (src_dir / unquote(target)).resolve()
        key = doc_rel(path) if path.is_relative_to(DOCS) else str(path)
        if key in SUPERSEDED:
            continue
        if not path.exists():
            errors.append(f"{where}: missing image {target}")
            continue
        if path in used:
            errors.append(f"{where}: {key} already used in {used[path]}")
            continue
        used[path] = where
        lm = FIG_LABEL.match(alt)
        caption = FIG_LABEL.sub("", alt).strip().rstrip(".")
        if re.fullmatch(r"SD-\d+", caption) and not heading.startswith("SD-"):
            num = caption[3:]
            if uc_titles and num in uc_titles:
                caption = f"{caption} {uc_titles[num]} (UC-{num})"
        if re.fullmatch(r"SD-\d+", caption) or not caption:
            caption = heading
        if caption.lower() == "software architecture" and chapter != "System":
            caption = f"{chapter} architecture (component view)"
        caption = re.sub(r"software architecture \(component diagram\)",
                         "architecture (component view)", caption, flags=re.I)
        if caption.lower() in GENERIC and chapter != "System":
            caption = f"{chapter}: {caption[0].lower()}{caption[1:]}"
        n = len(figures) + 1
        if lm:
            old_labels[lm.group(1)] = n
        figures.append(Figure(n, caption, path, chapter, section, section_title, owner,
                              heading, note_after(lines, i)))
        indent = re.match(r"\s*", l).group(0)
        out += [f"{indent}![{caption}]({out_link(path)})", "",
                f"{indent}*Figure {n}. {caption}*"]
    # Later references to the module's own figure numbers.
    if old_labels:
        def renumber(m: re.Match) -> str:
            return f"Figure {old_labels[m.group(1)]}" if m.group(1) in old_labels else m.group(0)
        out = [l if l.lstrip().startswith(("![", "*Figure")) else
               re.sub(r"\bFigure (TM-\d+|\d+)\b", renumber, l) for l in out]
    return out


def rewrite_links(lines: list[str], src_dir: Path, where: str, errors: list[str]) -> list[str]:
    def fix(m: re.Match) -> str:
        text, target, anchor = m.group(1), m.group(2), m.group(3) or ""
        if re.match(r"^[a-z]+:", target):
            return m.group(0)
        path = (src_dir / unquote(target)).resolve()
        if not path.exists():
            errors.append(f"{where}: broken link {target}")
            return m.group(0)
        return f"[{text}]({out_link(path)}{anchor})"
    return [LINK.sub(fix, l) for l in lines]


def apply_refs(lines: list[str], refs: dict[str, str]) -> list[str]:
    if not refs:
        return lines
    keys = sorted(refs, key=len, reverse=True)
    pattern = re.compile(r"(?<![\w.§])(" + "|".join(re.escape(k) for k in keys) + r")(?![\w])"
                         r"(?!\.\d)")
    out = []
    for l in lines:
        if HEADING.match(l) or l.lstrip().startswith(("![", "*Figure")):
            out.append(l)
        else:
            out.append(pattern.sub(lambda m: refs[m.group(1)], l))
    return out


def build_chapter(number: str, chapter: Chapter, figures: list[Figure],
                  used: dict[Path, str], errors: list[str]) -> tuple[list[str], dict]:
    src = DOCS / chapter.src
    text = read(src)
    for old, new in chapter.replace:
        if old not in text:
            errors.append(f"{chapter.src}: replacement text not found: {old[:50]!r}")
        text = text.replace(old, new)
    lines = text.split("\n")
    uc_titles = {m.group(1): m.group(2).strip() for l in lines
                 if (m := re.match(r"^#+\s+UC-(\d+)\s+(.*)$", l))}
    rel_src = out_link(src)
    out = [f"### {number} {chapter.title}", "",
           f"**Owner:** {chapter.owner}. **Source:** [{doc_rel(src)}]({rel_src}).", ""]
    info = {"number": number, "title": chapter.title, "owner": chapter.owner,
            "src": doc_rel(src), "parts": []}

    # Number the parts first, so aliases can point at them.
    refs = dict(chapter.refs)
    numbered: list[tuple[str | None, Part]] = []
    k = 0
    for part in chapter.parts:
        if part.title is None:
            numbered.append((None, part))
            continue
        k += 1
        pnum = f"{number}.{k}"
        numbered.append((pnum, part))
        for alias in part.aliases:
            refs[alias] = f"Section {pnum}"

    for pnum, part in numbered:
        body = drop_lines(slice_lines(lines, part, chapter.src), chapter.drop)
        for pat, rep in chapter.line_subs:
            body = [re.sub(pat, rep, l) for l in body]
        body = [l for l in body if l.strip() != "-"]
        body = expand_placeholders(body, chapter)
        body = shift_headings(body, 5)
        body = append_images(body, chapter) if any(
            (m := HEADING.match(l)) and any(m.group(2).startswith(k) for k in chapter.append)
            for l in body) else body
        where = f"{number} {chapter.title} / {part.title or 'preamble'}"
        body = process_images(body, src.parent, figures, used, where, chapter.title,
                              chapter.owner, pnum or number, part.title or chapter.title,
                              errors, uc_titles)
        body = rewrite_links(body, src.parent, where, errors)
        body = apply_refs(body, refs)
        while body and not body[0].strip():
            body.pop(0)
        while body and not body[-1].strip():
            body.pop()
        if pnum:
            out += [f"#### {pnum} {part.title}", ""]
            info["parts"].append({"number": pnum, "title": part.title})
        out += body + [""]
    return out, info


def build_concepts() -> list[str]:
    lines = read(HERE / "system_concepts.md").split("\n")
    body = [l for l in lines[1:] if l.strip() != "---"]
    # Drop the file's own intro paragraph; the frame introduces it.
    first = next(n for n, l in enumerate(body) if l.startswith("## "))
    intro = ["### 3.7 Key System-Wide Design Concepts", "",
             "The concepts every module's design rests on: route, authority, the "
             "distribution of wayside controllers, simulation timing, vitality, the "
             "wayside language and the hardware/software interface. Each states the "
             "design and the decision behind it; a module's own detail is in its "
             "chapter.", ""]
    out = []
    k = 0
    for l in body[first:]:
        m = HEADING.match(l)
        if m and len(m.group(1)) == 2:
            k += 1
            out.append(f"#### 3.7.{k} " + OLD_NUMBER.sub("", m.group(2)))
        elif m:
            out.append("#####" + " " + m.group(2))
        else:
            out.append(l)
    return intro + out


def slug(text: str) -> str:
    text = text.strip().lower()
    text = re.sub(r"[^\w\- ]", "", text)
    return text.replace(" ", "-")


def toc(lines: list[str]) -> list[str]:
    out = ["## Table of Contents", ""]
    seen: dict[str, int] = {}
    for l in lines:
        m = HEADING.match(l)
        if not m or len(m.group(1)) not in (2, 3, 4):
            continue
        title = m.group(2)
        if title in ("Table of Contents",) or title.startswith("For the Railway"):
            continue
        s = slug(title)
        if s in seen:
            seen[s] += 1
            s = f"{s}-{seen[s]}"
        else:
            seen[s] = 0
        indent = "  " * (len(m.group(1)) - 2)
        out.append(f"{indent}- [{title}](#{s})")
    return out + [""]


def appendixes(figures: list[Figure], chapters: list[dict]) -> list[str]:
    out = ["## 6. Appendixes", "", "### 6.1 Figure Register", "",
           "Every figure in this document, once. The owner keeps its source beside it.", "",
           "| Figure | Caption | Section | Viewpoint | Owner | Source file |",
           "|--------|---------|---------|-----------|-------|-------------|"]
    for f in figures:
        cap = f.caption.replace("|", "\\|")
        out.append(f"| {f.number} | {cap} | {f.section} | {viewpoint(f)} | {f.owner} | "
                   f"`{doc_rel(f.path)}` |")
    out += ["", "### 6.2 Requirements Traceability Index", "",
            "Each module traces its requirements in its own chapter.", "",
            "| Module | Traceability |", "|--------|--------------|"]
    for c in chapters:
        hits = [p for p in c["parts"]
                if p["title"] in ("Requirements coverage", "Requirements traceability")]
        where = ", ".join(f"Section {p['number']}" for p in hits) or (
            "No table in the module's contribution; its rules M0 to M20 are traced in "
            "`Train-Ctrl_HW/REQUIREMENTS.md`")
        out.append(f"| {c['title']} | {where} |")
    out += ["", "### 6.3 Module Figures Replaced by System Figures", "",
            "These module figures showed the whole system. Each system concept is drawn once, "
            "in Section 3, so these are not reproduced; they stay in their owners' folders.", "",
            "| Module figure | Replaced by |", "|---------------|-------------|"]
    for path, by in SUPERSEDED.items():
        out.append(f"| `{path}` | {by} |")
    return out + [""]


def build() -> Built:
    errors: list[str] = []
    figures: list[Figure] = []
    used: dict[Path, str] = {}
    frame = read(HERE / "sdd_frame.md").split("\n")

    # System figures first, in the frame's order, so they are numbered first.
    pre, _, rest = "\n".join(frame).partition("<!-- MODULES -->")
    pre_lines = pre.split("\n")
    concepts_at = pre_lines.index("<!-- CONCEPTS -->")
    pre_lines[concepts_at:concepts_at + 1] = build_concepts()
    section_title, section = "", ""
    sys_lines: list[str] = []
    for l in pre_lines:
        m = HEADING.match(l)
        if m and len(m.group(1)) == 3:
            section_title = OLD_NUMBER.sub("", m.group(2))
            section = m.group(2).split(" ")[0]
        sys_lines += process_images([l], HERE, figures, used, f"frame {section}", "System",
                                    "Team (system figures: Braden Bosilovich; system "
                                    "architecture: Ivan Zheng)", section, section_title,
                                    errors)
    for f in figures:
        if f.path.name == "system_architecture.png":
            f.owner = "Ivan Zheng"
        else:
            f.owner = "Braden Bosilovich"

    mod_lines = ["## 5. Module Designs", "",
                 "One chapter per module, from its owner's contribution. Each has the "
                 "module's use cases, its architecture (component view), class diagrams, "
                 "interface and one sequence diagram per use case. System figures are in "
                 "Section 3 and are not repeated here.", ""]
    chapter_info = []
    for n, chapter in enumerate(CHAPTERS, 1):
        lines, info = build_chapter(f"5.{n}", chapter, figures, used, errors)
        mod_lines += lines
        chapter_info.append(info)

    after = rest.split("\n")
    at = after.index("<!-- APPENDIXES -->")
    after[at:at + 1] = appendixes(figures, chapter_info)

    body = sys_lines + mod_lines + after
    at = body.index("<!-- TOC -->")
    body[at:at + 1] = toc(body)
    text = re.sub(r"\n{3,}", "\n\n", "\n".join(body)).rstrip() + "\n"
    if errors:
        raise BuildError("\n".join(errors))
    return Built(text, figures, chapter_info)


def main() -> int:
    try:
        built = build()
    except BuildError as e:
        print("SDD build failed:\n" + str(e), file=sys.stderr)
        return 1
    OUT.write_text(built.text, encoding="utf-8", newline="\n")
    MANIFEST.write_text(json.dumps(
        {"chapters": built.chapters,
         "figures": [{"number": f.number, "caption": f.caption, "path": doc_rel(f.path),
                      "chapter": f.chapter, "section": f.section,
                      "section_title": f.section_title, "owner": f.owner,
                      "heading": f.heading, "note": f.note,
                      "viewpoint": viewpoint(f)} for f in built.figures]},
        indent=1, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    print(f"Wrote {OUT.relative_to(REPO)}: {len(built.text.splitlines())} lines, "
          f"{len(built.figures)} figures, {len(built.chapters)} module chapters")
    return 0


if __name__ == "__main__":
    sys.exit(main())
