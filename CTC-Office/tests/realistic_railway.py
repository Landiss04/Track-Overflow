"""A realistic railway for the CTC Office's scheduler tests.

The CTC Office (``StubCtcOffice``) is driven through ``ctc.step(dt,
inputs)`` as the harness drives it, with the rest of the system stood in
for closely enough that a train can do what real ones did in the full
system: overrun its authority, stand next to another train, and be held
there by a wayside for good.

What it models
--------------

- **The waysides are the real ones.** Red runs the HW Track Controller
  (``TrackCtrlHw/track_ctrl_hw``) loaded with the three integration PLC
  programs (``TrackCtrlHw/data/plc/red_wayside_{1,2,3}_integration_test
  .plc``) and their territories, as the harness loads them with
  ``--load-starters``. Green runs the SW Track Controller
  (``TrackCtrlSW/track_ctrl``) with its generated starter programs on
  the default division of ``green_line.json``. Each is stepped with the
  CTC's suggestions (two for one block: the lower speed and the lower
  authority, each on its own, as ``common/harness/wayside_edges.py``
  merges them), closures, switch commands and route requests, and with
  the railway's occupancy and actual switch positions. Its track
  circuits (speed, authority per block) are what the trains obey, and
  its switch commands are what the switches do.
- **The track is the Track Model's.** Where a train goes on leaving a
  block is ``track_model.layout.Layout.next_block`` with the switches
  as they actually are: a train goes where the rails lead, not where
  the CTC routed it, and on into the next block whether or not it had
  the authority to.
- **Occupancy** is one block per train, the block its head is in, as
  the Track Model reports it (``TrackModel/track_model/model.py``
  ``_controller_outputs``).
- **Switches** move only when their wayside commands it, and take
  ``switch_move_s`` to do so; until then they report where they were.
- **Trains** have a position within their block and a speed. Each
  obeys the track circuit of the block its head is in (none: 0 m/s and
  no authority, as the Track Model sends). Its controller aims for the
  commanded speed and for a stop at the end of its authority: it
  wants to brake once its speed is more than it could stop from in the
  distance left to the end of its authority, less the distance it
  covers in its reaction time and one tick (``reaction_s + dt_s``).
  The brake comes on ``reaction_s`` after the controller first wants
  it (for a lower commanded speed, or to stop), and while it waits the
  train coasts. It then brakes at ``brake_mps2``: by default the CTC's
  own full train under the service brake, with the block's grade
  (``StubCtcOffice._full_train_braking_mps2``), the rate the CTC's
  suggested speed assumes. It accelerates at ``accel_mps2``, with no
  delay.

What it leaves out
------------------

- A train is a point at its head: no length, no tail block.
- No passengers, doors, signals, crossings, beacons, failures or
  track heaters. Coasting holds speed on any grade.
- The CTC and the waysides are stepped when the occupancy or a switch
  report changes, and otherwise every ``control_period_s``; the trains
  every ``dt_s``. In the full system every module steps every tick.
- The controller's braking curve uses the same braking rate as the
  train itself: it knows its own brake exactly.

``RealisticRailway.run`` runs the CTC's schedule until every run is
done, the line stands still for ``stall_s`` (a deadlock), or
``max_s``. It records what the tests check: each run's stops in
order, every block entered beyond the authority the train was given
(``Overrun``), every pair of trains standing next to each other while
the wayside zeroes both (``Freeze``), each train's long waits, and on a
deadlock what every train was waiting for.
"""

from __future__ import annotations

import json
import math
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

_REPO = Path(__file__).resolve().parents[2]
for _path in (_REPO / "CTC-Office", _REPO):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))
# Appended, not inserted: each module has its own ``tests`` package,
# and the CTC Office's must win.
for _path in (_REPO / "TrackModel", _REPO / "TrackCtrlHw",
              _REPO / "TrackCtrlSW"):
    if str(_path) not in sys.path:
        sys.path.append(str(_path))

from common.harness.track_devices import switch_places  # noqa: E402
from ctc.interface import CtcOutputs, SwitchReport  # noqa: E402
from ctc.model import StubCtcOffice  # noqa: E402
from ctc.scheduler import SIMULATION_START_S  # noqa: E402
from ctc.tracking import YARD_EXITS  # noqa: E402
from tests.occupancy import reports  # noqa: E402
from track_model.interface import SwitchPosition as TmPosition  # noqa: E402
from track_model.layout import YARD, load_layout  # noqa: E402

_TM_FILES = {"Green": "green_line.json", "Red": "red_line.json"}

