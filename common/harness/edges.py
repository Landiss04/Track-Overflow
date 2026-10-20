"""How the harness builds every module's inputs, as integrated so far.

``SystemEdges`` gives the modules wired in their real edges (D005), and
gives every module still a stub its producers' outputs whole
(``stub_edges``). Phase 1 wired in the Train Model and the Train
Controller SW; Phase 2 adds the Track Model:

- The CTC Office's ``new_trains`` and ``retired_trains`` keep the
  roster (``roster``, D022). Until Phase 4 the CTC Office is a stub
  that releases trains on cue.
- A released train enters at its line's yard exit block (D022). It
  joins the Track Model first, which places it there from a stand-in
  report (``track_edges.placement_report``) until its Train Model
  reports it. It joins its Train Model once the Track Model feeds it,
  and its Train Controller, chosen by line (D021), once the Train
  Model reports it: each needs that input on every tick. Until its
  first commands arrive, the Train Model holds the train
  (``train_edges.INERT_COMMANDS``).
- The Track Model takes each train's Train Model report, and per-block
  commands from a scripted wayside (``wayside_script``), which stands
  in for the Track Controller until Phase 3. Each train's Train Model
  takes its Track Model feed and its Train Controller's commands; each
  Train Controller takes its Train Model's outputs and the light the
  Track Model showed it (``track_edges``, ``train_edges``).
- The wayside steps once per tick on the Track Model's outputs of the
  tick before, and its commands reach the Track Model on the next
  tick, just as a module's would (R1).
- A train the Track Model stops feeding has left the track: it ran
  into the yard. It leaves every input, and the harness logs it, but
  it stays on the roster until the CTC Office retires it.
- A train the Train Model rejects on a tick is logged as the Train
  Model's ``TICK_REJECTED``, naming the train.

Every train's inputs to the Train Model and the Train Controller are
keyed by train ID under ``trains``, with its line, as their processes
expect (``train_model.module_process``, ``train_ctrl.module_process``).
The Track Model's are its own (``track_model.wire``).
"""

from __future__ import annotations

__all__ = ["CONTROLLER_FOR_LINE", "SystemEdges"]

from collections.abc import Collection, Mapping
from typing import Any

from common.harness.modules import (
    CTC_OFFICE,
    TRACK_MODEL,
    TRAIN_CONTROLLER_HW,
    TRAIN_CONTROLLER_SW,
    TRAIN_MODEL,
    WIRED_MODULES,
)
from common.harness.roster import Event, Roster
from common.harness.stub_edges import stub_inputs
from common.harness.track_edges import (
    YARD_EXIT_BLOCKS,
    BlockNames,
    block_commands_to_track_model,
    placement_report,
    track_model_to_train_model,
    train_model_to_track_model,
)
from common.harness.train_edges import (
    INERT_COMMANDS,
    aspect_to_train_controller,
    train_controller_to_train_model,
    train_model_to_train_controller,
)
from common.harness.wayside_script import ScriptedWayside

#: The Train Controller each line's trains run on (D021).
CONTROLLER_FOR_LINE: Mapping[str, str] = {
    "Green": TRAIN_CONTROLLER_SW,
    "Red": TRAIN_CONTROLLER_HW,
}

HARNESS = "harness"


