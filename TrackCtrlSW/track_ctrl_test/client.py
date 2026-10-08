"""The test UI's side of the stimulus link.

``TestClientState`` is the one object the test UI's QML binds to. It
keeps a connection to the Track Controller process, sends stimuli, and
turns each pushed snapshot into the handful of values the views show.

Inputs are split the way the test UI splits them:

physical  ``setOccupancy``, ``setBlockClosed``, ``setSwitchFault``,
          ``setSwitchMoving``, ``setSuggestedSpeed``,
          ``setSuggestedAuthority``, ``setSpeedLimit``,
          ``clearOccupancy``. These write onto the target controller's
          input card, so they change what its PLC program sees.
user      ``selectLine``, ``selectController``, ``setTab``,
          ``setMaintenance``, ``setSwitchByHand``, ``releaseSwitch``,
          ``run``, ``commit``, ``newFile``, ``openIteration``,
          ``editBuffer``, ``loadProgram``. These press the same
          controls the programmer does in the Track Controller UI.

Lists that feed a ComboBox (block ids, switch ids and so on) change only
when the topology or the target changes, never on a plain snapshot, so
a ComboBox is not reset to its first entry once a second.
"""

from __future__ import annotations

import json
from typing import Any

from PySide6.QtCore import Property, QObject, QTimer, Signal, Slot
from PySide6.QtNetwork import QLocalSocket

from track_ctrl.stimulus import SERVER_NAME

#: Milliseconds between reconnection attempts while the controller is
#: not running.
RECONNECT_MS = 1000

#: Text the "Edit buffer" button appends to the programmer's editor.
EDIT_MARKER = "\n// edited from the test UI\n"