#: How far short of the end of its authority the lookahead controller
#: aims to stop, in m.
STOP_SHORT_M = 1.0


def clock(seconds: float) -> str:
    """Seconds since midnight as ``HH:MM:SS``."""
    seconds = int(round(seconds))
    return (f"{seconds // 3600:02d}:{seconds // 60 % 60:02d}:"
            f"{seconds % 60:02d}")


# ---------------------------------------------------------------- records


@dataclass(frozen=True)
class Overrun:
    """A train entered a block its track circuit gave it no authority
    into."""

    time_s: float
    train_id: str
    from_block: str
    to_block: str
    speed_mps: float
    # The circuit it was obeying: (speed, authority).
    circuit: tuple[int, int]
    # The CTC's suggestion for that block, if any: (speed, authority).
    suggested: tuple[int, int] | None
    # The CTC's authority for the train then: blocks, end, reason, at.
    ctc_authority: str

    @property
    def past_ctc(self) -> bool:
        """Whether it ran past the CTC's own authority, not only past a
        wayside's cut of it (the CTC's suggestion for the block gave it
        at least one block more)."""
        return self.suggested is None or self.suggested[1] < 1

    def __str__(self) -> str:
        return (f"{clock(self.time_s)} {self.train_id} {self.from_block}"
                f"->{self.to_block} at {self.speed_mps:.1f} m/s, circuit "
                f"{self.circuit}, CTC suggested {self.suggested}, CTC "
                f"authority {self.ctc_authority}")


@dataclass
class Freeze:
    """Two trains standing in neighbouring blocks. The CTC never lets
    that happen (``keep_gap``: one empty block between trains), so one
    of them has run past its authority; and a wayside holds a train with
    an occupied neighbour (Red's ``AUTH_n``; Green's ``AUTH_n`` holds one
    whose next block is occupied), so neither may move again. ``why_a``
    and ``why_b`` say what held each when it was found: the CTC's
    authority, and whether the wayside zeroed its suggestion."""

    start_s: float
    train_a: str
    block_a: str
    train_b: str
    block_b: str
    why_a: str = ""
    why_b: str = ""
    end_s: float | None = None

    def __str__(self) -> str:
        end = "never cleared" if self.end_s is None else (
            f"cleared {clock(self.end_s)}")
        return (f"{clock(self.start_s)} {self.train_a}@{self.block_a} "
                f"[{self.why_a}] next to {self.train_b}@{self.block_b} "
                f"[{self.why_b}] ({end})")


@dataclass(frozen=True)
class Wait:
    """A train standing still, not dwelling at a stop."""

    train_id: str
    block: str
    start_s: float
    seconds: float
    # What the CTC said held it, when it stopped and when it left.
    why: str

    def __str__(self) -> str:
        return (f"{self.train_id} {self.seconds / 60:.1f} min on "
                f"{self.block} from {clock(self.start_s)}: {self.why}")


@dataclass
class Train:
    train_id: str
    block: str
    came_from: str          # a block, or YARD
    pos_m: float = 0.0
    speed_mps: float = 0.0
    brake_wanted_since: float | None = None
    stood_since: float | None = None
    stood_why: str = ""


@dataclass
class Result:
    line: str
    reaction_s: float
    controller: str = "lookahead"
    finished: bool = False
    end_s: float = 0.0
    # Each run's stops, in the order it dwelt at them.
    stops: dict[str, list[str]] = field(default_factory=dict)
    # Stops where the run was not on its stop block when it dwelt.
    misplaced_dwells: list[str] = field(default_factory=list)
    overruns: list[Overrun] = field(default_factory=list)
    freezes: list[Freeze] = field(default_factory=list)
    waits: list[Wait] = field(default_factory=list)
    collisions: list[str] = field(default_factory=list)
    misroutes: list[str] = field(default_factory=list)
    trailed: list[str] = field(default_factory=list)
    # What the railway could not follow: a train run into the yard or a
    # dead end, the CTC following a train somewhere else.
    anomalies: list[str] = field(default_factory=list)
    deadlock: list[str] = field(default_factory=list)
    released: list[str] = field(default_factory=list)
    retired: list[str] = field(default_factory=list)
    statuses: dict[str, str] = field(default_factory=dict)

    @property
    def clock(self) -> str:
        return clock(SIMULATION_START_S + self.end_s)

    def longest_waits(self, count: int = 5) -> list[Wait]:
        return sorted(self.waits, key=lambda w: -w.seconds)[:count]

    def summary(self) -> str:
        lines = [f"{self.line} ({self.controller} controller, reaction "
                 f"{self.reaction_s} s): "
                 + (f"done at {self.clock}" if self.finished
                    else f"NOT done, stopped at {self.clock}")
                 + f"; {len(self.overruns)} overruns, "
                 f"{len(self.freezes)} freezes, "
                 f"{len(self.collisions)} collisions"]
        lines += [f"  overrun {o}" for o in self.overruns]
        lines += [f"  freeze {f}" for f in self.freezes]
        lines += [f"  collision {c}" for c in self.collisions]
        lines += [f"  misroute {m}" for m in self.misroutes[:10]]
        lines += [f"  trailed {t}" for t in self.trailed[:10]]
        lines += [f"  anomaly {a}" for a in self.anomalies[:10]]
        lines += [f"  wait {w}" for w in self.longest_waits()]
        if self.deadlock:
            lines.append("  DEADLOCK:")
            lines += [f"    {d}" for d in self.deadlock]
        return "\n".join(lines)


