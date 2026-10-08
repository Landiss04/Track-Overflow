"""Drawing geometry for the CTC track map.

Each lettered section of each line is a polyline traced from the course
Red & Green Line diagram, in an 850 x 930 drawing frame. A section holds
several blocks from the layout files (``ctc.track_layout``), so each
section's polyline is cut into one segment per block, in file order, in
proportion to the blocks' lengths. Every block is then its own drawable
segment, so per-block state (occupancy, closures) can be shown later.

The geometry is presentation only: it says where a block is drawn, not
how blocks connect. Connectivity comes from the layout files.
"""

from __future__ import annotations

import math
from typing import Any

from PySide6.QtCore import Property, QObject, Slot

from ctc.track_layout import Block, Line, load_layout
from ctc_ui.display import M_TO_FT, MPS_TO_MPH

_KMH_PER_MPS = 3.6

Point = tuple[float, float]

MAP_WIDTH = 850
MAP_HEIGHT = 930

#: Section polylines per line, traced from the course diagram. Each runs
#: from the section's first block to its last, in file order.
SECTION_PATHS: dict[str, dict[str, list[Point]]] = {
    "Green": {
        "A": [(392, 18), (415, 38), (440, 62), (462, 90)],
        "B": [(462, 90), (490, 106), (520, 115), (553, 118)],
        "C": [(553, 118), (600, 113), (632, 98), (645, 78), (630, 55),
              (590, 38), (530, 26), (460, 19), (392, 18)],
        "D": [(392, 18), (285, 18)],
        "E": [(285, 18), (240, 24), (208, 40), (194, 62), (190, 95)],
        "F": [(190, 95), (190, 237)],
        "G": [(190, 237), (192, 300)],
        "H": [(192, 300), (200, 330), (222, 355), (262, 368)],
        "I": [(262, 368), (612, 368)],
        "J": [(612, 368), (670, 374), (715, 395), (748, 430), (765, 480)],
        "K": [(765, 480), (767, 712)],
        "L": [(767, 712), (760, 760), (735, 800), (700, 830), (660, 852)],
        "M": [(660, 852), (452, 852)],
        "N": [(452, 852), (270, 852)],
        "O": [(270, 852), (160, 852)],
        "P": [(160, 852), (128, 830), (115, 790), (118, 745), (138, 720),
              (165, 715), (190, 728), (205, 755), (208, 785)],
        "Q": [(208, 785), (225, 825), (250, 845), (270, 852)],
        "R": [(452, 852), (475, 825), (497, 797)],
        "S": [(497, 797), (595, 797)],
        "T": [(595, 797), (650, 792), (690, 775), (712, 740), (718, 700)],
        "U": [(718, 700), (718, 530)],
        "V": [(718, 530), (712, 480), (690, 445), (650, 425), (570, 415)],
        "W": [(570, 415), (222, 415)],
        "X": [(222, 415), (180, 408), (155, 390), (148, 365)],
        "Y": [(148, 365), (148, 290)],
        "Z": [(148, 290), (168, 262), (190, 237)],
    },
    "Red": {
        "A": [(545, 232), (575, 222), (605, 205), (630, 180)],
        "B": [(630, 180), (640, 155), (665, 138), (690, 134)],
        "C": [(690, 134), (735, 128), (775, 145), (795, 168), (800, 190)],
        "D": [(800, 190), (780, 212), (740, 228), (670, 232)],
        "E": [(670, 232), (545, 232)],
        "F": [(545, 232), (470, 232)],
        "G": [(470, 232), (432, 236), (410, 252), (402, 285)],
        "H": [(402, 285), (402, 590)],
        "I": [(402, 590), (395, 630), (370, 660), (335, 676), (300, 678)],
        "J": [(300, 678), (155, 676)],
        "K": [(155, 676), (110, 660), (80, 625), (70, 570)],
        "L": [(70, 570), (85, 520), (105, 500), (125, 498)],
        "M": [(125, 498), (145, 520), (162, 570), (175, 630)],
        "N": [(175, 630), (195, 660), (220, 673), (250, 677)],
        "O": [(402, 558), (372, 555), (352, 545)],
        "P": [(352, 545), (352, 492)],
        "Q": [(352, 492), (372, 483), (402, 478)],
        "R": [(402, 400), (372, 392), (350, 382)],
        "S": [(350, 382), (350, 335)],
        "T": [(350, 335), (372, 323), (402, 318)],
    },
}

