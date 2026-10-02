"""Test harness state for the CTC Office test UI.

The harness stands in for the Track Controller, the Track Model and
the clock, so the CTC Office can be run on its own. It reaches the
module only through its boundary, over a link (``ctc/link.py``): each
Send builds ``CtcInputs`` from the input rows, applies the dispatcher
rows, advances one fixed tick, and shows only the returned
``CtcOutputs``.

Rows are ``{name, kind, value, unit}`` dicts for ``SignalRow``. Lists of
blocks, trains, switches and so on are entered as one text row each, in
the formats in ``INPUT_FORMATS``. Values are shown in display units
(mph, ft) and converted to backend SI units at this layer, per
``truth/conventions/units.md``.
"""

from __future__ import annotations

import math
from typing import Any, get_args

from PySide6.QtCore import Property, QObject, Signal, Slot

from ctc.interface import (
    BlockOccupancy,
    CrossingReport,
    CrossingState,
    CtcInputs,
    CtcOutputs,
    SwitchPosition,
    SwitchReport,
    TrackFailureKind,
    TrackFailureReport,
    TrackModelInputs,
    TrainReport,
    TrackControllerInputs,
)
from ctc.link import CtcLink, LocalLink
from ctc.model import CtcError

#: Fixed simulated seconds per tick (decision D006), matching the shared
#: clock's default and the Train Model harness.
DT_S = 0.1

MPS_TO_MPH = 2.236936
M_TO_FT = 3.280840

#: Input rows from the neighboring modules, with their defaults.
INPUT_DEFAULTS: dict[str, tuple[str, Any, str]] = {
    "occupied_blocks": ("string", "", ""),
    "train_reports": ("string", "", "ft, mph"),
    "switch_states": ("string", "", ""),
    "crossing_states": ("string", "", ""),
    "track_failures": ("string", "", ""),
    "ticket_sales": ("int", 0, "tickets"),
}

#: Dispatcher rows: stand-ins for the CTC UI's own actions.
DISPATCHER_DEFAULTS: dict[str, tuple[str, Any, str]] = {
    "dispatch_orders": ("string", "", ""),
    "closed_blocks": ("string", "", ""),
    "maintenance_mode": ("bool", False, ""),
}

#: How each text row is written. Shown in the test UI.
INPUT_FORMATS: dict[str, str] = {
    "occupied_blocks": "block IDs, comma-separated: A1, A2",
    "train_reports": "train:block:offset ft:speed mph; ...  T1:A3:40:25",
    "switch_states": "switch=normal|reverse; ...  SW1=reverse",
    "crossing_states": "crossing=inactive|active; ...  X1=active",
    "track_failures": (
        "block=broken_rail|track_circuit|power; ...  A5=broken_rail"),
    "dispatch_orders": "train=destination block; ...  T1=A9",
    "closed_blocks": "block IDs, comma-separated: A5, A6",
}


class HarnessInputError(ValueError):
    """A row could not be parsed into a boundary value."""


def _ids(text: str) -> list[str]:
    return [part.strip() for part in text.split(",") if part.strip()]


def _entries(text: str) -> list[str]:
    return [part.strip() for part in text.split(";") if part.strip()]


def _pairs(text: str, row: str, allowed: tuple[str, ...]) -> list[
    tuple[str, str]
]:
    pairs = []
    for entry in _entries(text):
        key, sep, value = entry.partition("=")
        key, value = key.strip(), value.strip()
        if not sep or not key or value not in allowed:
            raise HarnessInputError(
                f"{row}: '{entry}' must be id=" + "|".join(allowed))
        pairs.append((key, value))
    return pairs


def _number(text: str, row: str, what: str) -> float:
    try:
        value = float(text)
    except ValueError:
        raise HarnessInputError(
            f"{row}: {what} '{text}' is not a number") from None
    if not math.isfinite(value):
        raise HarnessInputError(f"{row}: {what} must be finite")
    return value