# ---------------------------------------------------------------- waysides


class _Wayside:
    """One line's Track Controller, stepped with the CTC's outputs and
    the railway's state; returns circuits and switch commands by the
    CTC's block and switch IDs.

    A scan is skipped, and the last outputs kept, when its inputs are
    the same as the last scan's and that scan's outputs were the same
    as the one before: the programs are combinational, so it would give
    the same again. This keeps a whole schedule fast."""

    line: str
    _last_key: object = None
    _last_out: object = None
    _settled: bool = False

    def step(self, dt: float, time_s: float, out: CtcOutputs,
             occupied: set[str], switches: dict[str, str]
             ) -> tuple[dict[str, tuple[int, int]], dict[str, str]]:
        tc = out.track_controller
        key = (tuple(sorted(self._merged(out).items())),
               tuple(sorted((b.line, b.block_id) for b in tc.closed_blocks)),
               tuple(sorted((c.line, c.switch_id, c.position)
                            for c in tc.switch_commands)),
               tuple(sorted((c.line, c.switch_id, c.position)
                            for c in tc.route_requests)),
               frozenset(occupied), tuple(sorted(switches.items())))
        if key == self._last_key and self._settled:
            return self._last_out
        result = self._scan(dt, time_s, out, occupied, switches)
        self._settled = key == self._last_key and result == self._last_out
        self._last_key, self._last_out = key, result
        return result

    def _scan(self, dt: float, time_s: float, out: CtcOutputs,
              occupied: set[str], switches: dict[str, str]
              ) -> tuple[dict[str, tuple[int, int]], dict[str, str]]:
        raise NotImplementedError

    def _merged(self, out: CtcOutputs) -> dict[str, tuple[int, int]]:
        # Two suggestions for one block: the lower speed and the lower
        # authority, each on its own (``wayside_edges``).
        merged: dict[str, tuple[int, int]] = {}
        for s in out.track_controller.suggestions:
            if s.line != self.line:
                continue
            speed, auth = int(s.suggested_speed_mps), int(s.authority_blocks)
            if s.block_id in merged:
                old = merged[s.block_id]
                speed, auth = min(speed, old[0]), min(auth, old[1])
            merged[s.block_id] = (speed, auth)
        return merged


class RedHwWayside(_Wayside):
    """The HW Track Controller with the three Red integration programs."""

    line = "Red"

    def __init__(self) -> None:
        from track_ctrl_hw import interface as hwi
        from track_ctrl_hw.controller import HwTrackController
        from track_ctrl_hw.territory import load_territory_file
        self._i = hwi
        data = _REPO / "TrackCtrlHw" / "data"
        self.controller = HwTrackController()
        for n in (1, 2, 3):
            stem = f"red_wayside_{n}_integration_test"
            self.controller.load_territory(load_territory_file(
                data / "waysides" / f"{stem}.json"))
            self.controller.load_program(
                f"Red-{n}", (data / "plc" / f"{stem}.plc").read_text(
                    encoding="utf-8"), f"{stem}.plc")
        snap = self.controller.snapshot()
        self._keys = {k.block_id: k for w in snap.waysides
                      for k in w.territory.keys}
        self._switch_keys = {s.switch.key.block_id: s.switch.key
                             for w in snap.waysides for s in w.switches}

    def _scan(self, dt, time_s, out, occupied, switches):
        i = self._i
        tc = out.track_controller
        ref = lambda b: self._keys[b].ref  # noqa: E731
        inputs = i.TrackControllerInputs(
            time_s=time_s,
            ctc=i.CtcInputs(
                closed_blocks=frozenset(
                    ref(b.block_id) for b in tc.closed_blocks
                    if b.line == self.line),
                switch_commands={
                    ref(c.switch_id): c.position
                    for c in tc.switch_commands if c.line == self.line},
                route_requests={
                    ref(c.switch_id): c.position
                    for c in tc.route_requests if c.line == self.line},
                suggestions={
                    ref(b): i.Suggestion(*value)
                    for b, value in self._merged(out).items()}),
            track_model=i.TrackModelInputs(
                occupied_blocks=frozenset(self._keys[b] for b in occupied),
                switch_positions={self._switch_keys[s]: p
                                  for s, p in switches.items()}))
        result = self.controller.step(dt, inputs)
        circuits = {k.block_id: (c.speed_mps, c.authority_blocks)
                    for k, c in result.track_model.track_circuits.items()}
        commands = {k.block_id: p for k, p in
                    result.track_model.switch_commands.items()}
        return circuits, commands