class SystemEdges:
    """Real edges into the modules wired in, stub edges for the rest."""

    def __init__(
        self,
        wayside: ScriptedWayside,
        wired: Collection[str] = WIRED_MODULES,
    ) -> None:
        """Prepare the edges, with no train in service.

        Args:
            wayside: The Track Controller's stand-in.
            wired: The modules that are real, not stubs.
        """
        self._wayside = wayside
        self._wired = frozenset(wired)
        self._roster = Roster(CTC_OFFICE)
        self._names = BlockNames()
        # The Track Model's outputs as of the tick before, which the
        # wayside steps on.
        self._track_model: Mapping[str, Any] = {}
        # The wayside's last commands, in the Track Model's form.
        self._wayside_commands: dict[str, dict[str, Any]] = {}
        # Trains the Track Model has fed, and those it fed and then
        # stopped feeding: they left the track.
        self._on_track: set[str] = set()
        self._off_track: set[str] = set()

    @property
    def roster(self) -> Roster:
        """The trains in service."""
        return self._roster

    @property
    def block_names(self) -> BlockNames:
        """The Track Model's block names, as learned so far."""
        return self._names

    def tick_completed(
        self,
        tick: int,
        sim_time_s: float,
        fresh: Mapping[str, Mapping[str, Any]],
    ) -> list[Event]:
        """Act on a tick's new outputs, once each.

        Applies the CTC Office's train events, steps the wayside, and
        follows the trains on the track.

        Args:
            tick: The tick that is over.
            sim_time_s: Its simulation time.
            fresh: The outputs each module replied with on it.

        Returns:
            Events to log.
        """
        events: list[Event] = []
        if CTC_OFFICE in fresh:
            events += self._roster.apply(fresh[CTC_OFFICE], sim_time_s)
            in_service = {entry.train_id for entry in self._roster}
            self._on_track &= in_service
            self._off_track &= in_service
        rejected = fresh.get(TRAIN_MODEL, {}).get("rejected", {})
        if TRAIN_MODEL in self._wired and isinstance(rejected, Mapping):
            events += [
                (TRAIN_MODEL, "TICK_REJECTED", f"{train_id}: {reason}")
                for train_id, reason in rejected.items()
            ]
        # The wayside steps on what the Track Model reported the tick
        # before, as the Track Controller would.
        self._wayside_commands = self._step_wayside(sim_time_s)
        if TRACK_MODEL in fresh:
            self._track_model = fresh[TRACK_MODEL]
            self._names.learn(_occupancy(self._track_model))
            events += self._follow_trains(_feeds(self._track_model))
        return events

    def inputs_for(
        self,
        consumer: str,
        tick: int,
        sim_time_s: float,
        outputs: Mapping[str, Mapping[str, Any]],
    ) -> dict[str, Any]:
        """Return one module's inputs for a tick.

        Raises:
            KeyError: If a producer's outputs lack a field its edge
                maps; the harness then skips the consumer this tick.
        """
        if consumer not in self._wired:
            return stub_inputs(consumer, outputs)
        if consumer == TRACK_MODEL:
            return self._track_model_inputs(outputs)
        if consumer == TRAIN_MODEL:
            return self._train_model_inputs(outputs)
        if consumer in CONTROLLER_FOR_LINE.values():
            return self._train_controller_inputs(consumer, outputs)
        raise KeyError(f"no edges into {consumer} yet")

    def _step_wayside(self, sim_time_s: float) -> dict[str, dict[str, Any]]:
        # The wayside's commands for its line, in the Track Model's
        # names; none until the Track Model's blocks are known.
        if not self._names:
            return {}
        line = self._wayside.line
        occupied = []
        for name, is_occupied in _occupancy(self._track_model).items():
            if not is_occupied:
                continue
            block = self._block(name)
            if block is not None and block[0] == line:
                occupied.append(block[1])
        commands = self._wayside.step(sim_time_s, occupied)
        return block_commands_to_track_model(commands, line, self._names)

    def _block(self, name: str) -> tuple[str, str] | None:
        # A Track Model block's line and number; None if not known.
        try:
            return self._names.block(name)
        except KeyError:
            return None

    def _follow_trains(self, feeds: Mapping[str, Any]) -> list[Event]:
        # Note each train the Track Model feeds; one it fed before and
        # feeds no more has left the track.
        events: list[Event] = []
        for entry in self._roster:
            train_id = entry.train_id
            if train_id in feeds:
                self._on_track.add(train_id)
            elif (train_id in self._on_track
                  and train_id not in self._off_track):
                self._off_track.add(train_id)
                events.append((HARNESS, "TRAIN_LEFT_TRACK", train_id))
        return events

    def _track_model_inputs(
        self, outputs: Mapping[str, Mapping[str, Any]]
    ) -> dict[str, Any]:
        # The wayside's commands, and every train on the track: its
        # Train Model's report, or, until the Train Model reports a
        # block for it, the stand-in that places it at the yard exit.
        reports = _trains(outputs.get(TRAIN_MODEL))
        trains = {}
        for entry in self._roster:
            train_id = entry.train_id
            if train_id in self._off_track or not self._names:
                continue
            report = reports.get(train_id)
            if report is None or not report["track"]["block_id"]:
                trains[train_id] = placement_report(
                    self._names.track_model_name(
                        entry.line, YARD_EXIT_BLOCKS[entry.line]
                    )
                )
            else:
                trains[train_id] = train_model_to_track_model(
                    report, entry.line, self._names
                )
        return {"controller": self._wayside_commands, "trains": trains}

    def _train_model_inputs(
        self, outputs: Mapping[str, Mapping[str, Any]]
    ) -> dict[str, Any]:
        # Every train the Track Model feeds: its feed, and its Train
        # Controller's last commands, or the inert ones before the
        # first.
        feeds = _feeds(outputs.get(TRACK_MODEL))
        commands: dict[str, Any] = {}
        for controller in CONTROLLER_FOR_LINE.values():
            commands.update(_trains(outputs.get(controller)))
        trains = {}
        for entry in self._roster:
            train_id = entry.train_id
            feed = feeds.get(train_id)
            if feed is None or train_id in self._off_track:
                continue
            train_commands = commands.get(train_id)
            trains[train_id] = {
                "line": entry.line,
                "controller": (
                    dict(INERT_COMMANDS) if train_commands is None
                    else train_controller_to_train_model(train_commands)
                ),
                "track": track_model_to_train_model(feed, self._names),
            }
        return {"trains": trains}

    def _train_controller_inputs(
        self, consumer: str, outputs: Mapping[str, Mapping[str, Any]]
    ) -> dict[str, Any]:
        # The trains on this controller's line that the Train Model has
        # reported: its outputs, and the light the train last saw.
        reports = _trains(outputs.get(TRAIN_MODEL))
        seen = (outputs.get(TRACK_MODEL) or {}).get("signal_seen") or {}
        trains = {}
        for entry in self._roster:
            train_id = entry.train_id
            report = reports.get(train_id)
            if (
                CONTROLLER_FOR_LINE[entry.line] != consumer
                or report is None
                or train_id in self._off_track
            ):
                continue
            inputs = train_model_to_train_controller(report["controller"])
            aspect = seen.get(train_id)
            if aspect is not None:
                inputs["signal_light_ahead"] = aspect_to_train_controller(
                    aspect
                )
            trains[train_id] = {"line": entry.line, "inputs": inputs}
        return {"trains": trains}


def _trains(outputs: Mapping[str, Any] | None) -> Mapping[str, Any]:
    # One module's outputs per train; none from a stub or before the
    # module's first reply.
    trains = (outputs or {}).get("trains")
    return trains if isinstance(trains, Mapping) else {}


def _feeds(outputs: Mapping[str, Any] | None) -> Mapping[str, Any]:
    # The Track Model's feed for each train on the track.
    feeds = (outputs or {}).get("train_feeds")
    return feeds if isinstance(feeds, Mapping) else {}


def _occupancy(outputs: Mapping[str, Any] | None) -> Mapping[str, Any]:
    # The Track Model's occupancy, by its block names.
    controller = (outputs or {}).get("controller")
    if not isinstance(controller, Mapping):
        return {}
    occupancy = controller.get("block_occupancy")
    return occupancy if isinstance(occupancy, Mapping) else {}