def parse_train_reports(text: str) -> tuple[TrainReport, ...]:
    """Parse ``train:block:offset_ft:speed_mph; ...`` into reports.

    Offsets and speeds are converted from display units to SI.
    """
    reports = []
    for entry in _entries(text):
        parts = [part.strip() for part in entry.split(":")]
        if len(parts) != 4 or not all(parts[:2]):
            raise HarnessInputError(
                f"train_reports: '{entry}' must be "
                "train:block:offset ft:speed mph")
        train_id, block_id, offset_ft, speed_mph = parts
        reports.append(TrainReport(
            train_id=train_id,
            block_id=block_id,
            offset_m=_number(offset_ft, "train_reports", "offset") / M_TO_FT,
            speed_mps=(
                _number(speed_mph, "train_reports", "speed") / MPS_TO_MPH),
        ))
    return tuple(reports)


def build_inputs(values: dict[str, Any]) -> CtcInputs:
    """Turn input row values into ``CtcInputs``, or raise."""
    switches = _pairs(values["switch_states"], "switch_states",
                      get_args(SwitchPosition))
    crossings = _pairs(values["crossing_states"], "crossing_states",
                       get_args(CrossingState))
    failures = _pairs(values["track_failures"], "track_failures",
                      get_args(TrackFailureKind))
    tickets = values["ticket_sales"]
    if not isinstance(tickets, int) or tickets < 0:
        raise HarnessInputError("ticket_sales must be a whole number >= 0")
    return CtcInputs(
        track_controller=TrackControllerInputs(
            occupancy=tuple(
                BlockOccupancy(block_id, True)
                for block_id in _ids(values["occupied_blocks"])),
            trains=parse_train_reports(values["train_reports"]),
            switches=tuple(
                SwitchReport(switch_id, position)  # type: ignore[arg-type]
                for switch_id, position in switches),
            crossings=tuple(
                CrossingReport(crossing_id, state)  # type: ignore[arg-type]
                for crossing_id, state in crossings),
            failures=tuple(
                TrackFailureReport(block_id, kind)  # type: ignore[arg-type]
                for block_id, kind in failures),
        ),
        track_model=TrackModelInputs(ticket_sales=tickets),
    )


def output_rows(outputs: CtcOutputs, tickets_total: int,
                elapsed_s: float) -> list[dict[str, Any]]:
    """Rows for the outputs table, in display units."""
    rows: list[dict[str, Any]] = []
    for suggestion in outputs.track_controller.suggestions:
        rows.append({
            "name": f"suggested_speed[{suggestion.train_id}]",
            "kind": "float",
            "value": round(suggestion.suggested_speed_mps * MPS_TO_MPH, 1),
            "unit": "mph",
        })
        rows.append({
            "name": f"authority[{suggestion.train_id}]",
            "kind": "string",
            "value": suggestion.authority_block_id,
            "unit": "",
        })
    rows.append({
        "name": "closed_blocks",
        "kind": "string",
        "value": ", ".join(outputs.track_controller.closed_block_ids),
        "unit": "",
    })
    rows.append({
        "name": "maintenance_mode",
        "kind": "bool",
        "value": outputs.track_controller.maintenance_mode,
        "unit": "",
    })
    rows.append({"name": "tickets_sold_total", "kind": "int",
                 "value": tickets_total, "unit": "tickets"})
    rows.append({"name": "elapsed", "kind": "float",
                 "value": round(elapsed_s, 1), "unit": "s"})
    return rows


def _rows(defaults: dict[str, tuple[str, Any, str]],
          values: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {"name": name, "kind": kind, "value": values[name], "unit": unit,
         "hint": INPUT_FORMATS.get(name, "")}
        for name, (kind, _default, unit) in defaults.items()
    ]