class GreenSwWayside(_Wayside):
    """The SW Track Controller with its generated starter programs."""

    line = "Green"

    def __init__(self) -> None:
        from track_ctrl import interface as swi
        from track_ctrl.layout import default_layout_dir, load_layout_file
        from track_ctrl.module import SwTrackController
        self._i = swi
        self.controller = SwTrackController()
        self.controller.load_track(load_layout_file(
            default_layout_dir() / "green_line.json").divide())
        self.controller.load_starter_programs()

    def _key(self, block_id: str):
        return self._i.BlockKey(self.line, block_id)

    def _scan(self, dt, time_s, out, occupied, switches):
        i = self._i
        tc = out.track_controller
        inputs = i.TrackControllerInputs(
            time_s=time_s,
            ctc=i.CtcInputs(
                closed_blocks=frozenset(
                    self._key(b.block_id) for b in tc.closed_blocks
                    if b.line == self.line),
                switch_commands={
                    self._key(c.switch_id): c.position
                    for c in tc.switch_commands if c.line == self.line},
                route_requests={
                    self._key(c.switch_id): c.position
                    for c in tc.route_requests if c.line == self.line},
                suggestions={
                    self._key(b): i.Suggestion(*value)
                    for b, value in self._merged(out).items()}),
            track_model=i.TrackModelInputs(
                occupied_blocks=frozenset(self._key(b) for b in occupied),
                switch_positions={self._key(s): p
                                  for s, p in switches.items()}))
        result = self.controller.step(dt, inputs)
        circuits = {k.block_id: (c.speed_mps, c.authority_blocks)
                    for k, c in result.track_model.track_circuits.items()}
        commands = {k.block_id: p for k, p in
                    result.track_model.switch_commands.items()}
        return circuits, commands


# ---------------------------------------------------------------- railway


