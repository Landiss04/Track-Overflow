"""The Track Controller window's bridge between QML and the module.

``TrackControllerState`` owns the module and the test link server. QML
reads its properties and calls its slots; it never touches the module.
Steps from the test UI can arrive a hundred times a second at 10x, so
the window refreshes from a timer at most ten times a second rather
than once per step.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import Property, QObject, QTimer, QUrl, Signal, Slot

from track_ctrl_hw import display, views
from track_ctrl_hw.controller import HwTrackController
from track_ctrl_hw.errors import PlcError, TrackControllerError
from track_ctrl_hw.interface import WaysideSnapshot
from track_ctrl_hw.link import TestLinkServer
from track_ctrl_hw.rows_model import RowsModel
from track_ctrl_hw.territory import load_territory_file

_REFRESH_MS = 100
#: Larger than any real PLC program; guards against loading the wrong
#: file by mistake.
_MAX_PROGRAM_BYTES = 1_000_000


def _local_path(location: str) -> Path:
    # QML file dialogs hand back URLs; scripts and tests pass paths.
    url = QUrl(location)
    if url.isLocalFile():
        return Path(url.toLocalFile())
    return Path(location)


class TrackControllerState(QObject):
    """Everything the Track Controller window shows, and its actions."""

    changed = Signal()
    diagramChanged = Signal()
    #: ``title``, ``message`` and detail lines for an error dialog.
    problem = Signal(str, str, "QVariantList")
    #: ``title`` and ``message`` for an information dialog.
    notice = Signal(str, str)

    def __init__(
        self,
        controller: HwTrackController | None = None,
        server_name: str | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._controller = controller or HwTrackController()
        self._server = (
            TestLinkServer(self._controller, parent=self)
            if server_name is None
            else TestLinkServer(self._controller, server_name, parent=self)
        )
        self._server.stepped.connect(self._mark_dirty)
        self._server.reset.connect(self.refresh)
        self._server.connectedChanged.connect(self.refresh)
        self._selected = ""
        self._dirty = False
        self._seen_ticks = 0
        self._geometry: dict[str, dict[str, Any]] = {}
        self._diagram: dict[str, Any] = {}
        self._details: dict[str, Any] = {}
        self._scalars: dict[str, Any] = {}
        self._blocks = RowsModel(self)
        self._office = RowsModel(self)
        self._switches = RowsModel(self)
        self._devices = RowsModel(self)
        self._report = RowsModel(self)
        self._timer = QTimer(self)
        self._timer.setInterval(_REFRESH_MS)
        self._timer.timeout.connect(self._refresh_if_dirty)
        self._timer.start()
        self.refresh()

    # -- lifecycle ---------------------------------------------------

    @property
    def controller(self) -> HwTrackController:
        """The module this window hosts."""
        return self._controller

    def listen(self) -> bool:
        """Accept a test UI. False if another window already does."""
        return self._server.listen()

    def close(self) -> None:
        """Stop the link and the refresh timer, before shutdown."""
        self._timer.stop()
        self._server.close()

    # -- actions -------------------------------------------------------

    @Slot(str)
    def loadDatabase(self, location: str) -> None:  # noqa: N802
        """Load a wayside database chosen in the window."""
        path = _local_path(location)
        try:
            territory = load_territory_file(path)
            notices = self._controller.load_territory(territory)
        except TrackControllerError as error:
            self.problem.emit(
                "Database not loaded", str(error), []
            )
            return
        self._geometry.pop(territory.wayside_id, None)
        self._selected = territory.wayside_id
        self._server.push_territories()
        self.refresh()
        for message in notices:
            self.notice.emit("PLC program unloaded", message)

    @Slot(str)
    def loadProgram(self, location: str) -> None:  # noqa: N802
        """Load a PLC program into the wayside on screen."""
        if not self._selected:
            self.problem.emit(
                "No wayside", "Load a database before a PLC program.", []
            )
            return
        path = _local_path(location)
        try:
            if path.stat().st_size > _MAX_PROGRAM_BYTES:
                raise PlcError(f"{path.name} is too large to be a program.")
            with open(path, encoding="utf-8") as program_file:
                source = program_file.read()
            self._controller.load_program(self._selected, source, path.name)
        except PlcError as error:
            self.problem.emit(
                "PLC program not loaded", str(error), list(error.diagnostics)
            )
            return
        except (OSError, UnicodeDecodeError) as error:
            self.problem.emit(
                "PLC program not loaded", f"Cannot read {path.name}: {error}",
                [],
            )
            return
        self.refresh()

    @Slot(str)
    def selectWayside(self, wayside_id: str) -> None:  # noqa: N802
        """Show another loaded wayside."""
        if wayside_id in self._controller.wayside_ids:
            self._selected = wayside_id
            self.refresh()

    # -- refresh -------------------------------------------------------

    @Slot()
    def _mark_dirty(self) -> None:
        self._dirty = True

    @Slot()
    def _refresh_if_dirty(self) -> None:
        # Whoever stepped the module, the test UI or the central harness,
        # a new tick shows within one refresh.
        if self._dirty or self._controller.ticks != self._seen_ticks:
            self.refresh()

    @Slot()
    def refresh(self) -> None:
        """Rebuild everything the window shows from the module."""
        self._dirty = False
        snapshot = self._controller.snapshot()
        self._seen_ticks = snapshot.ticks
        ids = list(self._controller.wayside_ids)
        if self._selected not in ids:
            self._selected = ids[0] if ids else ""
        wayside = views.wayside(snapshot, self._selected)
        report = None if wayside is None else wayside.report
        self._scalars = {
            "line": snapshot.line or "",
            "waysides": ids,
            "selected": self._selected,
            "clock": display.clock(snapshot.time_s),
            "maintenance": snapshot.maintenance_mode,
            "testUi": self._server.connected,
            "source": (
                "Inputs from test UI" if self._server.connected
                else "Inputs stopped" if snapshot.ticks
                else "Waiting for inputs"
            ),
            "summary": "" if wayside is None
            else views.territory_summary(wayside),
            "received": "" if snapshot.time_s is None
            else display.clock(snapshot.time_s),
            "uplink": "Not sent yet" if report is None
            else f"Sent {display.clock(report.sent_at_s)}",
            "vitalFault": "" if wayside is None else wayside.scan.vital_fault,
            "agreeing": 0 if wayside is None
            else sum(1 for s in wayside.switches if s.agreeing),
            "switchCount": 0 if wayside is None else len(wayside.switches),
        }
        self._details = (
            {} if wayside is None else views.program_details(wayside)
        )
        self._fill_tables(wayside, snapshot.maintenance_mode)
        self._update_diagram(wayside)
        self.changed.emit()

    def _fill_tables(
        self, wayside: WaysideSnapshot | None, maintenance: bool
    ) -> None:
        if wayside is None:
            for model in (
                self._blocks, self._office, self._switches, self._devices,
                self._report,
            ):
                model.set_rows([])
            return
        self._blocks.set_rows(views.block_rows(wayside))
        self._office.set_rows(views.office_rows(wayside))
        self._switches.set_rows(views.switch_rows(wayside, maintenance))
        self._devices.set_rows(views.device_rows(wayside))
        self._report.set_rows(views.report_rows(wayside))

    def _update_diagram(self, wayside: WaysideSnapshot | None) -> None:
        if wayside is None:
            diagram: dict[str, Any] = {}
        else:
            wayside_id = wayside.territory.wayside_id
            geometry = self._geometry.get(wayside_id)
            if geometry is None:
                geometry = views.geometry_for(wayside)
                self._geometry[wayside_id] = geometry
            diagram = views.diagram(wayside, geometry)
        if diagram != self._diagram:
            self._diagram = diagram
            self.diagramChanged.emit()

    # -- properties ----------------------------------------------------

    def _scalar(self, name: str) -> Any:
        return self._scalars.get(name)

    @Property(str, notify=changed)
    def line(self) -> str:
        """The line this controller runs, or "" before a database."""
        return self._scalar("line")

    @Property("QVariantList", notify=changed)
    def waysides(self) -> list[str]:
        """Loaded wayside IDs, in load order."""
        return self._scalar("waysides")

    @Property(str, notify=changed)
    def selectedWayside(self) -> str:  # noqa: N802
        """The wayside on screen, or ""."""
        return self._scalar("selected")

    @Property(str, notify=changed)
    def clockText(self) -> str:  # noqa: N802
        """Simulation time of the last tick."""
        return self._scalar("clock")

    @Property(bool, notify=changed)
    def maintenance(self) -> bool:
        """Whether the CTC Office has maintenance mode on."""
        return self._scalar("maintenance")

    @Property(bool, notify=changed)
    def testUiConnected(self) -> bool:  # noqa: N802
        """Whether a test UI is supplying the inputs."""
        return self._scalar("testUi")

    @Property(str, notify=changed)
    def sourceText(self) -> str:  # noqa: N802
        """Where the inputs come from, for the header."""
        return self._scalar("source")

    @Property(str, notify=changed)
    def territorySummary(self) -> str:  # noqa: N802
        """Sections and blocks of the wayside on screen."""
        return self._scalar("summary")

    @Property(str, notify=changed)
    def receivedText(self) -> str:  # noqa: N802
        """When inputs last arrived, or "" before any."""
        return self._scalar("received")

    @Property(str, notify=changed)
    def uplinkText(self) -> str:  # noqa: N802
        """When the last report went to the CTC Office."""
        return self._scalar("uplink")

    @Property(str, notify=changed)
    def vitalFault(self) -> str:  # noqa: N802
        """Why the wayside on screen holds every output, or ""."""
        return self._scalar("vitalFault")

    @Property(int, notify=changed)
    def switchesAgreeing(self) -> int:  # noqa: N802
        """Switches that report their commanded position."""
        return self._scalar("agreeing")

    @Property(int, notify=changed)
    def switchCount(self) -> int:  # noqa: N802
        """Switches in the wayside on screen."""
        return self._scalar("switchCount")

    @Property("QVariantMap", notify=changed)
    def program(self) -> dict[str, Any]:
        """The PLC details of the wayside on screen."""
        return self._details

    @Property("QVariantMap", notify=diagramChanged)
    def diagram(self) -> dict[str, Any]:
        """Schematic of the wayside on screen, with its state."""
        return self._diagram

    @Property(QObject, constant=True)
    def blocks(self) -> RowsModel:
        """Rows of the block occupancy table."""
        return self._blocks

    @Property(QObject, constant=True)
    def office(self) -> RowsModel:
        """Suggestions received from the CTC Office."""
        return self._office

    @Property(QObject, constant=True)
    def switches(self) -> RowsModel:
        """Rows of the switch table."""
        return self._switches

    @Property(QObject, constant=True)
    def devices(self) -> RowsModel:
        """Rows of the signals and crossings table."""
        return self._devices

    @Property(QObject, constant=True)
    def report(self) -> RowsModel:
        """The last report to the CTC Office."""
        return self._report
