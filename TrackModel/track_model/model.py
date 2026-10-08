"""Track Model implementation.

One ``step`` per tick, in this order (see ``step``):

1. Validate the whole input; reject it before anything changes.
2. Store the Track Controller's commands.
3. Work out each device's actual state: what was commanded, unless a
   failure overrides it.
4. Warm or cool each section's track toward its target temperature.
5. Move trains across block boundaries from their reported offsets.
6. Sell tickets, board passengers, and build every output.

Failures have fail-safe effects:

- Any failure (broken rail, track circuit, power): the block reads as
  occupied, and its track circuit carries nothing, so a train in it gets
  0 m/s and no authority.
- Power failure, in addition: the block's switch stays where it is, its
  signal light shows RED, its crossing gates go down, and its section's
  heaters turn off.

Values marked PROVISIONAL are stand-ins for open questions, listed in
``TrackModel/README.md``.
"""

from __future__ import annotations

import dataclasses
import math
import random
from collections.abc import Mapping
from dataclasses import dataclass

from track_model.interface import (
    Block,
    BlockEdit,
    InvalidInputError,
    SignalAspect,
    SwitchPosition,
    TrackConfig,
    TrackControllerCommands,
    TrackControllerOutputs,
    TrackFailure,
    TrackInfo,
    TrackModelInputs,
    TrackModelOutputs,
    TrackModelSnapshot,
    TrackSignal,
    TrainFeed,
    TrainReport,
    TrainView,
    UnknownIdError,
    is_finite,
    is_whole,
)
from track_model.layout import YARD, Layout, load_layout

#: Safe state for a light nobody has commanded yet, or with no power.
DEFAULT_ASPECT = SignalAspect.RED
#: PROVISIONAL: the Track Model never learns door state, so a train
#: counts as stopped at a station when its speed is exactly zero.
STOPPED_SPEED_MPS = 0.0
#: PROVISIONAL: how far running heaters hold a section's track above
#: ambient, once warmed up.
HEATER_RISE_C = 10.0
#: PROVISIONAL: how quickly track temperature follows its target. After
#: one time constant it has closed about 63% of the gap.
TRACK_TIME_CONSTANT_S = 300.0
#: Failures that cut the block's track circuit.
CIRCUIT_DEAD = frozenset({
    TrackFailure.BROKEN_RAIL, TrackFailure.TRACK_CIRCUIT, TrackFailure.POWER,
})


@dataclass(slots=True)
class _Train:
    """What the Track Model tracks for one train between ticks."""

    block_id: str
    # Behind the train in its forward direction; YARD if it came out of
    # the yard; None if unknown.
    previous_block_id: str | None
    polarity: bool
    offset_m: float = 0.0
    actual_speed_mps: float = 0.0
    entered_this_tick: bool = True
    # The block it last moved out of, either way. A report naming it is
    # stale: the Train Model has not yet seen the new Track Info.
    left_block_id: str | None = None