class CtcTestHarness(QObject):
    """Bindable state behind ``TestHarnessView.qml``."""

    inputsChanged = Signal()
    outputsChanged = Signal()
    statusChanged = Signal()

    def __init__(self, link: CtcLink | None = None,
                 parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._link: CtcLink = link if link is not None else LocalLink()
        self._inputs = {name: d[1] for name, d in INPUT_DEFAULTS.items()}
        self._dispatcher = {
            name: d[1] for name, d in DISPATCHER_DEFAULTS.items()}
        self._applied_orders: dict[str, str] = {}
        self._applied_closed: set[str] = set()
        self._status = ""
        self._status_error = False
        self._outputs = self._read_back()

    # -- Bindable properties -------------------------------------------

    @Property(list, notify=inputsChanged)
    def inputs(self) -> list[dict[str, Any]]:
        return _rows(INPUT_DEFAULTS, self._inputs)

    @Property(list, notify=inputsChanged)
    def dispatcherInputs(self) -> list[dict[str, Any]]:  # noqa: N802
        return _rows(DISPATCHER_DEFAULTS, self._dispatcher)

    @Property(list, notify=outputsChanged)
    def outputs(self) -> list[dict[str, Any]]:
        return self._outputs

    @Property(bool, constant=True)
    def connected(self) -> bool:
        return self._link.connected

    @Property(str, notify=statusChanged)
    def status(self) -> str:
        return self._status

    @Property(bool, notify=statusChanged)
    def statusIsError(self) -> bool:  # noqa: N802
        return self._status_error

    # -- Edits ---------------------------------------------------------

    # Edits are stored as drafts without re-publishing the rows, so the
    # editor being typed in keeps its focus.

    @Slot(str, "QVariant")
    def setInput(self, name: str, value: Any) -> None:  # noqa: N802
        """Stage an edit to an input row; applied on Send."""
        if name in self._inputs:
            self._inputs[name] = value
        elif name in self._dispatcher:
            self._dispatcher[name] = value

    @Slot()
    def resetInputs(self) -> None:  # noqa: N802
        """Restore every input and dispatcher row to its default."""
        self._inputs = {name: d[1] for name, d in INPUT_DEFAULTS.items()}
        self._dispatcher = {
            name: d[1] for name, d in DISPATCHER_DEFAULTS.items()}
        self.inputsChanged.emit()
        self._set_status("Inputs reset. Send to apply them.", False)

    # -- Send ----------------------------------------------------------

    @Slot()
    def send(self) -> None:
        """Apply dispatcher rows, then step the module one tick."""
        try:
            inputs = build_inputs(self._inputs)
            orders = self._parse_orders()
            closed = set(_ids(self._dispatcher["closed_blocks"]))
            self._apply_dispatcher(orders, closed)
            self._link.step(DT_S, inputs)
        except (HarnessInputError, CtcError) as error:
            self._set_status(str(error), True)
            return
        self._outputs = self._read_back()
        self.outputsChanged.emit()
        self._set_status(f"Sent. Stepped {DT_S:g} s.", False)

    # -- Internals -----------------------------------------------------

    def _parse_orders(self) -> dict[str, str]:
        orders: dict[str, str] = {}
        for entry in _entries(self._dispatcher["dispatch_orders"]):
            train_id, sep, block_id = (p.strip() for p in entry.partition("="))
            if not sep or not train_id or not block_id:
                raise HarnessInputError(
                    f"dispatch_orders: '{entry}' must be train=block")
            orders[train_id] = block_id
        return orders

    def _apply_dispatcher(self, orders: dict[str, str],
                          closed: set[str]) -> None:
        """Send only what changed since the last Send."""
        for train_id in self._applied_orders.keys() - orders.keys():
            self._link.cancel_dispatch(train_id)
        for train_id, block_id in orders.items():
            if self._applied_orders.get(train_id) != block_id:
                self._link.dispatch(train_id, block_id)
        for block_id in self._applied_closed - closed:
            self._link.set_block_closed(block_id, False)
        for block_id in closed - self._applied_closed:
            self._link.set_block_closed(block_id, True)
        self._link.set_maintenance_mode(
            bool(self._dispatcher["maintenance_mode"]))
        self._applied_orders = orders
        self._applied_closed = closed

    def _read_back(self) -> list[dict[str, Any]]:
        snap = self._link.snapshot()
        return output_rows(snap.outputs, snap.tickets_sold_total,
                           snap.elapsed_s)

    def _set_status(self, text: str, is_error: bool) -> None:
        self._status = text
        self._status_error = is_error
        self.statusChanged.emit()
