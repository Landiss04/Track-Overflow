"""How the harness builds every module's inputs, as integrated so far.

``SystemEdges`` gives the modules wired in their real edges (D005), and
gives every module still a stub its producers' outputs whole
(``stub_edges``). Phase 1 wired in the Train Model and the Train
Controller SW, Phase 2 the Track Model, and Phase 3 the Track
Controller SW, which runs the Green Line (R77):

- A scripted CTC Office (``ctc_script``) stands in for the CTC
  Office's dispatch and suggestions until Phase 4. It reads what the
  CTC Office reads from the Track Controller (occupancy and each
  wayside's readiness), and answers in the CTC Office's form. The CTC
  Office's stub still runs the clock.
- Nothing runs until a person has loaded a PLC program on every
  wayside (R44, R70): until each line's waysides are ready, the
  stand-in releases no train and sends nothing. The clock runs on. The
  harness logs each line's readiness as it changes.
- The trains in service are a roster (``roster``, D022) that the CTC
  Office's ``new_trains`` and ``retired_trains`` keep: the stand-in's,
  and its stub's.
- A released train enters at its line's yard exit block (D022). It
  joins the Track Model first, which places it there from a stand-in
  report (``track_edges.placement_report``) until its Train Model
  reports it. It joins its Train Model once the Track Model feeds it,
  and its Train Controller, chosen by line (D021), once the Train
  Model reports it: each needs that input on every tick. Until its
  first commands arrive, the Train Model holds the train
  (``train_edges.INERT_COMMANDS``).
- The Track Controller takes the stand-in's suggestions and the Track
  Model's occupancy and device read-back; the Track Model takes the
  Track Controller's per-block commands, switches, crossings and
  lights, and each train's Train Model report (``wayside_edges``,
  ``track_edges``). Each train's Train Model takes its Track Model
  feed and its Train Controller's commands; each Train Controller
  takes its Train Model's outputs and the light the Track Model showed
  it (``track_edges``, ``train_edges``).
- The stand-in steps once per tick on the Track Controller's outputs
  of the tick before, and its outputs reach the Track Controller on
  the next tick, just as a module's would (R1).
- A train the Track Model stops feeding has left the track: it ran
  into the yard. It leaves every input, and the harness logs it, but
  it stays on the roster until the CTC Office retires it.
- A train the Train Model rejects on a tick is logged as the Train
  Model's ``TICK_REJECTED``, naming the train.

Every train's inputs to the Train Model and the Train Controller are
keyed by train ID under ``trains``, with its line, as their processes
expect (``train_model.module_process``, ``train_ctrl.module_process``).
The Track Model's and the Track Controller's are their own
(``track_model.wire``, ``track_ctrl.wire``).
"""

from __future__ import annotations

__all__ = ["CONTROLLER_FOR_LINE", "TRACK_CONTROLLER_FOR_LINE", "SystemEdges"]

from collections.abc import Collection, Mapping
from typing import Any

