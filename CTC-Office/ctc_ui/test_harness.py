"""Test harness state for the CTC Office test UI.

The harness stands in for the Track Controller, so the CTC Office can be
run on its own. Its inputs are only what the Track Controller sends the
CTC: whether it is ready, occupied blocks, switch states and crossing
states. Everything the
CTC itself decides (dispatch orders, block closures, switch commands,
the operating mode and the clock speed) is done in the CTC window, as a
dispatcher would. The harness reaches the module only through its
boundary, over a link (``ctc/link.py``): each Send builds ``CtcInputs``
from the rows and hands them over. Connected to the CTC window, the
window's clock steps the module with them every tick; standalone, Send
steps one fixed tick. The outputs table shows only the module's
``CtcOutputs``.

Rows are dicts for the test UI. Scalar rows are ``{name, kind, value,
unit}`` for ``SignalRow``. A list row (blocks, switches, crossings) has
``kind`` ``"list"``, a ``fields`` schema and its ``entries``, one dict
per entry keyed by field. Lines, blocks, switches and crossings are
picked from the track layout, so every reference names a real place;
block numbers repeat across lines, so each entry picks its line first.
Values are shown in display units (mph) and converted from backend SI
units at this layer, per ``truth/conventions/units.md``.

The Track Controller reports only which blocks are occupied: a train and
a failed block look the same, and the module works out which is which
from how occupancy changes over time (``ctc.tracking``). So trains are
moved here by changing occupied blocks while the CTC window's clock
runs; standalone, each Send is only 0.1 s, too soon for any train.
"""

from __future__ import annotations

from typing import Any, Mapping

from PySide6.QtCore import Property, QObject, Signal, Slot

from ctc.interface import (
    BlockOccupancy,
    CrossingReport,
    CtcInputs,
    CtcOutputs,
    SwitchReport,
    TrackControllerInputs,
)
from ctc.link import CtcLink, LocalLink
from ctc.model import CtcError
from ctc.track_layout import Line, load_layout
from ctc_ui.display import MPS_TO_MPH, block_key

__all__ = ["CtcTestHarness", "HarnessInputError", "MPS_TO_MPH",
           "build_inputs", "output_rows"]

Entry = dict[str, Any]

#: Input rows, all from the Track Controller: (kind, default, unit).
INPUT_DEFAULTS: dict[str, tuple[str, Any, str]] = {
    # Off, as at startup: the CTC sends nothing until it is on.
    "ready": ("bool", False, ""),
    "occupied_blocks": ("list", (), ""),
    "switch_states": ("list", (), ""),
    "crossing_states": ("list", (), ""),
}

#: Rows that also pick one of a few choices, shown as a dropdown in the
#: same row. None does at the moment.
INPUT_CHOICES: dict[str, tuple[str, ...]] = {}

#: Field types whose options come from the track layout, per line.
_LAYOUT_TYPES = ("block", "switch", "crossing")


def _field(key: str, label: str, kind: str, width: int,
           options: tuple[tuple[str, str], ...] = ()) -> dict[str, Any]:
    """One column of a list row.

    ``kind`` is ``line``, ``block``, ``switch``, ``crossing`` (picked
    from the layout), ``choice`` (picked from ``options``, value and
    text pairs), ``text`` or ``number``.
    """
    return {"key": key, "label": label, "kind": kind, "width": width,
            "options": [{"value": v, "text": t} for v, t in options]}


# Widths fit each dropdown's longest option beside its arrow.
_LINE = _field("line", "Line", "line", 112)
_BLOCK = _field("block", "Block", "block", 176)
_POSITION = _field("position", "Position", "choice", 124,
                   (("normal", "Normal"), ("reverse", "Reverse")))
_SWITCH = _field("switch", "Switch", "switch", 204)

#: Columns of each list row.
LIST_FIELDS: dict[str, tuple[dict[str, Any], ...]] = {
    "occupied_blocks": (_LINE, _BLOCK),
    "switch_states": (_LINE, _SWITCH, _POSITION),
    "crossing_states": (
        _LINE, _field("crossing", "Crossing", "crossing", 104),
        _field("state", "State", "choice", 124,
               (("inactive", "Inactive"), ("active", "Active")))),
}

