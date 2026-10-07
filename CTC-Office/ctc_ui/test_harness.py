"""Test harness state for the CTC Office test UI.

The harness stands in for the Track Controller and the Track Model, so
the CTC Office can be run on its own. It reaches the module only
through its boundary, over a link (``ctc/link.py``): each Send builds
``CtcInputs`` from the input rows, applies the dispatcher rows, and
hands the inputs over. Connected to the CTC window, the window's clock
steps the module with them every tick; standalone, Send steps one fixed
tick. The outputs table shows only the module's ``CtcOutputs``.

Rows are dicts for the test UI. Scalar rows are ``{name, kind, value,
unit}`` for ``SignalRow``. A list row (blocks, trains, switches, ...)
has ``kind`` ``"list"``, a ``fields`` schema and its ``entries``, one
dict per entry keyed by field. Lines, blocks, switches and crossings are
picked from the track layout, so every reference names a real place;
block numbers repeat across lines, so each entry picks its line first.
Values are shown in display units (mph, ft) and converted to backend SI
units at this layer, per ``truth/conventions/units.md``.
"""

from __future__ import annotations

import math
from typing import Any, Mapping

from PySide6.QtCore import Property, QObject, Signal, Slot

from ctc.interface import (
    BlockOccupancy,
    CrossingReport,
    CtcInputs,
    CtcOutputs,
    CtcSnapshot,
    DispatchOrder,
    SwitchReport,
    TicketSales,
    TrackFailureReport,
    TrackModelInputs,
    TrainReport,
    TrackControllerInputs,
)
from ctc.link import CtcLink, LocalLink
from ctc.model import CtcError
from ctc.track_layout import Line, load_layout
from ctc_ui.display import (
    M_TO_FT,
    MPS_TO_MPH,
    TimeOfDayError,
    block_key,
    format_time_of_day,
    parse_time_of_day,
)

__all__ = ["CtcTestHarness", "HarnessInputError", "MPS_TO_MPH",
           "M_TO_FT", "build_inputs", "output_rows"]

Entry = dict[str, Any]

#: Input rows from the neighboring modules: (kind, default, unit).
INPUT_DEFAULTS: dict[str, tuple[str, Any, str]] = {
    "occupied_blocks": ("list", (), ""),
    "train_reports": ("list", (), "ft, mph"),
    "switch_states": ("list", (), ""),
    "crossing_states": ("list", (), ""),
    "track_failures": ("list", (), ""),
    "ticket_sales": ("int", 0, "tickets"),
}

#: Dispatcher rows: stand-ins for the CTC UI's own actions.
DISPATCHER_DEFAULTS: dict[str, tuple[str, Any, str]] = {
    "dispatch_orders": ("list", (), ""),
    "closed_blocks": ("list", (), ""),
    "switch_commands": ("list", (), ""),
    "maintenance_mode": ("bool", False, ""),
    "clock_speedup": ("bool", False, ""),
}

#: Rows that also pick one of a few choices, shown as a dropdown in the
#: same row: ticket sales are for one line at a time.
INPUT_CHOICES: dict[str, tuple[str, ...]] = {
    "ticket_sales": ("Green", "Red"),
}

#: Dispatcher rows the CTC UI owns when it is attached.
_CTC_UI_OWNED = frozenset({"maintenance_mode", "clock_speedup"})

#: Dispatcher rows that mirror the module until edited.
_MIRRORED = ("dispatch_orders", "closed_blocks", "switch_commands")

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
_TRAIN = _field("train", "Train", "text", 72)
_POSITION = _field("position", "Position", "choice", 124,
                   (("normal", "Normal"), ("reverse", "Reverse")))
_SWITCH = _field("switch", "Switch", "switch", 204)

#: Columns of each list row.
LIST_FIELDS: dict[str, tuple[dict[str, Any], ...]] = {
    "occupied_blocks": (_LINE, _BLOCK),
    "train_reports": (
        _TRAIN, _LINE, _BLOCK,
        _field("offset_ft", "Offset ft", "number", 80),
        _field("speed_mph", "Speed mph", "number", 80)),
    "switch_states": (_LINE, _SWITCH, _POSITION),
    "crossing_states": (
        _LINE, _field("crossing", "Crossing", "crossing", 104),
        _field("state", "State", "choice", 124,
               (("inactive", "Inactive"), ("active", "Active")))),
    "track_failures": (
        _LINE, _BLOCK,
        _field("kind", "Failure", "choice", 156,
               (("broken_rail", "Broken rail"),
                ("track_circuit", "Track circuit"),
                ("power", "Power")))),
    "dispatch_orders": (
        _TRAIN, _LINE, _BLOCK,
        _field("arrival", "Arrive (HH:MM)", "text", 112)),
    "closed_blocks": (_LINE, _BLOCK),
    "switch_commands": (_LINE, _SWITCH, _POSITION),
}

