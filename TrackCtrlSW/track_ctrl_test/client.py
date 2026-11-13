"""The test UI's side of the link to the Track Controller.

``TestClientState`` is the one object the test UI's QML binds to. It
plays everything around the Track Controller that is not there when it
runs alone:

* the shared clock (D017), ticked in real time at 1x or 10x;
* the CTC Office and the Track Model, as a :class:`StandInWorld`;
* the programmer, through the same buttons the Track Controller UI has.

Each clock tick it builds the module's boundary inputs from the world,
sends them as one ``step``, and feeds the outputs that come back to the
world as the Track Model's read-back. That is the call the central
harness will make, so the test UI exercises the module the way the
harness will. A step is sent only after the last was answered; ticks that
fall due meanwhile are owed and sent as soon as the link is free, so a
slow controller is never buried in requests.

Inputs are split the way the test UI splits them:

physical  ``setOccupancy``, ``clearOccupancy``, ``setSwitchMoving`` (the
          Track Model) and ``setBlockClosed``, ``setSuggestedSpeed``,
          ``setSuggestedAuthority``, ``setAllSuggestions``,
          ``clearSuggestion``, ``setMaintenance``, ``setSwitchCommand``
          (the CTC Office). These change the world, so they change what
          the controller is given on the next tick. Maintenance mode is
          the CTC Office's, so it is a physical input here and not a
          user one. The controller is told nothing about failures: a
          failed block reads as occupied.
user      ``selectLine``, ``selectController``, ``setTab``,
          ``setSwitchByHand``, ``releaseSwitch``, ``run``, ``commit``,
          ``newFile``, ``openIteration``, ``editBuffer``,
          ``loadProgram``. These press the same controls the programmer
          does in the Track Controller UI.

Speeds are typed in mph, as on every screen, and sent as whole m/s, the
system's backend unit. Rounding is down, so a typed speed can only
become slower.

Lists that feed a ComboBox (block ids, switch ids and so on) change only
when the topology or the target changes, never on a plain snapshot, so
a ComboBox is not reset to its first entry once a second.
"""

from __future__ import annotations

import json
from typing import Any

from PySide6.QtCore import Property, QObject, QTimer, Signal, Slot
from PySide6.QtNetwork import QLocalSocket

from track_ctrl import wire
from track_ctrl.display import mps_to_mph, whole_mps_from_mph
from track_ctrl.errors import InvalidInputError, TrackControllerError
from track_ctrl.interface import BlockKey
from track_ctrl.models import list_property
from track_ctrl.stimulus import SERVER_NAME
from track_ctrl_test.world import StandInWorld
from utils.clock_driver import ClockDriver
from utils.system_clock import SystemClock

#: Milliseconds between reconnection attempts while the controller is
#: not running.
RECONNECT_MS = 1000