#: What each row is. Shown in the test UI under the row's name.
ROW_HINTS: dict[str, str] = {
    "ready": "On once a PLC program is loaded on every wayside. Until "
             "then the CTC sends the Track Controller nothing.",
    "occupied_blocks": "Blocks the Track Controller reports occupied: "
                       "trains and failed blocks alike. A train leaves "
                       "the yard into Green 63 or Red 9.",
    "switch_states": "Switch positions the Track Controller reports. "
                     "Normal is the first connection in the layout file.",
    "crossing_states": "Railway crossings and whether they are active.",
}


#: What one entry of a list row is, for its "+ Add" button.
ROW_NOUNS: dict[str, str] = {
    "occupied_blocks": "block",
    "switch_states": "switch",
    "crossing_states": "crossing",
}


class HarnessInputError(ValueError):
    """A row could not be turned into a boundary value."""


def layout_options(
    layout: Mapping[str, Line],
) -> dict[str, dict[str, list[dict[str, str]]]]:
    """Options per layout field type, per line: blocks (with station
    names), switches (with their connections) and crossings."""
    options: dict[str, dict[str, list[dict[str, str]]]] = {
        kind: {} for kind in _LAYOUT_TYPES}
    for name, line in layout.items():
        options["block"][name] = [
            {"value": b.block_id,
             "text": b.block_id + (f" · {b.station.title()}"
                                   if b.station else "")}
            for b in line.blocks]
        options["switch"][name] = [
            {"value": b.block_id, "text": f"{b.block_id} ({b.switch})"}
            for b in line.blocks if b.switch]
        options["crossing"][name] = [
            {"value": b.block_id, "text": b.block_id}
            for b in line.blocks if b.railway_crossing]
    return options


def build_inputs(lists: Mapping[str, list[Entry]]) -> CtcInputs:
    """Turn list-row entries into ``CtcInputs``: the Track Controller's
    part. The Track Model's (ticket sales) is left empty."""
    return CtcInputs(
        track_controller=TrackControllerInputs(
            occupancy=tuple(BlockOccupancy(e["line"], e["block"], True)
                            for e in lists["occupied_blocks"]),
            switches=tuple(SwitchReport(e["line"], e["switch"],
                                        e["position"])
                           for e in lists["switch_states"]),
            crossings=tuple(CrossingReport(e["line"], e["crossing"],
                                           e["state"])
                            for e in lists["crossing_states"]),
            ready=lists["ready"],
        ),
    )


def output_rows(outputs: CtcOutputs,
                elapsed_s: float) -> list[dict[str, Any]]:
    """Rows for the outputs table, in display units: what the CTC sends
    the Track Controller and the central harness."""
    track = outputs.track_controller
    rows: list[dict[str, Any]] = []
    for suggestion in track.suggestions:
        # Where the Track Controller sends this train's speed and
        # authority: the block its head is in.
        rows.append({
            "name": f"block[{suggestion.train_id}]",
            "kind": "string",
            "value": block_key(suggestion.line, suggestion.block_id),
            "unit": "",
        })
        # The type column shows the boundary type (whole m/s); the value
        # is shown in display units, mph.
        rows.append({
            "name": f"suggested_speed[{suggestion.train_id}]",
            "kind": "int",
            "value": round(suggestion.suggested_speed_mps * MPS_TO_MPH, 1),
            "unit": "mph",
        })
        rows.append({
            "name": f"authority[{suggestion.train_id}]",
            "kind": "int",
            "value": suggestion.authority_blocks,
            "unit": "blocks",
        })
    rows.append({
        "name": "closed_blocks",
        "kind": "string",
        "value": ", ".join(block_key(b.line, b.block_id)
                           for b in track.closed_blocks),
        "unit": "",
    })
    rows.append({
        "name": "switch_commands",
        "kind": "string",
        "value": "; ".join(f"{block_key(c.line, c.switch_id)}={c.position}"
                           for c in track.switch_commands),
        "unit": "",
    })
    rows.append({
        "name": "clock_speedup",
        "kind": "bool",
        "value": outputs.clock_speedup,
        "unit": "",
    })
    rows.append({"name": "elapsed", "kind": "float",
                 "value": round(elapsed_s, 1), "unit": "s"})
    return rows


def _from_qml(kind: str, value: Any) -> Any:
    """A row edit as Python expects it.

    QML has one number type, so an int row's value arrives as a float
    (10 as 10.0). A whole number becomes an int; anything else is kept
    for ``build_inputs`` to reject.
    """
    if kind == "int" and isinstance(value, float) and value.is_integer():
        return int(value)
    return value


def _default_choices() -> dict[str, str]:
    return {name: options[0] for name, options in INPUT_CHOICES.items()}