#: Yard connections, drawn as plain track (no blocks).
YARD_RECT = (718.0, 282.0, 84.0, 40.0)   # x, y, width, height
YARD_SPURS: dict[str, list[list[Point]]] = {
    "Green": [
        [(612, 368), (680, 360), (718, 345), (735, 322)],   # I end to yard
        [(762, 322), (765, 480)],                           # yard to K
    ],
    "Red": [
        [(800, 190), (790, 240), (775, 282)],               # C/D to yard
    ],
}

#: Where each section letter sits, traced from the course diagram so
#: the map reads like it.
LABEL_POSITIONS: dict[str, dict[str, Point]] = {
    "Green": {
        "A": (430, 65), "B": (495, 128), "C": (655, 57), "D": (338, 42),
        "E": (238, 57), "F": (218, 170), "G": (210, 268), "H": (222, 333),
        "I": (545, 353), "J": (730, 392), "K": (788, 588), "L": (760, 800),
        "M": (565, 868), "N": (348, 868), "O": (210, 868), "P": (128, 775),
        "Q": (240, 800), "R": (458, 818), "S": (536, 782), "T": (655, 760),
        "U": (703, 620), "V": (658, 458), "W": (530, 432), "X": (155, 410),
        "Y": (133, 332), "Z": (155, 258),
    },
    "Red": {
        "A": (588, 188), "B": (658, 160), "C": (755, 160), "D": (755, 235),
        "E": (600, 248), "F": (513, 248), "G": (440, 258), "H": (420, 513),
        "I": (348, 645), "J": (245, 692), "K": (97, 622), "L": (97, 537),
        "M": (180, 548), "N": (209, 653), "O": (366, 575), "P": (338, 522),
        "Q": (365, 470), "R": (380, 385), "S": (336, 357), "T": (370, 310),
    },
}


def _length(points: list[Point]) -> float:
    return sum(math.dist(a, b) for a, b in zip(points, points[1:]))


def _point_at(points: list[Point], distance: float) -> tuple[Point, int]:
    """Point ``distance`` along the polyline, and its segment index."""
    for index, (a, b) in enumerate(zip(points, points[1:])):
        step = math.dist(a, b)
        if distance <= step or index == len(points) - 2:
            t = 0.0 if step == 0 else min(distance / step, 1.0)
            return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t), index
        distance -= step
    return points[-1], len(points) - 2


def place_on_block(piece: list[Point],
                   fraction: float) -> tuple[float, float, float]:
    """Point ``fraction`` of the way along a block's piece, and the
    track's heading there in degrees.

    The heading is kept within (-90, 90] so a drawn train never renders
    upside down; it says which way the track runs, not which way the
    train travels.
    """
    fraction = min(max(fraction, 0.0), 1.0)
    (x, y), index = _point_at(piece, _length(piece) * fraction)
    (ax, ay), (bx, by) = piece[index], piece[index + 1]
    angle = math.degrees(math.atan2(by - ay, bx - ax))
    if angle > 90:
        angle -= 180
    elif angle <= -90:
        angle += 180
    return round(x, 1), round(y, 1), round(angle, 1)


def _distance_to_segment(p: Point, a: Point, b: Point) -> float:
    (ax, ay), (bx, by) = a, b
    dx, dy = bx - ax, by - ay
    span = dx * dx + dy * dy
    t = 0.0 if span == 0 else max(0.0, min(1.0, (
        (p[0] - ax) * dx + (p[1] - ay) * dy) / span))
    return math.dist(p, (ax + t * dx, ay + t * dy))


