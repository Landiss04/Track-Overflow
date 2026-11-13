"""Layout of the wayside territory schematic.

The schematic is drawn in two kinds of unit. Along the track, positions
are in block columns: block ``i`` of a row spans columns ``i`` to
``i + 1``, and the view stretches columns to zoom. Across the track,
everything is in fixed pixels, so symbols and labels keep their size at
any zoom and never shrink below the 12 px text floor.

Blocks are laid out in database order on one row. A block where a
switch's reverse leg arrives starts a new row when the block before it
in the file is not that switch's point: that is a branch, such as the
second leg of a Y, and it is drawn below, starting beside the switch.
Every other reverse leg is drawn as a loop over the track, when it
ends at a block of this wayside, or as a short labelled stub, when it
leaves the wayside or leads to the yard.
"""

from __future__ import annotations

from typing import Any

from track_ctrl_hw.interface import Territory
from track_ctrl_hw.territory import YARD

#: Fixed vertical layout, in pixels. The track runs at ``TOP`` on the
#: first row; each further row is ``ROW_HEIGHT`` lower.
TOP = 84
ROW_HEIGHT = 176
BOTTOM = 96


def layout(territory: Territory) -> dict[str, Any]:
    """Schematic geometry for one territory, ready for QML."""
    keys = territory.keys
    number_index = {key.block_id: i for i, key in enumerate(keys)}
    switch_by_reverse_end = {
        switch.reverse_end: switch
        for switch in territory.switches
        if switch.reverse_end in number_index
    }

    rows: list[list[int]] = []
    row_start: list[float] = []
    place: dict[int, tuple[int, float]] = {}
    for index, key in enumerate(keys):
        switch = switch_by_reverse_end.get(key.block_id)
        branch = (
            index > 0
            and switch is not None
            and keys[index - 1].block_id != switch.point
            and number_index[switch.point] in place
        )
        if index == 0 or branch:
            start = 0.0
            if branch and switch is not None:
                # Leave one column for the leg to run diagonally down
                # from the points to the branch.
                point_row, point_col = place[number_index[switch.point]]
                start = point_col + 2
            rows.append([])
            row_start.append(start)
        row = len(rows) - 1
        place[index] = (row, row_start[row] + len(rows[row]))
        rows[row].append(index)

    blocks = [
        {
            "number": key.block_id,
            "label": key.label,
            "row": place[i][0],
            "col": place[i][1],
        }
        for i, key in enumerate(keys)
    ]
    row_spans = [
        {
            "row": r,
            "first": place[members[0]][1],
            "last": place[members[-1]][1] + 1,
        }
        for r, members in enumerate(rows)
    ]

    switches = []
    loops = 0
    for switch in territory.switches:
        point_row, point_col = place[number_index[switch.point]]
        normal = number_index.get(switch.normal_end)
        # The points sit at the end of the point block that faces the
        # normal leg.
        if normal is not None and place[normal][0] == point_row:
            normal_col = place[normal][1]
            joint = max(point_col, normal_col)
            away = 1 if normal_col > point_col else -1
        else:
            joint = point_col + 1
            away = 1
        listed_row, listed_col = place[number_index[switch.switch_id]]
        reverse: dict[str, Any]
        far = number_index.get(switch.reverse_end)
        if far is not None and place[far][0] != point_row:
            far_row, far_col = place[far]
            reverse = {"kind": "branch", "row": far_row, "col": far_col}
        elif far is not None:
            far_row, far_col = place[far]
            span = row_spans[far_row]
            if far_col == span["first"]:
                end_col = far_col
            elif far_col + 1 == span["last"]:
                end_col = far_col + 1
            else:
                end_col = far_col + 0.5
            reverse = {"kind": "loop", "col": end_col, "level": loops}
            loops += 1
        else:
            target = (
                "YARD" if switch.reverse_end == YARD
                else switch.reverse_end
            )
            reverse = {"kind": "stub", "direction": away,
                       "label": f"TO {target}"}
        switches.append({
            "number": switch.switch_id,
            "row": point_row,
            "joint": joint,
            "signalRow": listed_row,
            "signalCol": listed_col + 0.5,
            "reverse": reverse,
            "normalEnd": switch.normal_end,
            "reverseEnd": switch.reverse_end,
        })

    crossings = [
        {
            "number": key.block_id,
            "row": place[number_index[key.block_id]][0],
            "col": place[number_index[key.block_id]][1] + 0.5,
        }
        for key in territory.crossings
    ]
    columns = max(span["last"] for span in row_spans)
    return {
        "columns": columns,
        "rowCount": len(rows),
        "top": TOP,
        "rowHeight": ROW_HEIGHT,
        "height": TOP + (len(rows) - 1) * ROW_HEIGHT + BOTTOM,
        "rows": row_spans,
        "blocks": blocks,
        "switches": switches,
        "crossings": crossings,
    }