class TrackModel:
    """The Track Model. Constructed as ``TrackModel(config)``."""

    # State, set by _restart(). "_cmd" is what the Track Controller last
    # commanded; the matching name without it is the device's actual
    # state, which a failure can override.
    _blocks: dict[str, Block]
    _signal_set: set[str]
    _switch_cmd: dict[str, SwitchPosition]
    _switches: dict[str, SwitchPosition]
    _crossing_cmd: dict[str, bool]
    _signal_cmd: dict[str, SignalAspect]
    _heater_cmd: dict[str, bool]                 # by section
    _track_temp_c: dict[str, float]              # by section
    _temps_started: bool
    _failures: dict[str, TrackFailure]
    _commanded_speed: dict[str, int]
    _authority: dict[str, str]
    _trains: dict[str, _Train]
    _waiting: dict[str, int]
    _last_sales: dict[str, int]
    _rng: random.Random
    _ambient_temp_c: float
    _elapsed_s: float
    _outputs: TrackModelOutputs

    def __init__(self, config: TrackConfig) -> None:
        """Load the layout and start with every device at rest."""
        self.config = config
        self._layout: Layout = load_layout(config.layout_paths)
        self._sections: dict[str, list[str]] = {}
        for block in self._layout.blocks.values():
            self._sections.setdefault(block.section_id, []).append(
                block.block_id
            )
        self._restart()

    # ------------------------------------------------------------------ #
    # Protocol
    # ------------------------------------------------------------------ #

    def step(self, dt: float, inputs: TrackModelInputs) -> TrackModelOutputs:
        """Advance one tick. Rejects invalid input before changing state."""
        self._validate(dt, inputs)
        self._elapsed_s += dt
        self._apply_commands(inputs.controller)
        self._ambient_temp_c = inputs.ambient_temp_c
        self._update_track_temps(dt)
        self._move_trains(inputs.trains)
        self._last_sales = self._sell_tickets()
        # A train that ran into the yard this tick gets no feed.
        feeds = {
            train_id: self._feed(self._trains[train_id], report)
            for train_id, report in inputs.trains.items()
            if train_id in self._trains
        }
        self._outputs = TrackModelOutputs(
            controller=self._controller_outputs(),
            train_feeds=feeds,
            signal_seen={
                train_id: self._signal_seen(train)
                for train_id, train in self._trains.items()
            },
        )
        return self._outputs

    def snapshot(self) -> TrackModelSnapshot:
        """Return the current state for display. No side effects."""
        return TrackModelSnapshot(
            blocks=tuple(self._blocks.values()),
            switches=tuple(self._layout.switches.values()),
            signal_block_ids=self._layout.signal_block_ids,
            beacons=self._layout.beacons,
            trains=tuple(
                TrainView(
                    train_id=train_id,
                    block_id=train.block_id,
                    previous_block_id=train.previous_block_id,
                    offset_m=train.offset_m,
                    actual_speed_mps=train.actual_speed_mps,
                    polarity=train.polarity,
                )
                for train_id, train in self._trains.items()
            ),
            waiting_passengers=dict(self._waiting),
            ambient_temp_c=self._ambient_temp_c,
            elapsed_s=self._elapsed_s,
            outputs=self._outputs,
        )

    def set_block_failure(self, block_id: str, failure: TrackFailure) -> None:
        """Inject or clear a failure. Reported at once, between steps.

        The Track Controller read-back (occupancy, lights, gates,
        heaters) changes immediately; a train in the block feels it from
        the next step, when its feed is next built.
        """
        self._require_block(block_id)
        self._failures[block_id] = failure
        self._outputs = dataclasses.replace(
            self._outputs, controller=self._controller_outputs()
        )

    def edit_block(self, block_id: str, edit: BlockEdit) -> None:
        """Test only: override a block's loaded stats."""
        self._require_block(block_id)
        if not all(v is None or is_finite(v) for v in edit.values()):
            raise InvalidInputError(f"non-finite edit for {block_id}")
        if edit.length_m is not None and edit.length_m <= 0:
            raise InvalidInputError(f"length must be positive: {block_id}")
        changes = {
            name: value
            for name, value in dataclasses.asdict(edit).items()
            if value is not None
        }
        self._blocks[block_id] = dataclasses.replace(
            self._blocks[block_id], **changes
        )

    def reset(self) -> None:
        """Test only: return to the freshly loaded state."""
        self._restart()

    # ------------------------------------------------------------------ #
    # Devices and failures
    # ------------------------------------------------------------------ #

    def _apply_commands(self, commands: TrackControllerCommands) -> None:
        # Store commands; absent keys keep their last value. A switch
        # only moves to its command while its block has power.
        self._commanded_speed.update(commands.commanded_speed_mps)
        self._authority.update(commands.commanded_authority)
        self._switch_cmd.update(commands.switch_commands)
        self._crossing_cmd.update(commands.crossing_commands)
        self._signal_cmd.update(commands.signal_commands)
        self._heater_cmd.update(commands.heater_commands)
        for switch_id, position in self._switch_cmd.items():
            if not self._powered_off(switch_id):
                self._switches[switch_id] = position

    def _powered_off(self, block_id: str) -> bool:
        # Whether this block has a power failure.
        return self._failures[block_id] is TrackFailure.POWER

    def _circuit_dead(self, block_id: str) -> bool:
        # Whether this block's track circuit is out.
        return self._failures[block_id] in CIRCUIT_DEAD

    def _signal_state(self, block_id: str) -> SignalAspect:
        # The colour a light actually shows: RED without power.
        if self._powered_off(block_id):
            return DEFAULT_ASPECT
        return self._signal_cmd[block_id]

    def _gate_closed(self, block_id: str) -> bool:
        # Gates go down without power (fail-safe).
        return self._powered_off(block_id) or self._crossing_cmd[block_id]

    def _heater_on(self, section_id: str) -> bool:
        # A section's heaters run if commanded and none of its blocks
        # has lost power.
        return self._heater_cmd[section_id] and not any(
            self._powered_off(b) for b in self._sections[section_id]
        )

    def _update_track_temps(self, dt: float) -> None:
        # Each section's track temperature moves toward ambient, plus
        # HEATER_RISE_C while its heaters run. Ambient itself is input.
        if not self._temps_started:
            self._track_temp_c = {
                s: self._ambient_temp_c for s in self._sections
            }
            self._temps_started = True
        share = 1.0 - math.exp(-dt / TRACK_TIME_CONSTANT_S)
        for section_id, temp in self._track_temp_c.items():
            target = self._ambient_temp_c + (
                HEATER_RISE_C if self._heater_on(section_id) else 0.0
            )
            self._track_temp_c[section_id] = temp + (target - temp) * share

    # ------------------------------------------------------------------ #
    # Trains
    # ------------------------------------------------------------------ #

    def _move_trains(self, reports: Mapping[str, TrainReport]) -> None:
        # Place, advance or drop each train from its Train Model report.
        for train_id in list(self._trains):
            if train_id not in reports:
                del self._trains[train_id]
        for train_id, report in reports.items():
            train = self._trains.get(train_id)
            if train is None or report.block_id not in (
                train.block_id, train.left_block_id
            ):
                # New train, or placed by the test UI. One placed where
                # the yard joins the line has come out of the yard.
                switch = self._layout.switches.get(report.block_id)
                came_from = (
                    YARD if switch is not None and switch.from_yard else None
                )
                train = _Train(report.block_id, came_from, polarity=False)
                self._trains[train_id] = train
            else:
                train.entered_this_tick = False
            train.offset_m = report.offset_m
            train.actual_speed_mps = report.actual_speed_mps
            if report.block_id != train.block_id:
                # Stale report from the block this train just left: the
                # Train Model has not seen the new Track Info yet.
                continue
            self._advance(train_id, train, report.offset_m)

    def _advance(self, train_id: str, train: _Train, offset_m: float) -> None:
        # Move one train across a block boundary if its offset says so.
        # previous_block_id is the block behind the train in its forward
        # direction, so it stays correct through a run of rollbacks.
        length = self._blocks[train.block_id].length_m
        old = train.block_id
        if offset_m >= length:
            target = self._layout.next_block(
                old, train.previous_block_id, self._switches
            )
            behind: str | None = old
        elif offset_m < 0.0:
            target = self._layout.previous_block(old, train.previous_block_id)
            behind = None if target == old else self._behind(target, old)
        else:
            return
        if target is None:
            # Rails lead into the yard: the train leaves the track.
            del self._trains[train_id]
            return
        if target == old:
            return  # Dead end; the train stays where it is.
        train.previous_block_id = behind
        train.left_block_id = old
        train.block_id = target
        train.polarity = not train.polarity
        train.entered_this_tick = True

    def _behind(self, block_id: str, ahead: str) -> str | None:
        # The block beyond block_id on the side away from ahead, following
        # the switches as set; YARD where the rails lead into the yard,
        # None at a dead end.
        beyond = self._layout.next_block(block_id, ahead, self._switches)
        if beyond is None:
            return YARD
        return None if beyond == block_id else beyond

    # ------------------------------------------------------------------ #
    # Stations
    # ------------------------------------------------------------------ #

    def _sell_tickets(self) -> dict[str, int]:
        # Each station rolls for one new ticket per tick.
        sales: dict[str, int] = {}
        for station in self._waiting:
            sold = int(self._rng.random() < self.config.ticket_probability)
            self._waiting[station] += sold
            sales[station] = sold
        return sales

    def _board(self, block: Block, report: TrainReport) -> int:
        # PROVISIONAL: board while stopped in a station block.
        station = block.station_name
        if station is None or report.actual_speed_mps != STOPPED_SPEED_MPS:
            return 0
        boarded = min(self._waiting.get(station, 0), report.passenger_capacity)
        self._waiting[station] -= boarded
        return boarded

    # ------------------------------------------------------------------ #
    # Outputs
    # ------------------------------------------------------------------ #

    def _feed(self, train: _Train, report: TrainReport) -> TrainFeed:
        # Everything one train receives from the track this tick.
        block = self._blocks[train.block_id]
        if self._circuit_dead(block.block_id):
            # A dead track circuit carries no speed and no authority.
            signal = TrackSignal(commanded_speed_mps=0,
                                 authority_block_id=None)
        else:
            # The track circuit of the occupied block: both per block.
            signal = TrackSignal(
                commanded_speed_mps=self._commanded_speed.get(
                    block.block_id, 0
                ),
                authority_block_id=self._authority.get(block.block_id),
            )
        return TrainFeed(
            track_info=TrackInfo(
                block_id=block.block_id,
                grade_deg=block.grade_deg,
                elevation_m=block.elevation_m,
                speed_limit_mps=block.speed_limit_mps,
                polarity=train.polarity,
                station_name=block.station_name,
            ),
            track_signal=signal,
            beacon=self._layout.beacons.get(block.block_id),
            passengers_boarded=self._board(block, report),
        )

    def _signal_seen(self, train: _Train) -> SignalAspect | None:
        # A train sees a light once, on the tick it enters that block.
        if not train.entered_this_tick:
            return None
        if train.block_id not in self._signal_set:
            return None
        return self._signal_state(train.block_id)

    def _controller_outputs(self) -> TrackControllerOutputs:
        # Everything the Track Controller reads back: actual states.
        occupied = {train.block_id for train in self._trains.values()}
        return TrackControllerOutputs(
            block_occupancy={
                b: b in occupied or self._circuit_dead(b)
                for b in self._blocks
            },
            switch_states=dict(self._switches),
            crossing_states={
                b: self._gate_closed(b) for b in self._crossing_cmd
            },
            signal_states={
                b: self._signal_state(b) for b in self._signal_cmd
            },
            failure_status=dict(self._failures),
            heater_states={s: self._heater_on(s) for s in self._heater_cmd},
            ticket_sales=dict(self._last_sales),
            track_temp_c=dict(self._track_temp_c),
        )

    # ------------------------------------------------------------------ #
    # Validation and setup
    # ------------------------------------------------------------------ #

    def _validate(self, dt: float, inputs: TrackModelInputs) -> None:
        # Reject the whole tick before any state changes.
        if not is_finite(dt) or dt <= 0.0:
            raise InvalidInputError(f"dt must be finite and positive: {dt}")
        if not is_finite(inputs.ambient_temp_c):
            raise InvalidInputError("ambient temperature is not finite")
        cmd = inputs.controller
        for block_id, speed in cmd.commanded_speed_mps.items():
            self._require_block(block_id)
            if not is_whole(speed) or speed < 0:
                raise InvalidInputError(
                    f"commanded speed for {block_id} must be a whole, "
                    f"non-negative m/s: {speed!r}"
                )
        for block_id, authority in cmd.commanded_authority.items():
            self._require_block(block_id)
            self._require_block(authority)
        self._require_ids(cmd.switch_commands, self._switch_cmd, "switch")
        self._require_ids(cmd.crossing_commands, self._crossing_cmd,
                          "crossing")
        self._require_ids(cmd.signal_commands, self._signal_set, "signal")
        self._require_ids(cmd.heater_commands, self._heater_cmd,
                          "heater section")
        for train_id, report in inputs.trains.items():
            self._require_block(report.block_id)
            if not (is_finite(report.offset_m)
                    and is_finite(report.actual_speed_mps)):
                raise InvalidInputError(f"non-finite report for {train_id}")
            if report.passenger_capacity < 0:
                raise InvalidInputError(f"negative capacity for {train_id}")

    def _require_block(self, block_id: str) -> None:
        # Raise if the block is not in the loaded layout.
        if block_id not in self._blocks:
            raise UnknownIdError(f"unknown block {block_id!r}")

    @staticmethod
    def _require_ids(
        given: Mapping[str, object], known: Mapping[str, object] | set[str],
        kind: str,
    ) -> None:
        # Raise if a command names a device that does not exist.
        for device_id in given:
            if device_id not in known:
                raise UnknownIdError(f"unknown {kind} {device_id!r}")

    def _restart(self) -> None:
        # Fresh state: every device at its safe default, no trains.
        layout = self._layout
        self._blocks = dict(layout.blocks)
        self._signal_set = set(layout.signal_block_ids)
        self._switch_cmd = {
            switch_id: SwitchPosition.NORMAL for switch_id in layout.switches
        }
        self._switches = dict(self._switch_cmd)
        self._crossing_cmd = {
            b.block_id: False for b in self._blocks.values() if b.has_crossing
        }
        self._signal_cmd = {
            block_id: DEFAULT_ASPECT for block_id in layout.signal_block_ids
        }
        self._heater_cmd = {s: False for s in self._sections}
        self._track_temp_c = {s: 0.0 for s in self._sections}
        self._temps_started = False
        self._failures = {
            block_id: TrackFailure.NONE for block_id in self._blocks
        }
        self._commanded_speed = {}
        self._authority = {}
        self._trains = {}
        self._waiting = {
            b.station_name: 0
            for b in self._blocks.values() if b.station_name is not None
        }
        self._last_sales = {}
        self._rng = random.Random(self.config.seed)
        self._ambient_temp_c = 0.0
        self._elapsed_s = 0.0
        self._outputs = TrackModelOutputs(
            controller=self._controller_outputs(),
            train_feeds={},
            signal_seen={},
        )