class TestClientState(QObject):
    """Connection, target selection and the view of the controller."""

    # Not a test case, despite the name pytest and unittest look for.
    __test__ = False

    connectionChanged = Signal()
    snapshotChanged = Signal()
    topologyChanged = Signal()
    targetChanged = Signal()
    uiTopologyChanged = Signal()
    replyChanged = Signal()

    def __init__(
        self,
        server_name: str = SERVER_NAME,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._server_name = server_name
        self._socket = QLocalSocket(self)
        self._buffer = bytearray()
        self._next_id = 1

        self._snapshot: dict[str, Any] = {}
        self._target = ""
        self._reply = ""
        self._reply_is_error = False

        # Stable lists, rebuilt only when they would actually change.
        self._controller_ids: list[str] = []
        self._controller_labels: list[str] = []
        self._line_names: list[str] = []
        self._block_ids: list[str] = []
        self._block_labels: list[str] = []
        self._switch_ids: list[str] = []
        self._ui_switch_ids: list[str] = []

        self._socket.connected.connect(self._on_connected)
        self._socket.disconnected.connect(self._on_disconnected)
        self._socket.readyRead.connect(self._on_ready)

        self._retry = QTimer(self)
        self._retry.setInterval(RECONNECT_MS)
        self._retry.timeout.connect(self._try_connect)
        self._retry.start()
        self._try_connect()

    # --- connection ---------------------------------------------------

    def _try_connect(self) -> None:
        if self._socket.state() == QLocalSocket.LocalSocketState.UnconnectedState:
            self._socket.connectToServer(self._server_name)

    def _on_connected(self) -> None:
        # Do not clear the receive buffer here. The first snapshot is
        # large and arrives in pieces; if the connected signal is
        # delivered after the first piece, clearing would corrupt it.
        # The buffer is reset when the link goes down instead.
        self._set_reply("Connected to the Track Controller.", False)
        self.connectionChanged.emit()
        self._send({"type": "hello"})
        self._on_ready()

    def _on_disconnected(self) -> None:
        self._buffer.clear()
        self._snapshot = {}
        self._set_reply("Track Controller closed the link.", True)
        self.connectionChanged.emit()
        self.snapshotChanged.emit()

    def _on_ready(self) -> None:
        self._buffer.extend(self._socket.readAll().data())
        while True:
            end = self._buffer.find(b"\n")
            if end < 0:
                return
            raw = bytes(self._buffer[:end])
            del self._buffer[: end + 1]
            if raw.strip():
                self._handle(raw)

    def _handle(self, raw: bytes) -> None:
        try:
            message = json.loads(raw.decode("utf-8"))
        except ValueError:
            return
        kind = message.get("type")
        if kind == "snapshot":
            self._take_snapshot(message)
        elif kind == "error":
            self._set_reply(str(message.get("message", "error")), True)
        elif kind == "ack":
            note = message.get("note", "")
            if note and note != "hello":
                self._set_reply(str(note), False)

    # --- snapshot -----------------------------------------------------

    def _controller(self, controller_id: str) -> dict[str, Any]:
        for entry in self._snapshot.get("controllers", []):
            if entry["id"] == controller_id:
                return entry
        return {}

    def _take_snapshot(self, snapshot: dict[str, Any]) -> None:
        self._snapshot = snapshot
        controllers = snapshot.get("controllers", [])

        ids = [entry["id"] for entry in controllers]
        labels = [
            f"{entry['id']}  ·  {entry['span']}" for entry in controllers
        ]
        lines = list(snapshot.get("lines", []))
        topology_changed = (
            ids != self._controller_ids
            or labels != self._controller_labels
            or lines != self._line_names
        )
        self._controller_ids = ids
        self._controller_labels = labels
        self._line_names = lines

        # First snapshot: aim at whatever the programmer is looking at.
        target_changed = False
        if self._target not in ids and ids:
            ui_controller = snapshot.get("ui", {}).get("controller", ids[0])
            self._target = ui_controller if ui_controller in ids else ids[0]
            target_changed = True

        if self._rebuild_target_lists():
            target_changed = True

        ui_switches = [
            item["id"]
            for item in self._controller(
                snapshot.get("ui", {}).get("controller", "")
            ).get("switches", [])
        ]
        ui_topology_changed = ui_switches != self._ui_switch_ids
        self._ui_switch_ids = ui_switches

        if topology_changed:
            self.topologyChanged.emit()
        if target_changed:
            self.targetChanged.emit()
        if ui_topology_changed:
            self.uiTopologyChanged.emit()
        self.snapshotChanged.emit()

    def _rebuild_target_lists(self) -> bool:
        entry = self._controller(self._target)
        block_ids = [block["id"] for block in entry.get("blocks", [])]
        block_labels = [block["label"] for block in entry.get("blocks", [])]
        switch_ids = [item["id"] for item in entry.get("switches", [])]
        changed = (
            block_ids != self._block_ids
            or block_labels != self._block_labels
            or switch_ids != self._switch_ids
        )
        self._block_ids = block_ids
        self._block_labels = block_labels
        self._switch_ids = switch_ids
        return changed

    def _set_reply(self, text: str, is_error: bool) -> None:
        self._reply = text
        self._reply_is_error = is_error
        self.replyChanged.emit()

    # --- sending ------------------------------------------------------

    def _send(self, payload: dict[str, Any]) -> bool:
        if self._socket.state() != QLocalSocket.LocalSocketState.ConnectedState:
            self._set_reply("Not connected to a Track Controller.", True)
            return False
        payload["id"] = self._next_id
        self._next_id += 1
        line = json.dumps(payload, separators=(",", ":")) + "\n"
        self._socket.write(line.encode("utf-8"))
        self._socket.flush()
        return True

    def _physical(self, op: str, **fields: Any) -> None:
        self._send(
            {"type": "physical", "op": op, "controller": self._target,
             **fields}
        )

    def _user(self, op: str, **fields: Any) -> None:
        self._send({"type": "user", "op": op, **fields})

    # --- connection state for the views ---------------------------------

    @Property(bool, notify=connectionChanged)
    def connected(self) -> bool:
        """Whether a Track Controller is on the other end of the link."""
        return (
            self._socket.state() == QLocalSocket.LocalSocketState.ConnectedState
        )

    @Property(str, notify=replyChanged)
    def reply(self) -> str:
        """The last acknowledgement or error from the controller."""
        return self._reply

    @Property(bool, notify=replyChanged)
    def replyIsError(self) -> bool:
        """Whether :attr:`reply` is a refusal."""
        return self._reply_is_error

    @Property(str, notify=snapshotChanged)
    def clock(self) -> str:
        """The controller's clock."""
        return str(self._snapshot.get("clock", "--:--:--"))

    @Property(bool, notify=snapshotChanged)
    def standin(self) -> bool:
        """Whether the controller's stand-in world is still running."""
        return bool(self._snapshot.get("standin", True))

    # --- stable lists ---------------------------------------------------

    @Property("QStringList", notify=topologyChanged)
    def controllerIds(self) -> list[str]:
        """Every controller id, in line order."""
        return list(self._controller_ids)

    @Property("QStringList", notify=topologyChanged)
    def controllerLabels(self) -> list[str]:
        """Controller ids with their block span, for a picker."""
        return list(self._controller_labels)

    @Property("QStringList", notify=topologyChanged)
    def lineNames(self) -> list[str]:
        """Every line name."""
        return list(self._line_names)

    @Property(str, notify=targetChanged)
    def target(self) -> str:
        """The controller the physical inputs are applied to."""
        return self._target

    @Property("QStringList", notify=targetChanged)
    def blockIds(self) -> list[str]:
        """Block ids owned by the target controller."""
        return list(self._block_ids)

    @Property("QStringList", notify=targetChanged)
    def blockLabels(self) -> list[str]:
        """Block labels owned by the target controller."""
        return list(self._block_labels)

    @Property("QStringList", notify=targetChanged)
    def switchIds(self) -> list[str]:
        """Switch ids on the target controller."""
        return list(self._switch_ids)

    @Property("QStringList", notify=uiTopologyChanged)
    def uiSwitchIds(self) -> list[str]:
        """Switch ids on the controller the programmer has selected."""
        return list(self._ui_switch_ids)

    # --- the target controller, refreshed every snapshot ----------------

    @Property("QVariantMap", notify=snapshotChanged)
    def occupied(self) -> dict[str, Any]:
        """Block id -> occupied, for the target controller."""
        return {
            block["id"]: block["occupied"]
            for block in self._controller(self._target).get("blocks", [])
        }

    @Property("QVariantMap", notify=snapshotChanged)
    def closed(self) -> dict[str, Any]:
        """Block id -> closed, for the target controller."""
        return {
            block["id"]: block["closed"]
            for block in self._controller(self._target).get("blocks", [])
        }

    @Property("QVariantMap", notify=snapshotChanged)
    def switchFault(self) -> dict[str, Any]:
        """Switch id -> faulted, for the target controller."""
        return {
            item["id"]: item["fault"]
            for item in self._controller(self._target).get("switches", [])
        }

    @Property("QVariantMap", notify=snapshotChanged)
    def switchMoving(self) -> dict[str, Any]:
        """Switch id -> mid-throw, for the target controller."""
        return {
            item["id"]: item["moving"]
            for item in self._controller(self._target).get("switches", [])
        }

    @Property("QVariantMap", notify=snapshotChanged)
    def inputs(self) -> dict[str, Any]:
        """The CTC values currently on the target's input card."""
        return dict(self._controller(self._target).get("inputs", {}))

    @Property("QVariantList", notify=snapshotChanged)
    def outputs(self) -> list[Any]:
        """What the target controller is driving, as display rows."""
        return list(self._controller(self._target).get("outputs", []))

    @Property("QVariantList", notify=snapshotChanged)
    def overrides(self) -> list[Any]:
        """Vital restrictions applied to the target's outputs."""
        return list(self._controller(self._target).get("overrides", []))

    @Property(str, notify=snapshotChanged)
    def presence(self) -> str:
        """Occupied blocks on the target, as reported back to the CTC."""
        blocks = self._controller(self._target).get("presence", [])
        return ", ".join(blocks) if blocks else "none"

    @Property("QVariantMap", notify=snapshotChanged)
    def targetInfo(self) -> dict[str, Any]:
        """Mode, iteration and file of the target controller."""
        entry = self._controller(self._target)
        return {
            "mode": "Maintenance" if entry.get("maintenance") else "Automatic",
            "iteration": entry.get("iteration", 0),
            "file": entry.get("file", ""),
            "line": entry.get("line", ""),
        }

    @Property("QVariantMap", notify=snapshotChanged)
    def ui(self) -> dict[str, Any]:
        """What the programmer's UI is currently showing."""
        return dict(self._snapshot.get("ui", {}))

    @Property("QStringList", notify=snapshotChanged)
    def historyLabels(self) -> list[str]:
        """Committed iterations the programmer's UI can open."""
        return [
            f"#{item['number']}  ·  {item['file']}"
            for item in self._snapshot.get("ui", {}).get("history", [])
        ]

    @Property("QVariantList", notify=snapshotChanged)
    def historyNumbers(self) -> list[Any]:
        """Iteration numbers matching :attr:`historyLabels`."""
        return [
            item["number"]
            for item in self._snapshot.get("ui", {}).get("history", [])
        ]

    # --- choosing the target --------------------------------------------

    @Slot(str)
    def selectTarget(self, controller_id: str) -> None:
        """Aim the physical inputs at another controller."""
        if controller_id == self._target or controller_id not in (
            self._controller_ids
        ):
            return
        self._target = controller_id
        self._rebuild_target_lists()
        self.targetChanged.emit()
        self.snapshotChanged.emit()

    # --- physical inputs --------------------------------------------------

    @Slot(str, bool)
    def setOccupancy(self, block_id: str, occupied: bool) -> None:
        """Put a train on, or take it off, one block."""
        self._physical("set_occupancy", block=block_id, value=occupied)

    @Slot()
    def clearOccupancy(self) -> None:
        """Clear every block on the target controller."""
        self._physical("clear_occupancy")

    @Slot(str, bool)
    def setBlockClosed(self, block_id: str, closed: bool) -> None:
        """Close or reopen one block, as the CTC would."""
        self._physical("set_block_closed", block=block_id, value=closed)

    @Slot(str, bool)
    def setSwitchFault(self, switch_id: str, faulted: bool) -> None:
        """Flag a switch machine as faulted."""
        self._physical("set_switch_fault", switch=switch_id, value=faulted)

    @Slot(str, bool)
    def setSwitchMoving(self, switch_id: str, moving: bool) -> None:
        """Flag a switch machine as mid-throw."""
        self._physical("set_switch_moving", switch=switch_id, value=moving)

    @Slot(float)
    def setSuggestedSpeed(self, mph: float) -> None:
        """Send the CTC's suggested speed, in mph."""
        self._physical("set_suggested_speed", value=mph)

    @Slot(float)
    def setSuggestedAuthority(self, blocks: float) -> None:
        """Send the CTC's suggested authority, in blocks."""
        self._physical("set_suggested_authority", value=blocks)

    @Slot(float)
    def setSpeedLimit(self, mph: float) -> None:
        """Override the posted limit; zero or less restores the layout's."""
        self._physical("set_speed_limit", value=mph if mph > 0 else None)

    # --- user inputs --------------------------------------------------------

    @Slot(str)
    def selectLine(self, name: str) -> None:
        """Select a line in the programmer's UI."""
        self._user("select_line", name=name)

    @Slot(str)
    def selectController(self, name: str) -> None:
        """Select a controller in the programmer's UI."""
        self._user("select_controller", name=name)

    @Slot(int)
    def setTab(self, index: int) -> None:
        """Show the Program (0) or View (1) tab."""
        self._user("set_tab", index=index)

    @Slot(bool)
    def setMaintenance(self, active: bool) -> None:
        """Press the programmer's maintenance-mode button."""
        self._user("set_maintenance", value=active)

    @Slot(str, bool)
    def setSwitchByHand(self, switch_id: str, reverse: bool) -> None:
        """Apply the manual-switch dialog."""
        self._user("set_switch", switch=switch_id, reverse=reverse)

    @Slot(str)
    def releaseSwitch(self, switch_id: str) -> None:
        """Release a hand-set switch back to the program."""
        self._user("release_switch", switch=switch_id)

    @Slot()
    def run(self) -> None:
        """Press RUN."""
        self._user("run")

    @Slot()
    def commit(self) -> None:
        """Press COMMIT ITERATION."""
        self._user("commit")

    @Slot()
    def newFile(self) -> None:
        """Press NEW."""
        self._user("new_file")

    @Slot(int)
    def openIteration(self, number: int) -> None:
        """Open a committed iteration; zero returns to the live buffer."""
        self._user("open_file", iteration=number)

    @Slot()
    def editBuffer(self) -> None:
        """Type into the editor, so the buffer no longer matches a run."""
        self._user("append_buffer", text=EDIT_MARKER)

    @Slot(str)
    def loadProgram(self, path: str) -> None:
        """Load a .plc file from disk into the editor."""
        self._user("load_program", path=path)