class CtcTestHarness(QObject):
    """Bindable state behind ``TestHarnessView.qml``.

    Send replaces the Track Controller inputs. Dispatcher actions are
    taken in the CTC window; their effect shows in the outputs.
    """

    inputsChanged = Signal()
    outputsChanged = Signal()
    statusChanged = Signal()
    connectedChanged = Signal()

    def __init__(self, link: CtcLink | None = None,
                 layout: Mapping[str, Line] | None = None,
                 parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._link: CtcLink = link if link is not None else LocalLink()
        self._layout = dict(load_layout() if layout is None else layout)
        self._options = layout_options(self._layout)
        self._values: dict[str, Any] = {}
        self._choices: dict[str, str] = {}
        self._reset_values()
        # Whether the link has been up before: a later connection is a
        # reconnect, after which the inputs are sent again.
        self._had_connection = self._link.connected
        self._status = ""
        self._status_error = False
        self._outputs: list[dict[str, Any]] = []
        self._refresh()
        # A socket link reports connection changes and pushes snapshots
        # when the CTC UI changes the module.
        if self._link.ctc_ui_attached and not self._link.connected:
            self._set_status("Connecting to the CTC Office…", False)
        for signal, slot in (("connectedChanged", self._on_connected),
                             ("snapshotChanged", self._on_snapshot),
                             ("connectionFailed", self._on_failed)):
            source = getattr(self._link, signal, None)
            if source is not None:
                source.connect(slot)

    def _reset_values(self) -> None:
        self._values = {
            name: list(default) if kind == "list" else default
            for name, (kind, default, _unit) in INPUT_DEFAULTS.items()}
        self._choices = _default_choices()

    # -- Bindable properties ------------------------------------------

    @Property(list, notify=inputsChanged)
    def inputs(self) -> list[dict[str, Any]]:
        return self._rows(INPUT_DEFAULTS)

    @Property(list, constant=True)
    def lineNames(self) -> list[str]:  # noqa: N802
        return list(self._layout)

    @Property(dict, constant=True)
    def layoutOptions(self) -> dict[str, Any]:  # noqa: N802
        """Options for block, switch and crossing fields, per line."""
        return self._options

    @Property(list, notify=outputsChanged)
    def outputs(self) -> list[dict[str, Any]]:
        return self._outputs

    @Property(bool, notify=connectedChanged)
    def connected(self) -> bool:
        return self._link.connected

    @Property(str, notify=statusChanged)
    def status(self) -> str:
        return self._status

    @Property(bool, notify=statusChanged)
    def statusIsError(self) -> bool:  # noqa: N802
        return self._status_error

    # -- Edits --------------------------------------------------------

    # Typed edits (text and numbers) are stored without re-publishing the
    # rows, so the editor being typed in keeps its focus. Anything drawn
    # from the row's value (a toggle, a dropdown, the list of entries) is
    # re-published; clicking it has already committed any typed text.

    @Slot(str, "QVariant")
    def setInput(self, name: str, value: Any) -> None:  # noqa: N802
        """Stage an edit to a scalar row; applied on Send."""
        kind = self._kind(name)
        if kind is None or kind == "list":
            return
        self._values[name] = _from_qml(kind, value)
        if kind == "bool":
            self.inputsChanged.emit()

    @Slot(str, str)
    def setInputChoice(self, name: str,  # noqa: N802
                       choice: str) -> None:
        """Pick a row's choice, from ``INPUT_CHOICES``."""
        if choice in INPUT_CHOICES.get(name, ()):
            self._choices[name] = choice
            self.inputsChanged.emit()

    @Slot(str)
    def addEntry(self, name: str) -> None:  # noqa: N802
        """Add an entry to a list row, filled with the first options."""
        if self._kind(name) != "list":
            return
        entry = {field["key"]: self._default(field)
                 for field in LIST_FIELDS[name]}
        self._values[name].append(entry)
        self.inputsChanged.emit()

    @Slot(str, int)
    def removeEntry(self, name: str, index: int) -> None:  # noqa: N802
        if self._kind(name) != "list":
            return
        entries = self._values[name]
        if 0 <= index < len(entries):
            del entries[index]
            self.inputsChanged.emit()

    @Slot(str, int, str, "QVariant")
    def setEntryField(self, name: str, index: int,  # noqa: N802
                      key: str, value: Any) -> None:
        """Change one field of one entry of a list row."""
        if self._kind(name) != "list":
            return
        entries = self._values[name]
        field = next((f for f in LIST_FIELDS[name] if f["key"] == key),
                     None)
        if field is None or not 0 <= index < len(entries):
            return
        entry = entries[index]
        entry[key] = value
        if field["kind"] == "line":
            # A new line has different blocks, switches and crossings.
            for other in LIST_FIELDS[name]:
                if other["kind"] in _LAYOUT_TYPES:
                    entry[other["key"]] = self._default(other, line=value)
        if field["kind"] not in ("text", "number"):
            self.inputsChanged.emit()

    @Slot()
    def resetInputs(self) -> None:  # noqa: N802
        """Restore every row to its default."""
        self._reset_values()
        self.inputsChanged.emit()
        self._set_status("Inputs reset. Send to apply them.", False)

    # -- Send ---------------------------------------------------------

    @Slot()
    def send(self) -> None:
        """Replace the Track Controller inputs with the rows."""
        try:
            self._link.set_inputs(build_inputs(self._values))
        except (HarnessInputError, CtcError) as error:
            self._set_status(str(error), True)
            self._refresh()
            return
        self._refresh()
        if self._link.ctc_ui_attached:
            self._set_status("Sent. The CTC window's clock applies the "
                             "inputs on every tick while it runs.", False)
        else:
            self._set_status("Sent. Stepped one 0.1 s tick.", False)

    # -- Internals ----------------------------------------------------

    def _kind(self, name: str) -> str | None:
        if name in INPUT_DEFAULTS:
            return INPUT_DEFAULTS[name][0]
        return None

    def _rows(self, defaults: dict[str, tuple[str, Any, str]]
              ) -> list[dict[str, Any]]:
        rows = []
        for name, (kind, _default, unit) in defaults.items():
            row: dict[str, Any] = {
                "name": name, "kind": kind, "unit": unit,
                "hint": ROW_HINTS.get(name, "")}
            if kind == "list":
                row["fields"] = list(LIST_FIELDS[name])
                row["noun"] = ROW_NOUNS[name]
                # Copies, so QML never holds the harness's own dicts.
                row["entries"] = [dict(e) for e in self._values[name]]
            else:
                row["value"] = self._values[name]
            if name in self._choices:
                row["choices"] = list(INPUT_CHOICES[name])
                row["choice"] = self._choices[name]
            rows.append(row)
        return rows

    def _default(self, field: dict[str, Any],
                 line: str | None = None) -> Any:
        """The value a new entry starts with in one field."""
        first_line = next(iter(self._layout))
        kind = field["kind"]
        if kind == "line":
            return first_line
        if kind in _LAYOUT_TYPES:
            options = self._options[kind].get(line or first_line, [])
            return options[0]["value"] if options else ""
        if kind == "choice":
            return field["options"][0]["value"]
        if kind == "number":
            return 0.0
        return ""

    def _refresh(self) -> None:
        """Read the module's outputs back."""
        try:
            snap = self._link.snapshot()
        except CtcError:
            self._outputs = []           # not connected yet
            self.outputsChanged.emit()
            return
        self._outputs = output_rows(snap.outputs, snap.elapsed_s)
        self.outputsChanged.emit()

    def _on_connected(self) -> None:
        self.connectedChanged.emit()
        self.inputsChanged.emit()
        self._refresh()
        if self._link.connected:
            if self._had_connection:
                self._resend_inputs()
            else:
                self._set_status("Connected to the CTC Office.", False)
            self._had_connection = True
        else:
            self._set_status("The CTC Office is not running. Start it with "
                             "python -m ctc_ui from CTC-Office.", True)

    def _resend_inputs(self) -> None:
        """After the CTC window restarts its module knows nothing of the
        inputs shown here: send them again."""
        try:
            self._link.set_inputs(build_inputs(self._values))
        except (HarnessInputError, CtcError) as error:
            self._set_status("Reconnected, but your inputs could not be "
                             f"re-sent: {error}", True)
            return
        self._refresh()
        self._set_status("Reconnected to the CTC Office; your inputs were "
                         "sent again.", False)

    def _on_failed(self) -> None:
        # Say so once; the link keeps retrying every second.
        if not self._status_error:
            self._set_status("The CTC Office is not running. Start it with "
                             "python -m ctc_ui from CTC-Office.", True)

    def _on_snapshot(self) -> None:
        self._refresh()

    def _set_status(self, text: str, is_error: bool) -> None:
        self._status = text
        self._status_error = is_error
        self.statusChanged.emit()