from common.harness.ctc_script import ScriptedCtc
from common.harness.modules import (
    CTC_OFFICE,
    TRACK_CONTROLLER_HW,
    TRACK_CONTROLLER_SW,
    TRACK_MODEL,
    TRAIN_CONTROLLER_HW,
    TRAIN_CONTROLLER_SW,
    TRAIN_MODEL,
    WIRED_MODULES,
)
from common.harness.roster import Event, Roster
from common.harness.stub_edges import stub_inputs
from common.harness.track_devices import TrackDevices
from common.harness.track_edges import (
    YARD_EXIT_BLOCKS,
    BlockNames,
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
from common.harness.wayside_edges import (
    ctc_to_track_controller,
    line_ready,
    track_controller_to_ctc,
    track_controller_to_track_model,
    track_model_to_track_controller,
)

#: The Train Controller each line's trains run on (D021).
CONTROLLER_FOR_LINE: Mapping[str, str] = {
    "Green": TRAIN_CONTROLLER_SW,
    "Red": TRAIN_CONTROLLER_HW,
}

#: The Track Controller that runs each line (R77, D021).
TRACK_CONTROLLER_FOR_LINE: Mapping[str, str] = {
    "Green": TRACK_CONTROLLER_SW,
    "Red": TRACK_CONTROLLER_HW,
}

HARNESS = "harness"

# A Track Controller's inputs before its producers have replied.
_NO_CTC: Mapping[str, Any] = {
    "closed_blocks": [], "switch_commands": [], "suggestions": [],
}
_NO_TRACK_MODEL: Mapping[str, Any] = {
    "occupied_blocks": [], "switch_positions": [], "crossings_active": [],
    "signal_aspects": [],
}


class SystemEdges:
    """Real edges into the modules wired in, stub edges for the rest."""

    def __init__(
        self,
        ctc: ScriptedCtc,
        wired: Collection[str] = WIRED_MODULES,
        devices: TrackDevices | None = None,
    ) -> None:
        """Prepare the edges, with no train in service.

        Args:
            ctc: The CTC Office's stand-in.
            wired: The modules that are real, not stubs.
            devices: Where each switch and light stands; read from the
                layout files if None.
        """
        self._ctc = ctc
        self._wired = frozenset(wired)
        self._devices = TrackDevices.load() if devices is None else devices
        self._roster = Roster(CTC_OFFICE)
        self._names = BlockNames()
        # The Track Controllers' outputs as of the tick before, which
        # the stand-in steps on, and its outputs, for the next tick.
        self._track_controllers: dict[str, Mapping[str, Any]] = {}
        self._ctc_outputs: Mapping[str, Any] = {}
        # Each line's readiness as last logged.
        self._ready: dict[str, bool] = {}
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

        Applies the CTC Office's train events, steps the CTC Office's
        stand-in and applies its own, and follows the trains on the
        track.

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
        rejected = fresh.get(TRAIN_MODEL, {}).get("rejected", {})
        if TRAIN_MODEL in self._wired and isinstance(rejected, Mapping):
            events += [
                (TRAIN_MODEL, "TICK_REJECTED", f"{train_id}: {reason}")
                for train_id, reason in rejected.items()
            ]
        # The stand-in steps on what the Track Controller reported the
        # tick before, as the CTC Office would.
        events += self._step_ctc(sim_time_s)
        in_service = {entry.train_id for entry in self._roster}
        self._on_track &= in_service
        self._off_track &= in_service
        for name in TRACK_CONTROLLER_FOR_LINE.values():
            if name in fresh and name in self._wired:
                self._track_controllers[name] = fresh[name]
        if TRACK_MODEL in fresh:
            track_model = fresh[TRACK_MODEL]
            self._names.learn(_occupancy(track_model))
            events += self._follow_trains(_feeds(track_model))
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
        if consumer in TRACK_CONTROLLER_FOR_LINE.values():
            return self._track_controller_inputs(consumer, outputs)
        if consumer == TRAIN_MODEL:
            return self._train_model_inputs(outputs)
        if consumer in CONTROLLER_FOR_LINE.values():
            return self._train_controller_inputs(consumer, outputs)
        raise KeyError(f"no edges into {consumer} yet")

    def _step_ctc(self, sim_time_s: float) -> list[Event]:
        # The stand-in's outputs for the next tick, from what its line's
        # Track Controller reported: its readiness, logged as it
        # changes, and its occupancy. A train it releases joins the
        # roster now, as one the CTC Office released on this tick.
        line = self._ctc.line
        reported = self._track_controllers.get(
            TRACK_CONTROLLER_FOR_LINE[line]
        )
        inputs = {} if reported is None else track_controller_to_ctc(
            reported
        )
        events = self._readiness(line, inputs.get("waysides", []))
        self._ctc_outputs = self._ctc.step(sim_time_s, inputs)
        events += self._roster.apply(
            {"new_trains": self._ctc_outputs["new_trains"]}, sim_time_s
        )
        return events

    def _readiness(
        self, line: str, waysides: list[Mapping[str, Any]]
    ) -> list[Event]:
        # One event when a line's readiness changes, once its waysides
        # have reported: which are not ready, and why.
        if not any(each["line"] == line for each in waysides):
            return []
        ready = line_ready(waysides, line)
        if self._ready.get(line) == ready:
            return []
        self._ready[line] = ready
        source = TRACK_CONTROLLER_FOR_LINE[line]
        if ready:
            return [(source, "WAYSIDES_READY", line)]
        reasons: dict[str, list[str]] = {}
        for each in waysides:
            if each["line"] == line and not each["ready"]:
                reasons.setdefault(each["reason"], []).append(
                    each["wayside_id"]
                )
        detail = "; ".join(
            f"{', '.join(ids)}: {reason or 'not ready'}"
            for reason, ids in reasons.items()
        )
        return [(source, "WAYSIDES_NOT_READY", f"{line}: {detail}")]

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

    def _track_controller_inputs(
        self, consumer: str, outputs: Mapping[str, Mapping[str, Any]]
    ) -> dict[str, Any]:
        # The stand-in's suggestions for this Track Controller's line,
        # and what the Track Model reported of it.
        line = next(
            line for line, name in TRACK_CONTROLLER_FOR_LINE.items()
            if name == consumer
        )
        track_model = outputs.get(TRACK_MODEL)
        return {
            "ctc": (
                ctc_to_track_controller(self._ctc_outputs, line)
                if self._ctc_outputs else dict(_NO_CTC)
            ),
            "track_model": (
                track_model_to_track_controller(
                    track_model, line, self._names, self._devices
                )
                if track_model and TRACK_MODEL in self._wired
                else dict(_NO_TRACK_MODEL)
            ),
        }

    def _track_model_inputs(
        self, outputs: Mapping[str, Mapping[str, Any]]
    ) -> dict[str, Any]:
        # Every wired Track Controller's commands, and every train on
        # the track: its Train Model's report, or, until the Train
        # Model reports a block for it, the stand-in that places it at
        # the yard exit.
        controller: dict[str, dict[str, Any]] = {}
        for name in TRACK_CONTROLLER_FOR_LINE.values():
            commands = outputs.get(name)
            if name not in self._wired or not commands or not self._names:
                continue
            mapped = track_controller_to_track_model(
                commands, self._names, self._devices
            )
            for field, values in mapped.items():
                controller.setdefault(field, {}).update(values)
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
        return {"controller": controller, "trains": trains}

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