def distance_to_piece(point: Point, piece: list[Point]) -> float:
    """Shortest distance from a point to a block's drawn piece."""
    return min(_distance_to_segment(point, a, b)
               for a, b in zip(piece, piece[1:]))


def split_polyline(points: list[Point],
                   weights: list[float]) -> list[list[Point]]:
    """Cut a polyline into consecutive pieces sized by ``weights``."""
    total = _length(points)
    weight_sum = sum(weights) or 1.0
    pieces: list[list[Point]] = []
    start, start_index = points[0], 0
    walked = 0.0
    for weight in weights:
        walked += total * weight / weight_sum
        end, end_index = _point_at(points, walked)
        piece = [start, *points[start_index + 1:end_index + 1], end]
        pieces.append(piece)
        start, start_index = end, end_index
    return pieces


def _flat(points: list[Point]) -> list[float]:
    return [round(c, 1) for point in points for c in point]


def build_map(layout: dict[str, Line]) -> dict[str, list[dict[str, Any]]]:
    """Drawable blocks, labels and markers for every line."""
    blocks: list[dict[str, Any]] = []
    labels: list[dict[str, Any]] = []
    stations: list[dict[str, Any]] = []
    crossings: list[dict[str, Any]] = []
    for line_name, line in layout.items():
        paths = SECTION_PATHS[line_name]
        for letter, section_blocks in line.sections().items():
            path = paths[letter]
            pieces = split_polyline(
                path, [block.length_m for block in section_blocks])
            for block, piece in zip(section_blocks, pieces):
                blocks.append(_block_entry(block, piece))
                middle, _ = _point_at(piece, _length(piece) / 2)
                if block.station is not None:
                    stations.append({"line": line_name, "x": middle[0],
                                     "y": middle[1],
                                     "name": block.station})
                if block.railway_crossing:
                    crossings.append({"line": line_name,
                                      "blockId": block.block_id,
                                      "x": middle[0], "y": middle[1]})
            x, y = LABEL_POSITIONS[line_name][letter]
            labels.append({"line": line_name, "text": letter,
                           "x": x, "y": y})
    spurs = [{"line": line_name, "points": _flat(spur)}
             for line_name, line_spurs in YARD_SPURS.items()
             for spur in line_spurs]
    return {"blocks": blocks, "labels": labels, "stations": stations,
            "crossings": crossings, "spurs": spurs}


def _block_entry(block: Block, piece: list[Point]) -> dict[str, Any]:
    """A block to draw, with where to label it and what it is.

    ``mid`` and ``normal`` (a unit vector to the left of the drawing
    direction there) place its number beside the track; ``tick`` (x, y,
    degrees) marks where it starts. Speed limit and length are in
    display units (mph, ft): this is the UI edge.
    """
    (mx, my), index = _point_at(piece, _length(piece) / 2)
    (ax, ay), (bx, by) = piece[index], piece[index + 1]
    span = math.hypot(bx - ax, by - ay) or 1.0
    (sx, sy), (tx, ty) = piece[0], piece[1]
    return {
        "line": block.line,
        "blockId": block.block_id,
        "section": block.section,
        "points": _flat(piece),
        "mid": [round(mx, 1), round(my, 1)],
        # Drawn length in map units, to skip numbering blocks too short
        # on screen to label.
        "drawnLength": round(_length(piece), 1),
        "normal": [round((ay - by) / span, 3), round((bx - ax) / span, 3)],
        "tick": [round(sx, 1), round(sy, 1),
                 round(math.degrees(math.atan2(ty - sy, tx - sx)), 1)],
        "speedLimitMph": round(block.speed_limit_kmh / _KMH_PER_MPS
                               * MPS_TO_MPH),
        "lengthFt": round(block.length_m * M_TO_FT),
        # None: no station; "": a station the file leaves unnamed.
        "station": block.station,
    }