#: Most ticks owed to a controller that is slower than the clock. Past
#: this the oldest are dropped, so a stalled link cannot queue forever.
MAX_OWED_TICKS = 50

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
        self._world = StandInWorld()
        # The clock is the test UI's, standing in for the harness's.
        self._clock = SystemClock()
        self._driver = ClockDriver(self._clock, self)
        self._driver.start()
        self._clock.add_tick_listener(self._on_clock_tick)
        self._clock.add_state_listener(self._on_clock_state)
        self._owed = 0
        self._step_id: int | None = None
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
        self._tell_clock()
        self._clock.resume()
        self._on_ready()

    def _on_disconnected(self) -> None:
        self._buffer.clear()
        self._snapshot = {}
        self._step_id = None
        self._owed = 0
        self._clock.pause()
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
        elif kind == "outputs":
            self._take_outputs(message)
        elif kind == "busy":
            self._set_reply(
                "Another test UI is already driving the Track Controller.",
                True,
            )
        elif kind == "error":
            if message.get("id") == self._step_id:
                self._step_id = None
            self._set_reply(str(message.get("message", "error")), True)
            self._pump()
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
        if self._world.load_topology(controllers):
            self._owe(1)

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
        self._pump()

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

    # --- the tick: clock, world, step ---------------------------------

    def _on_clock_tick(self, sim_time_s: float, tick_s: float) -> None:
        self._world.advance(tick_s)
        self._owe(1)

    def _on_clock_state(self) -> None:
        self._tell_clock()
        self.snapshotChanged.emit()

    def _tell_clock(self) -> None:
        if self.connected:
            self._send({
                "type": "clock",
                "paused": self._clock.is_paused,
                "speed": self._clock.speed,
            })

    def _owe(self, ticks: int) -> None:
        self._owed = min(self._owed + ticks, MAX_OWED_TICKS)
        self._pump()

    def _pump(self) -> None:
        """Send the next owed step, if the last has been answered."""
        if (
            self._owed <= 0
            or self._step_id is not None
            or not self._world.lines
            or not self.connected
        ):
            return
        self._owed -= 1
        inputs = self._world.build_inputs(self._clock.time_of_day_s)
        payload: dict[str, Any] = {
            "type": "step",
            "dt": self._clock.tick_s,
            "inputs": wire.inputs_to_wire(inputs),
        }
        if self._send(payload):
            self._step_id = payload["id"]

    def _take_outputs(self, message: dict[str, Any]) -> None:
        if message.get("id") != self._step_id:
            return
        self._step_id = None
        try:
            outputs = wire.outputs_from_wire(message.get("outputs"))
        except TrackControllerError as error:
            self._set_reply(f"Bad outputs from the controller: {error}", True)
        else:
            self._world.apply_outputs(outputs)
        self._pump()

    def _key(self, block_id: str) -> BlockKey:
        """A block of the target controller, as the boundary names it.

        Raises:
            InvalidInputError: If the target controller does not own it.
        """
        entry = self._controller(self._target)
        if block_id not in {block["id"] for block in entry.get("blocks", [])}:
            raise InvalidInputError(
                f"{self._target} does not own block {block_id}"
            )
        return BlockKey(entry.get("line_key", ""), block_id)

    def _edit(self, action: Any, note: str) -> None:
        """Change the world, tell the controller at once, and report."""
        try:
            action()
        except TrackControllerError as error:
            self._set_reply(str(error), True)
            return
        self._set_reply(f"TEST {self._target} {note}", False)
        self.snapshotChanged.emit()
        self._owe(1)

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
        """The test UI's clock, simulated time of day."""
        return self._clock.format_time_of_day()

    @Property(bool, notify=snapshotChanged)
    def clockPaused(self) -> bool:
        """Whether the clock is held."""
        return self._clock.is_paused

    @Property(int, notify=snapshotChanged)
    def clockSpeed(self) -> int:
        """The clock's speed, 1 or 10."""
        return self._clock.speed

    @Property(bool, notify=snapshotChanged)
    def controllerReady(self) -> bool:
        """Whether the controller has said it is started up.

        The stand-in CTC sends no suggestion until it has.
        """
        return self._world.controller_ready

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

    def _blocks(self) -> list[dict[str, Any]]:
        return list(self._controller(self._target).get("blocks", []))

    def _switches(self) -> list[dict[str, Any]]:
        return list(self._controller(self._target).get("switches", []))

    @Property("QVariantMap", notify=snapshotChanged)
    def occupied(self) -> dict[str, Any]:
        """Block id -> occupied, for the target controller."""
        occupied = self._world.occupied()
        return {
            block["id"]: self._key(block["id"]) in occupied
            for block in self._blocks()
        }

    @Property("QVariantMap", notify=snapshotChanged)
    def closed(self) -> dict[str, Any]:
        """Block id -> closed, for the target controller."""
        return {
            block["id"]: self._key(block["id"]) in self._world.closed
            for block in self._blocks()
        }

    @Property("QVariantMap", notify=snapshotChanged)
    def switchMoving(self) -> dict[str, Any]:
        """Switch id -> machine held stuck, for the target controller."""
        return {
            item["id"]: self._key(item["block_id"])
            in self._world.stuck_switches
            for item in self._switches()
        }

    @Property("QVariantMap", notify=snapshotChanged)
    def suggestedMph(self) -> dict[str, Any]:
        """Block id -> suggested speed in mph, -1 where none is sent."""
        found: dict[str, Any] = {}
        for block in self._blocks():
            suggestion = self._world.suggestions.get(self._key(block["id"]))
            found[block["id"]] = (
                -1.0 if suggestion is None
                else round(mps_to_mph(suggestion.speed_mps), 1)
            )
        return found

    @Property("QVariantMap", notify=snapshotChanged)
    def suggestedBlocks(self) -> dict[str, Any]:
        """Block id -> suggested authority in blocks, -1 where none."""
        found: dict[str, Any] = {}
        for block in self._blocks():
            suggestion = self._world.suggestions.get(self._key(block["id"]))
            found[block["id"]] = (
                -1 if suggestion is None else suggestion.authority_blocks
            )
        return found

    @Property("QVariantMap", notify=snapshotChanged)
    def ctcCommand(self) -> dict[str, Any]:
        """Switch id -> the CTC's command: normal, reverse or none."""
        return {
            item["id"]: self._world.switch_commands.get(
                self._key(item["block_id"]), "none"
            )
            for item in self._switches()
        }

    @Property("QVariantMap", notify=snapshotChanged)
    def switchForBlock(self) -> dict[str, Any]:
        """Block id -> the switch on that block, where one exists."""
        return {
            item["block_id"]: item["id"]
            for item in self._controller(self._target).get("switches", [])
        }

    @Property(bool, notify=snapshotChanged)
    def maintenance(self) -> bool:
        """Whether the CTC (this test UI) has maintenance mode on."""
        return self._world.maintenance

    @Slot(float, result=int)
    def wholeMps(self, mph: float) -> int:
        """What a typed speed becomes on the wire: whole m/s, rounded down."""
        return whole_mps_from_mph(mph)

    @list_property(snapshotChanged)
    def outputs(self) -> list[Any]:
        """What the target controller is driving, as display rows."""
        return list(self._controller(self._target).get("outputs", []))

    @list_property(snapshotChanged)
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

    @list_property(snapshotChanged)
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
        self._edit(
            lambda: self._world.set_occupancy(self._key(block_id), occupied),
            f"occupancy {block_id} = {int(occupied)}",
        )

    @Slot()
    def clearOccupancy(self) -> None:
        """Clear every block on the target controller."""
        keys = [self._key(block["id"]) for block in self._blocks()]
        self._edit(
            lambda: self._world.clear_occupancy(keys),
            "occupancy cleared on every block",
        )

    @Slot(str, bool)
    def setBlockClosed(self, block_id: str, closed: bool) -> None:
        """Close or reopen one block, as the CTC would."""
        self._edit(
            lambda: self._world.set_closed(self._key(block_id), closed),
            f"block {block_id} {'closed' if closed else 'opened'}",
        )

    @Slot(str, bool)
    def setSwitchMoving(self, switch_id: str, moving: bool) -> None:
        """Hold a switch machine where it is, so it does not follow."""
        block_id = self._switch_block(switch_id)
        self._edit(
            lambda: self._world.set_switch_stuck(
                self._key(block_id), moving
            ),
            f"switch {switch_id} {'held' if moving else 'released'}",
        )

    def _switch_block(self, switch_id: str) -> str:
        for item in self._switches():
            if item["id"] == switch_id:
                return str(item["block_id"])
        return switch_id

    @Slot(str, float)
    def setSuggestedSpeed(self, block_id: str, mph: float) -> None:
        """Suggest a speed for one block, typed in mph."""
        mps = whole_mps_from_mph(mph)
        self._edit(
            lambda: self._world.set_suggestion(
                self._key(block_id), speed_mps=mps
            ),
            f"CTC suggests block {block_id}: {mps} m/s",
        )

    @Slot(str, float)
    def setSuggestedAuthority(self, block_id: str, blocks: float) -> None:
        """Suggest an authority, in blocks, for one block."""
        self._edit(
            lambda: self._world.set_suggestion(
                self._key(block_id), authority_blocks=blocks
            ),
            f"CTC suggests block {block_id}: {blocks:g} block(s)",
        )

    @Slot(float, float)
    def setAllSuggestions(self, mph: float, blocks: float) -> None:
        """Suggest the same speed and authority for every block."""
        keys = [self._key(block["id"]) for block in self._blocks()]
        mps = whole_mps_from_mph(mph)
        self._edit(
            lambda: self._world.set_all_suggestions(keys, mps, blocks),
            f"CTC suggestion set on all {len(keys)} blocks",
        )

    @Slot(str)
    def clearSuggestion(self, block_id: str) -> None:
        """Send nothing for one block."""
        self._edit(
            lambda: self._world.clear_suggestion(self._key(block_id)),
            f"CTC sends nothing for block {block_id}",
        )

    @Slot(bool)
    def setMaintenance(self, active: bool) -> None:
        """Turn the CTC Office's maintenance mode on or off, system-wide."""
        self._edit(
            lambda: self._world.set_maintenance(active),
            f"CTC maintenance mode = {int(active)}",
        )

    @Slot(str, str)
    def setSwitchCommand(self, switch_id: str, position: str) -> None:
        """Command a switch normal or reverse; any other value withdraws."""
        chosen = position if position in ("normal", "reverse") else None
        self._edit(
            lambda: self._world.set_switch_command(
                self._key(self._switch_block(switch_id)), chosen
            ),
            f"CTC commands switch {switch_id} {chosen or 'withdrawn'}",
        )

    # --- the clock (the harness's, played by the test UI) --------------------

    @Slot()
    def pauseClock(self) -> None:
        """Hold the clock."""
        self._clock.pause()

    @Slot()
    def resumeClock(self) -> None:
        """Run the clock."""
        self._clock.resume()

    @Slot(int)
    def setClockSpeed(self, speed: int) -> None:
        """Set the clock to 1x or 10x."""
        self._clock.set_speed(speed)

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