#: What each row is. Shown in the test UI under the row's name.
ROW_HINTS: dict[str, str] = {
    "occupied_blocks": "Blocks the Track Controller reports occupied.",
    "train_reports": "Where each train is and how fast it is going.",
    "switch_states": "Switch positions the Track Controller reports. "
                     "Normal is the first connection in the layout file.",
    "crossing_states": "Railway crossings and whether they are active.",
    "track_failures": "Failed blocks the Track Controller reports.",
    "ticket_sales": "Tickets sold on the line picked beside it.",
    "dispatch_orders": "Where each train is sent; arrival is optional.",
    "closed_blocks": "Blocks closed for maintenance.",
    "switch_commands": "Switch positions the CTC sets (maintenance mode "
                       "only).",
}


#: What one entry of a list row is, for its "+ Add" button.
ROW_NOUNS: dict[str, str] = {
    "occupied_blocks": "block",
    "train_reports": "train",
    "switch_states": "switch",
    "crossing_states": "crossing",
    "track_failures": "failure",
    "dispatch_orders": "order",
    "closed_blocks": "block",
    "switch_commands": "command",
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


def _text(entry: Entry, key: str) -> str:
    return str(entry.get(key, "")).strip()


def _number(entry: Entry, key: str, where: str) -> float:
    try:
        value = float(entry.get(key, 0))
    except (TypeError, ValueError):
        raise HarnessInputError(
            f"{where}: {key} '{entry.get(key)}' is not a number") from None
    if not math.isfinite(value):
        raise HarnessInputError(f"{where}: {key} must be finite")
    return value


def _where(row: str, index: int) -> str:
    return f"{row} entry {index + 1}"


def _train(entry: Entry, where: str) -> str:
    train_id = _text(entry, "train")
    if not train_id:
        raise HarnessInputError(f"{where}: enter a train ID")
    return train_id


def build_inputs(lists: Mapping[str, list[Entry]], tickets: Any,
                 ticket_line: str = "Green") -> CtcInputs:
    """Turn list-row entries and ticket sales into ``CtcInputs``."""
    if (isinstance(tickets, bool) or not isinstance(tickets, int)
            or tickets < 0):
        raise HarnessInputError("ticket_sales must be a whole number >= 0")
    trains = []
    for i, e in enumerate(lists["train_reports"]):
        where = _where("train_reports", i)
        trains.append(TrainReport(
            train_id=_train(e, where), line=e["line"], block_id=e["block"],
            offset_m=_number(e, "offset_ft", where) / M_TO_FT,
            speed_mps=_number(e, "speed_mph", where) / MPS_TO_MPH))
    return CtcInputs(
        track_controller=TrackControllerInputs(
            occupancy=tuple(BlockOccupancy(e["line"], e["block"], True)
                            for e in lists["occupied_blocks"]),
            trains=tuple(trains),
            switches=tuple(SwitchReport(e["line"], e["switch"],
                                        e["position"])
                           for e in lists["switch_states"]),
            crossings=tuple(CrossingReport(e["line"], e["crossing"],
                                           e["state"])
                            for e in lists["crossing_states"]),
            failures=tuple(TrackFailureReport(e["line"], e["block"],
                                              e["kind"])
                           for e in lists["track_failures"]),
        ),
        track_model=TrackModelInputs(ticket_sales=(
            (TicketSales(ticket_line, tickets),) if tickets else ())),
    )


def build_orders(entries: list[Entry]) -> dict[str, DispatchOrder]:
    """Dispatch order entries as orders by train; a later entry for the
    same train wins."""
    orders: dict[str, DispatchOrder] = {}
    for i, e in enumerate(entries):
        where = _where("dispatch_orders", i)
        arrival_text = _text(e, "arrival")
        try:
            arrival = (parse_time_of_day(arrival_text) if arrival_text
                       else None)
        except TimeOfDayError as error:
            raise HarnessInputError(f"{where}: {error}") from None
        train_id = _train(e, where)
        orders[train_id] = DispatchOrder(train_id, e["line"], e["block"],
                                         arrival)
    return orders


def _mirror(snap: CtcSnapshot) -> dict[str, list[Entry]]:
    """The mirrored dispatcher rows as the module has them now."""
    track = snap.outputs.track_controller
    return {
        "dispatch_orders": [
            {"train": o.train_id, "line": o.line,
             "block": o.destination_block_id,
             "arrival": ("" if o.arrival_s is None
                         else format_time_of_day(o.arrival_s))}
            for o in snap.orders],
        # Closed and still-closing blocks: the output lists both.
        "closed_blocks": [{"line": b.line, "block": b.block_id}
                          for b in sorted(
                              track.closed_blocks,
                              key=lambda b: (b.line, _number_key(b)))],
        "switch_commands": [
            {"line": c.line, "switch": c.switch_id, "position": c.position}
            for c in track.switch_commands],
    }


def _number_key(block: Any) -> tuple[int, str]:
    # Block number as a number where it is one, for display order.
    block_id = block.block_id
    return (int(block_id) if block_id.isdigit() else -1, block_id)


def output_rows(outputs: CtcOutputs, tickets_sold: tuple[TicketSales, ...],
                elapsed_s: float) -> list[dict[str, Any]]:
    """Rows for the outputs table, in display units."""
    track = outputs.track_controller
    rows: list[dict[str, Any]] = []
    for suggestion in track.suggestions:
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
    for sale in tickets_sold:
        rows.append({"name": f"tickets_sold[{sale.line}]", "kind": "int",
                     "value": sale.tickets, "unit": "tickets"})
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

    The orders, closed blocks and switch commands rows mirror the
    module, so changes made in the CTC window show up here; once edited,
    a row keeps the edit until Send applies it. Send makes the module
    match every edited row and replaces the Track Controller and Track
    Model inputs.
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
        # Mirrored rows edited since the last Send.
        self._edited: set[str] = set()
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
            for defaults in (INPUT_DEFAULTS, DISPATCHER_DEFAULTS)
            for name, (kind, default, _unit) in defaults.items()}
        self._choices = _default_choices()

    # -- Bindable properties ------------------------------------------

    @Property(list, notify=inputsChanged)
    def inputs(self) -> list[dict[str, Any]]:
        return self._rows(INPUT_DEFAULTS)

    @Property(list, notify=inputsChanged)
    def dispatcherInputs(self) -> list[dict[str, Any]]:  # noqa: N802
        rows = self._rows(DISPATCHER_DEFAULTS)
        if self._link.ctc_ui_attached:
            # The CTC UI owns maintenance mode (operating mode) and
            # clock speedup (clock speed); they show in the outputs.
            rows = [r for r in rows if r["name"] not in _CTC_UI_OWNED]
        return rows

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
        """Pick a row's choice, e.g. the line ticket sales are for."""
        if choice in INPUT_CHOICES.get(name, ()):
            self._choices[name] = choice
            self.inputsChanged.emit()

    @Slot(str)
    def addEntry(self, name: str) -> None:  # noqa: N802
        """Add an entry to a list row, filled with the first options."""
        if self._kind(name) != "list":
            return
        entry = {field["key"]: self._default(field, name)
                 for field in LIST_FIELDS[name]}
        self._values[name].append(entry)
        self._touched(name, republish=True)

    @Slot(str, int)
    def removeEntry(self, name: str, index: int) -> None:  # noqa: N802
        if self._kind(name) != "list":
            return
        entries = self._values[name]
        if 0 <= index < len(entries):
            del entries[index]
            self._touched(name, republish=True)

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
                    entry[other["key"]] = self._default(other, name,
                                                        line=value)
        self._touched(name,
                      republish=field["kind"] not in ("text", "number"))

    @Slot()
    def resetInputs(self) -> None:  # noqa: N802
        """Restore every row to its default and re-mirror the
        dispatcher rows."""
        self._reset_values()
        self._edited.clear()
        self._refresh()
        self.inputsChanged.emit()
        self._set_status("Inputs reset. Send to apply them.", False)

    # -- Send ---------------------------------------------------------

    @Slot()
    def send(self) -> None:
        """Apply the edited dispatcher rows, then the inputs."""
        try:
            inputs = build_inputs(self._values, self._values["ticket_sales"],
                                  self._choices["ticket_sales"])
            # All or nothing: if any part is rejected, none is applied.
            self._link.apply_batch(inputs, self._dispatcher_actions())
        except (HarnessInputError, CtcError) as error:
            self._set_status(str(error), True)
            self._refresh()
            return
        self._edited.clear()
        self._refresh()
        self.inputsChanged.emit()
        if self._link.ctc_ui_attached:
            self._set_status("Sent. The CTC window's clock applies the "
                             "inputs on every tick while it runs.", False)
        else:
            self._set_status("Sent. Stepped one 0.1 s tick.", False)

    # -- Internals ----------------------------------------------------

    def _kind(self, name: str) -> str | None:
        for defaults in (INPUT_DEFAULTS, DISPATCHER_DEFAULTS):
            if name in defaults:
                return defaults[name][0]
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

    def _default(self, field: dict[str, Any], row: str,
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
        if field["key"] == "train":
            return self._next_train(row)
        return ""

    def _next_train(self, row: str) -> str:
        used = {_text(e, "train") for e in self._values[row]}
        number = 1
        while f"T{number}" in used:
            number += 1
        return f"T{number}"

    def _touched(self, name: str, republish: bool) -> None:
        if name in _MIRRORED:
            self._edited.add(name)
        if republish:
            self.inputsChanged.emit()

    def _dispatcher_actions(self) -> list[tuple[str, dict[str, Any]]]:
        """The actions that make the module match every edited
        dispatcher row, in order."""
        snap = self._link.snapshot()
        track = snap.outputs.track_controller
        actions: list[tuple[str, dict[str, Any]]] = []
        if not self._link.ctc_ui_attached:
            # First, so the closures and switch commands after it are
            # accepted.
            actions.append(("set_maintenance_mode", {
                "active": bool(self._values["maintenance_mode"])}))
            actions.append(("set_clock_speedup", {
                "active": bool(self._values["clock_speedup"])}))
        if "dispatch_orders" in self._edited:
            wanted = build_orders(self._values["dispatch_orders"])
            current = {o.train_id: o for o in snap.orders}
            for train_id in sorted(current.keys() - wanted.keys()):
                actions.append(("cancel_dispatch", {"train_id": train_id}))
            for train_id, order in wanted.items():
                if current.get(train_id) != order:
                    actions.append(("dispatch", {
                        "train_id": train_id, "line": order.line,
                        "destination_block_id": order.destination_block_id,
                        "arrival_s": order.arrival_s}))
        if "closed_blocks" in self._edited:
            wanted_blocks = {(e["line"], e["block"])
                             for e in self._values["closed_blocks"]}
            closed = {(b.line, b.block_id) for b in track.closed_blocks}
            for line, block_id in sorted(closed - wanted_blocks):
                actions.append(("set_block_closed", {
                    "line": line, "block_id": block_id, "closed": False}))
            for line, block_id in sorted(wanted_blocks - closed):
                actions.append(("set_block_closed", {
                    "line": line, "block_id": block_id, "closed": True}))
        if "switch_commands" in self._edited:
            wanted_switches = {(e["line"], e["switch"]): e["position"]
                               for e in self._values["switch_commands"]}
            commanded = {(c.line, c.switch_id): c.position
                         for c in track.switch_commands}
            for line, switch_id in sorted(commanded.keys()
                                          - wanted_switches):
                actions.append(("release_switch", {
                    "line": line, "switch_id": switch_id}))
            for (line, switch_id), position in wanted_switches.items():
                if commanded.get((line, switch_id)) != position:
                    actions.append(("set_switch", {
                        "line": line, "switch_id": switch_id,
                        "position": position}))
        return actions

    def _refresh(self) -> None:
        """Read the module back: outputs, and unedited mirrored rows."""
        try:
            snap = self._link.snapshot()
        except CtcError:
            self._outputs = []           # not connected yet
            self.outputsChanged.emit()
            return
        self._outputs = output_rows(snap.outputs, snap.tickets_sold,
                                    snap.elapsed_s)
        self.outputsChanged.emit()
        mirrored = {name: entries for name, entries in _mirror(snap).items()
                    if name not in self._edited}
        if any(self._values[name] != entries
               for name, entries in mirrored.items()):
            self._values.update(mirrored)
            self.inputsChanged.emit()

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
        inputs shown here: send them again (not the dispatcher rows)."""
        try:
            self._link.set_inputs(build_inputs(
                self._values, self._values["ticket_sales"],
                self._choices["ticket_sales"]))
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