class TrackMapModel(QObject):
    """The track map as constant properties for ``TrackMap.qml``."""

    def __init__(self, layout: dict[str, Line] | None = None,
                 parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._map = build_map(load_layout() if layout is None else layout)
        # Every block's entry by "Line:block". QML asks for the few it
        # needs through blockInfo and blocksIn: looping over ``blocks`` in
        # QML re-reads the whole list on every element, which is slow.
        self._by_key = {f"{b['line']}:{b['blockId']}": b
                        for b in self._map["blocks"]}
        # Each block's drawn piece, for placing trains on it.
        self._pieces = {
            (b["line"], b["blockId"]): list(zip(b["points"][::2],
                                                b["points"][1::2]))
            for b in self._map["blocks"]}

    @Slot(list, result=list)
    def placeTrains(self, trains: list[dict[str, Any]]  # noqa: N802
                    ) -> list[dict[str, Any]]:
        """Where to draw each train: ``{train, line, block, fraction}``
        in, ``{train, line, x, y, angle}`` out. Trains on a block the
        map does not draw are left out."""
        placed = []
        for train in trains:
            piece = self._pieces.get((train["line"], train["block"]))
            if piece is None:
                continue
            x, y, angle = place_on_block(piece, float(train["fraction"]))
            placed.append({"train": train["train"], "line": train["line"],
                           "block": train["block"],
                           "x": x, "y": y, "angle": angle})
        return placed

    @Slot(str, result="QVariantMap")
    def blockInfo(self, key: str) -> dict[str, Any]:  # noqa: N802
        """One block's entry by ``Line:block``; empty if there is none."""
        return self._by_key.get(key, {})

    @Slot(list, result=list)
    def blocksIn(self, keys: list[str]) -> list[dict[str, Any]]:  # noqa
        """The entries of the blocks named by ``Line:block`` keys, in map
        order."""
        wanted = set(keys)
        return [entry for key, entry in self._by_key.items()
                if key in wanted]

    @Slot(float, float, float, int, result="QVariantMap")
    def blockAt(self, x: float, y: float,  # noqa: N802
                tolerance: float, line_filter: int) -> dict[str, Any]:
        """The drawn block nearest a map point, within ``tolerance`` map
        units: ``{line, blockId}``, or empty if none is that close.
        ``line_filter`` is the map's: 0 both lines, 1 Red, 2 Green."""
        shown = {0: ("Green", "Red"), 1: ("Red",), 2: ("Green",)}.get(
            line_filter, ("Green", "Red"))
        best: tuple[float, str, str] | None = None
        for (line, block_id), piece in self._pieces.items():
            if line not in shown:
                continue
            distance = distance_to_piece((x, y), piece)
            if distance <= tolerance and (best is None
                                          or distance < best[0]):
                best = (distance, line, block_id)
        return {} if best is None else {"line": best[1],
                                        "blockId": best[2]}

    @Property(list, constant=True)
    def blocks(self) -> list[dict[str, Any]]:
        return self._map["blocks"]

    @Property(list, constant=True)
    def labels(self) -> list[dict[str, Any]]:
        return self._map["labels"]

    @Property(list, constant=True)
    def stations(self) -> list[dict[str, Any]]:
        return self._map["stations"]

    @Property(list, constant=True)
    def crossings(self) -> list[dict[str, Any]]:
        return self._map["crossings"]

    @Property(list, constant=True)
    def spurs(self) -> list[dict[str, Any]]:
        return self._map["spurs"]

    @Property(list, constant=True)
    def yard(self) -> list[float]:
        return list(YARD_RECT)

    @Property(int, constant=True)
    def mapWidth(self) -> int:  # noqa: N802
        return MAP_WIDTH

    @Property(int, constant=True)
    def mapHeight(self) -> int:  # noqa: N802
        return MAP_HEIGHT