class RealisticRailway:
    """One line of the railway around a CTC Office (module docstring).

    ``brake_mps2`` is a rate, or a function of the block, or None for
    the CTC's full train under the service brake on that block's grade.
    """

    def __init__(self, ctc: StubCtcOffice, line: str, *,
                 reaction_s: float = 1.0,
                 controller: str = "lookahead",
                 brake_mps2: float | Callable[[str], float] | None = None,
                 accel_mps2: float = 0.5,
                 dt_s: float = 0.1,
                 control_period_s: float = 5.0,
                 switch_move_s: float = 2.0,
                 stall_s: float = 20 * 60,
                 freeze_s: float = 5.0) -> None:
        self.ctc = ctc
        self.line = line
        self.reaction_s = reaction_s
        if controller not in ("lookahead", "speed"):
            raise ValueError(f"unknown controller {controller!r}")
        self.controller = controller
        self.accel = accel_mps2
        self.dt = dt_s
        self.control_period = control_period_s
        self.switch_move_s = switch_move_s
        self.stall_s = stall_s
        self.freeze_s = freeze_s
        if brake_mps2 is None:
            brake = lambda b: ctc._full_train_braking_mps2(line, b)  # noqa
        elif callable(brake_mps2):
            brake = brake_mps2
        else:
            brake = lambda b, r=float(brake_mps2): r  # noqa: E731
        path = _REPO / "TrackModel" / _TM_FILES[line]
        self.layout = load_layout([path])
        upper = line.upper()
        self._tm = {str(b.number): b.block_id
                    for b in self.layout.blocks.values() if b.line == upper}
        self._ctc_id = {tm: n for n, tm in self._tm.items()}
        self._tm_id = dict(self._tm)
        self.lengths = {n: self.layout.blocks[tm].length_m
                        for n, tm in self._tm.items()}
        self._rate = {n: brake(n) for n in self._tm}
        self._brake = self._rate.__getitem__
        self._ahead_cache: dict[tuple, tuple[list[str], float]] = {}
        self.neighbours = {
            n: {self._ctc_id[x] for x in self.layout.neighbours[tm]}
            for n, tm in self._tm.items()}
        places = switch_places(json.loads(path.read_text(encoding="utf-8")))
        # Track Controller switch ID -> the Track Model's point block.
        self._points = {p.switch_id: self._tm[p.point] for p in places}
        self._legs = {self._tm[p.point]: self.layout.switches[
            self._tm[p.point]] for p in places}
        self.wayside: _Wayside = (RedHwWayside() if line == "Red"
                                  else GreenSwWayside())
        self.switches = {s: "normal" for s in self._points}
        self._commanded = dict(self.switches)
        self._moving_since: dict[str, float] = {}
        self._switch_version = 0
        self.trains: dict[str, Train] = {}
        self.circuits: dict[str, tuple[int, int]] = {}
        self.suggested: dict[str, tuple[int, int]] = {}
        self.now = 0.0
        self._last_ctc = 0.0
        self._last_report: tuple | None = None
        self._last_progress = 0.0
        self._progress_mark: tuple | None = None
        self._open_freezes: dict[tuple[str, str], Freeze] = {}
        self._adjacent_since: dict[tuple[str, str], float] = {}
        self._dwelling: dict[str, tuple[str, float]] = {}
        self.result = Result(line, reaction_s, controller)
        self._authority_text: dict[str, str] = {}
        self._snap = None

    # -- the loop ----------------------------------------------------

    def run(self, max_s: float = 8 * 3600) -> Result:
        result = self.result
        for plan in self.ctc._auto.plans:
            if plan.line == self.line:
                result.stops.setdefault(plan.train_id, [])
        while self.now < max_s:
            self.tick()
            if self._snap is not None:
                runs = [r for r in self._snap.scheduled_runs
                        if r.line == self.line]
                if runs and all(r.status == "done" for r in runs) \
                        and not self.trains:
                    result.finished = True
                    break
            if self.now - self._last_progress > self.stall_s:
                result.deadlock = self._describe()
                break
        result.end_s = self.now
        self._close_waits()
        for key, freeze in self._open_freezes.items():
            result.freezes.append(freeze)
        self._open_freezes.clear()
        if self._snap is not None:
            result.statuses = {r.train_id: r.status
                               for r in self._snap.scheduled_runs
                               if r.line == self.line}
        return result

    def tick(self) -> None:
        self.now += self.dt
        report = (frozenset(t.block for t in self.trains.values()),
                  tuple(sorted(self.switches.items())))
        if (report != self._last_report
                or self.now - self._last_ctc >= self.control_period - 1e-9):
            self._control(report)
        self._move_switches()
        for train in sorted(self.trains.values(), key=lambda t: t.train_id):
            self._drive(train)
        self._watch()

    # -- CTC and wayside ---------------------------------------------

    def _control(self, report: tuple) -> None:
        dt = self.now - self._last_ctc
        self._last_ctc = self.now
        self._last_report = report
        occupied = {t.block for t in self.trains.values()}
        out = self.ctc.step(dt, reports(
            occupied=[(self.line, b) for b in occupied],
            switches=[SwitchReport(self.line, s, p)
                      for s, p in self.switches.items()]))
        snap = self.ctc.snapshot()
        self._snap = snap
        for gone in out.retired_trains:
            train = self.trains.pop(gone.train_id, None)
            if train is not None:
                self._end_wait(train)
                self.result.retired.append(gone.train_id)
                self._progress()
        exit_block = YARD_EXITS[self.line]
        for new in out.new_trains:
            if new.train_id in self.trains:
                continue
            for other in self.trains.values():
                if other.block == exit_block:
                    self.result.collisions.append(
                        f"{clock(self._t())} {new.train_id} released onto "
                        f"{exit_block} with {other.train_id} on it")
            self.trains[new.train_id] = Train(new.train_id, exit_block, YARD)
            self.result.released.append(new.train_id)
            self._progress()
        self._authority_text = {
            a.train_id: (f"{a.blocks} to {a.end_block_id} ({a.reason}"
                         + (f" {a.at}" if a.at else "")
                         + (f" by {a.held_by}" if a.held_by else "") + ")")
            for a in snap.authorities if a.line == self.line}
        self._limits = {a.train_id: a for a in snap.authorities
                        if a.line == self.line}
        occupied = {t.block for t in self.trains.values()}
        self.suggested = self.wayside._merged(out)
        self.circuits, commands = self.wayside.step(
            max(dt, 1e-3), self._t(), out, occupied, dict(self.switches))
        for switch_id, position in commands.items():
            if switch_id in self._commanded:
                self._commanded[switch_id] = position
        self._follow_runs(snap)

    def _t(self) -> float:
        return SIMULATION_START_S + self.now

    def _follow_runs(self, snap) -> None:
        mark = []
        for run in snap.scheduled_runs:
            if run.line != self.line:
                continue
            mark.append((run.train_id, run.status, run.stops_done))
            train = self.trains.get(run.train_id)
            if run.status == "dwelling" and run.train_id not in self._dwelling:
                self._dwelling[run.train_id] = (run.stop_block_id, self.now)
                self.result.stops.setdefault(run.train_id, []).append(
                    run.stop_block_id)
                if train is None or train.block != run.stop_block_id:
                    self.result.misplaced_dwells.append(
                        f"{clock(self._t())} {run.train_id} dwells at "
                        f"{run.stop_block_id} on "
                        f"{train.block if train else 'nothing'}")
            elif run.status != "dwelling":
                self._dwelling.pop(run.train_id, None)
        followed = {t.train_id: t.blocks[-1] for t in snap.trains
                    if t.line == self.line}
        for train_id, train in self.trains.items():
            head = followed.get(train_id)
            if head is not None and head != train.block:
                text = (f"the CTC follows {train_id} on {head}, it is on "
                        f"{train.block}")
                if not self.result.anomalies or \
                        self.result.anomalies[-1][9:] != text:
                    self.result.anomalies.append(
                        f"{clock(self._t())} {text}")
        mark_t = tuple(mark)
        if mark_t != self._progress_mark:
            self._progress_mark = mark_t
            self._progress()

    def _progress(self) -> None:
        self._last_progress = self.now

    # -- switches ----------------------------------------------------

    def _move_switches(self) -> None:
        for switch_id, wanted in self._commanded.items():
            if wanted == self.switches[switch_id]:
                self._moving_since.pop(switch_id, None)
                continue
            since = self._moving_since.setdefault(switch_id, self.now)
            if self.now - since >= self.switch_move_s - 1e-9:
                point = self._ctc_id[self._points[switch_id]]
                on = [t.train_id for t in self.trains.values()
                      if t.block == point]
                if on:
                    self.result.anomalies.append(
                        f"{clock(self._t())} switch {switch_id} moved to "
                        f"{wanted} under {on}")
                self.switches[switch_id] = wanted
                self._switch_version += 1
                del self._moving_since[switch_id]

    def _tm_switches(self) -> dict[str, TmPosition]:
        return {self._points[s]: (TmPosition.REVERSE if p == "reverse"
                                  else TmPosition.NORMAL)
                for s, p in self.switches.items()}

    def _next(self, block: str, came_from: str) -> str | None:
        """Where the rails lead from ``block``: a block, None for the
        yard, or ``block`` itself at a dead end."""
        tm_from = came_from if came_from == YARD else self._tm[came_from]
        nxt = self.layout.next_block(self._tm[block], tm_from,
                                     self._tm_switches())
        return None if nxt is None else self._ctc_id[nxt]

    # -- trains ------------------------------------------------------

    def _ahead(self, train: Train, count: int) -> tuple[list[str], float]:
        """The blocks the rails lead to next, up to ``count`` of them,
        with the switches as they are, and their total length."""
        key = (train.block, train.came_from, count, self._switch_version)
        found = self._ahead_cache.get(key)
        if found is None:
            blocks = []
            here, came = train.block, train.came_from
            for _ in range(count):
                nxt = self._next(here, came)
                if nxt is None or nxt == here:
                    break
                blocks.append(nxt)
                here, came = nxt, here
            found = (blocks, sum(self.lengths[b] for b in blocks))
            self._ahead_cache[key] = found
        return found

    def _stop_speed(self, train: Train, auth: int, ceiling: float) -> float:
        """The fastest the lookahead controller lets the train go, up to
        ``ceiling``: what it can stop from at the end of its authority
        after coasting its reaction time and one tick."""
        blocks, beyond = self._ahead(train, auth)
        here = self.lengths[train.block] - train.pos_m
        # It aims to stop ``STOP_SHORT_M`` short of the end: a train
        # standing at the very end is still in its block.
        total = here + beyond - STOP_SHORT_M
        late = self.reaction_s + self.dt
        slowest = min([self._brake(train.block)]
                      + [self._brake(b) for b in blocks])
        if total >= ceiling * ceiling / (2 * slowest) + ceiling * late + 1:
            return ceiling      # the end of authority is far off
        segments = [(here, self._brake(train.block))]
        segments += [(self.lengths[b], self._brake(b)) for b in blocks]
        short = STOP_SHORT_M
        while short > 0 and segments:
            d, rate = segments.pop()
            if d > short:
                segments.append((d - short, rate))
            short -= d

        def can_stop_from(distance: float) -> float:
            # v^2 a full stop takes over the last ``distance`` metres.
            v2, left = 0.0, distance
            for d, rate in reversed(segments):
                use = min(d, left)
                v2 += 2 * rate * use
                left -= use
                if left <= 0:
                    break
            return math.sqrt(max(0.0, v2))

        v = can_stop_from(total)
        for _ in range(6):
            v = can_stop_from(max(0.0, total - v * late))
        return min(ceiling, v) if total > 0.0 else 0.0

    def _drive(self, train: Train) -> None:
        circuit = self.circuits.get(train.block, (0, 0))
        speed_cmd, auth = circuit
        v = train.speed_mps
        if self.controller == "speed":
            # Train-Ctrl_HW's law (``train_ctrl/control.py``): the
            # commanded speed is the target, and no authority is a stop.
            target = float(speed_cmd) if auth > 0 else 0.0
        elif v == 0.0 and speed_cmd == 0:
            target = 0.0
        else:
            target = self._stop_speed(train, auth, float(speed_cmd))
        if v > target + 1e-6:
            # The brake comes on ``reaction_s`` after it is first wanted;
            # this tick runs from ``now - dt``.
            if train.brake_wanted_since is None:
                train.brake_wanted_since = self.now - self.dt
            if (self.now - self.dt - train.brake_wanted_since
                    >= self.reaction_s - 1e-9):
                v = max(target if self.controller == "speed" else 0.0,
                        v - self._brake(train.block) * self.dt)
        else:
            train.brake_wanted_since = None
            if v < target:
                v = min(target, v + self.accel * self.dt)
        train.pos_m += (train.speed_mps + v) / 2 * self.dt
        train.speed_mps = v
        while train.pos_m > self.lengths[train.block] + 1e-6:
            if not self._enter_next(train, circuit):
                break
            circuit = self.circuits.get(train.block, (0, 0))
        self._note_stand(train)

    def _enter_next(self, train: Train, circuit: tuple[int, int]) -> bool:
        here = train.block
        nxt = self._next(here, train.came_from)
        if nxt is None or nxt == here:
            self.result.anomalies.append(
                f"{clock(self._t())} {train.train_id} reached "
                f"{'the yard' if nxt is None else 'a dead end'} from {here}")
            train.pos_m = self.lengths[here]
            train.speed_mps = 0.0
            return False
        if circuit[1] < 1:
            self.result.overruns.append(Overrun(
                self._t(), train.train_id, here, nxt, train.speed_mps,
                circuit, self.suggested.get(here),
                self._authority_text.get(train.train_id, "none")))
        limit = getattr(self, "_limits", {}).get(train.train_id)
        if limit is not None and len(limit.route) > 1 \
                and limit.route[0] == here and limit.route[1] != nxt:
            self.result.misroutes.append(
                f"{clock(self._t())} {train.train_id} {here}->{nxt}, "
                f"routed to {limit.route[1]}")
        switch = self._legs.get(self._tm[nxt])
        if switch is not None:
            legs = {switch.normal_block_id: "normal",
                    switch.reverse_block_id: "reverse"}
            tm_here = self._tm[here]
            if tm_here in legs:
                switch_id = next(s for s, p in self._points.items()
                                 if p == self._tm[nxt])
                if self.switches[switch_id] != legs[tm_here]:
                    self.result.trailed.append(
                        f"{clock(self._t())} {train.train_id} {here}->{nxt}"
                        f" through switch {switch_id} set "
                        f"{self.switches[switch_id]}")
        for other in self.trains.values():
            if other is not train and other.block == nxt:
                self.result.collisions.append(
                    f"{clock(self._t())} {train.train_id} {here}->{nxt} "
                    f"onto {other.train_id}")
        train.pos_m -= self.lengths[here]
        train.came_from, train.block = here, nxt
        self._progress()
        return True

    # -- what is recorded --------------------------------------------

    def _held(self, block: str) -> bool:
        """The wayside zeroes the CTC's suggestion for a block."""
        suggested = self.suggested.get(block)
        return (suggested is not None and suggested != (0, 0)
                and self.circuits.get(block, (0, 0)) == (0, 0))

    def _watch(self) -> None:
        standing = {t.train_id: t for t in self.trains.values()
                    if t.speed_mps <= 1e-6}
        seen = set()
        ids = sorted(standing)
        for i, a in enumerate(ids):
            for b in ids[i + 1:]:
                ta, tb = standing[a], standing[b]
                if tb.block not in self.neighbours[ta.block]:
                    continue
                key = (a, b)
                seen.add(key)
                since = self._adjacent_since.setdefault(key, self.now)
                if (self.now - since >= self.freeze_s
                        and key not in self._open_freezes):
                    self._open_freezes[key] = Freeze(
                        SIMULATION_START_S + since, a, ta.block, b, tb.block,
                        self._why(ta), self._why(tb))
        for key in list(self._adjacent_since):
            if key not in seen:
                del self._adjacent_since[key]
                freeze = self._open_freezes.pop(key, None)
                if freeze is not None:
                    freeze.end_s = self._t()
                    self.result.freezes.append(freeze)

    def _why(self, train: Train) -> str:
        text = self._authority_text.get(train.train_id, "no authority")
        if self._held(train.block):
            text += f"; wayside zeroes {self.suggested.get(train.block)}"
        return text

    def _note_stand(self, train: Train) -> None:
        if train.speed_mps <= 1e-6:
            if train.stood_since is None:
                train.stood_since = self.now
                train.stood_why = ""
            if not train.stood_why and self.now - train.stood_since > 5:
                train.stood_why = self._why(train)
        else:
            self._end_wait(train)

    def _end_wait(self, train: Train) -> None:
        if train.stood_since is None:
            return
        seconds = self.now - train.stood_since
        dwelt = train.train_id in self._dwelling
        if seconds >= 60 and not (dwelt and seconds < 120):
            self.result.waits.append(Wait(
                train.train_id, train.block,
                SIMULATION_START_S + train.stood_since, seconds,
                train.stood_why or self._why(train)))
        train.stood_since = None

    def _close_waits(self) -> None:
        for train in self.trains.values():
            self._end_wait(train)

    def _describe(self) -> list[str]:
        """What every train on the line is doing, and waiting for."""
        lines = [f"nothing moved since {clock(SIMULATION_START_S + self._last_progress)}"]
        runs = {r.train_id: r for r in self._snap.scheduled_runs}
        for train in sorted(self.trains.values(),
                            key=lambda t: int(t.train_id[1:])):
            run = runs.get(train.train_id)
            status = (f"{run.status}, next stop {run.stop_block_id}"
                      if run else "no run")
            lines.append(
                f"{train.train_id} on {train.block} "
                f"({train.pos_m:.0f}/{self.lengths[train.block]:.0f} m, "
                f"{train.speed_mps:.1f} m/s) circuit "
                f"{self.circuits.get(train.block, (0, 0))}, suggested "
                f"{self.suggested.get(train.block)}, CTC authority "
                f"{self._authority_text.get(train.train_id, 'none')}; "
                f"{status}")
        waiting = [r.train_id for r in self._snap.scheduled_runs
                   if r.line == self.line and r.train_id not in self.trains
                   and r.status != "done"]
        if waiting:
            lines.append(f"not out: {', '.join(waiting)}")
        lines.append("switches " + ", ".join(
            f"{s} {p}" for s, p in sorted(self.switches.items(),
                                          key=lambda i: int(i[0]))))
        return lines


def schedule_office(line: str, schedule=None) -> StubCtcOffice:
    """A ready CTC Office in automatic mode with ``line``'s runs of
    ``schedule`` (default ``utils/schedule_v4.json``) loaded."""
    from ctc.schedule import Schedule, load_schedule
    from tests.occupancy import ready_office
    if schedule is None:
        schedule = load_schedule(_REPO / "utils" / "schedule_v4.json")
    runs = tuple(t for t in schedule.trains if t.line == line)
    ctc = ready_office()
    ctc.load_schedule(Schedule(f"{line} runs", runs))
    ctc.set_automatic_mode(True)
    return ctc


def run_line(line: str, **options) -> Result:
    """The whole of ``line``'s schedule_v4 on a realistic railway."""
    max_s = options.pop("max_s", 8 * 3600)
    railway = RealisticRailway(schedule_office(line), line, **options)
    return railway.run(max_s)
