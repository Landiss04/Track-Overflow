"""How the harness builds every module's inputs, as integrated so far.

``SystemEdges`` gives the modules wired in their real edges (D005), and
gives every module still a stub its producers' outputs whole
(``stub_edges``). Phase 1 wires in the Train Model and the Train
Controller SW:

- The CTC Office's ``new_trains`` and ``retired_trains`` keep the
  roster (``roster``, D022). Until Phase 4 the CTC Office is a stub
  that releases trains on cue.
- Each train's Train Model gets its Train Controller's last commands
  (``train_edges``) and its track from a fixed track feed
  (``track_feed``), which stands in for the Track Model until Phase 2.
- Each train's Train Controller, chosen by its line (D021), gets its
  Train Model's last outputs and the light ahead. It takes the train
  on once the Train Model has reported it, since it needs that report
  on every tick; until its first commands arrive, the Train Model
  holds the train (``train_edges.INERT_COMMANDS``).
- A train the Train Model rejects on a tick is logged as the Train
  Model's ``TICK_REJECTED``, naming the train.

Every train's inputs are keyed by train ID under ``trains``, with its
line, as the module processes expect
(``train_model.module_process``, ``train_ctrl.module_process``).
"""

from __future__ import annotations

__all__ = ["CONTROLLER_FOR_LINE", "SystemEdges"]

from collections.abc import Collection, Mapping
from typing import Any

from common.harness.modules import (
    CTC_OFFICE,
    TRAIN_CONTROLLER_HW,
    TRAIN_CONTROLLER_SW,
    TRAIN_MODEL,
    WIRED_MODULES,
)
from common.harness.roster import Event, Roster
from common.harness.stub_edges import stub_inputs
from common.harness.track_feed import FixedTrackFeed
from common.harness.train_edges import (
    INERT_COMMANDS,
    aspect_to_train_controller,
    train_controller_to_train_model,
    train_model_to_train_controller,
)

#: The Train Controller each line's trains run on (D021).
CONTROLLER_FOR_LINE: Mapping[str, str] = {
    "Green": TRAIN_CONTROLLER_SW,
    "Red": TRAIN_CONTROLLER_HW,
}


class SystemEdges:
    """Real edges into the modules wired in, stub edges for the rest."""

    def __init__(
        self,
        track_feed: FixedTrackFeed,
        wired: Collection[str] = WIRED_MODULES,
    ) -> None:
        """Prepare the edges, with no train in service.

        Args:
            track_feed: The track every train finds.
            wired: The modules that are real, not stubs.
        """
        self._feed = track_feed
        self._wired = frozenset(wired)
        self._roster = Roster(CTC_OFFICE)

    @property
    def roster(self) -> Roster:
        """The trains in service."""
        return self._roster

    def tick_completed(
        self,
        tick: int,
        sim_time_s: float,
        fresh: Mapping[str, Mapping[str, Any]],
    ) -> list[Event]:
        """Apply the CTC Office's train events and log rejections.

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
        if consumer == TRAIN_MODEL:
            return self._train_model_inputs(sim_time_s, outputs)
        if consumer in CONTROLLER_FOR_LINE.values():
            return self._train_controller_inputs(
                consumer, sim_time_s, outputs
            )
        raise KeyError(f"no edges into {consumer} yet")

    def _train_model_inputs(
        self, sim_time_s: float, outputs: Mapping[str, Mapping[str, Any]]
    ) -> dict[str, Any]:
        # Every train in service: its Train Controller's last commands,
        # or the inert ones before the first, and its track.
        commands: dict[str, Any] = {}
        for controller in CONTROLLER_FOR_LINE.values():
            commands.update(_trains(outputs.get(controller)))
        trains = {}
        for entry in self._roster:
            train_commands = commands.get(entry.train_id)
            trains[entry.train_id] = {
                "line": entry.line,
                "controller": (
                    dict(INERT_COMMANDS) if train_commands is None
                    else train_controller_to_train_model(train_commands)
                ),
                "track": self._feed.track_inputs(
                    sim_time_s - entry.joined_s
                ),
            }
        return {"trains": trains}

    def _train_controller_inputs(
        self,
        consumer: str,
        sim_time_s: float,
        outputs: Mapping[str, Mapping[str, Any]],
    ) -> dict[str, Any]:
        # The trains on this controller's line that the Train Model has
        # reported: its outputs, and the light ahead.
        reports = _trains(outputs.get(TRAIN_MODEL))
        trains = {}
        for entry in self._roster:
            report = reports.get(entry.train_id)
            if CONTROLLER_FOR_LINE[entry.line] != consumer or report is None:
                continue
            inputs = train_model_to_train_controller(report["controller"])
            inputs["signal_light_ahead"] = aspect_to_train_controller(
                self._feed.aspect_ahead(sim_time_s - entry.joined_s)
            )
            trains[entry.train_id] = {"line": entry.line, "inputs": inputs}
        return {"trains": trains}


def _trains(outputs: Mapping[str, Any] | None) -> Mapping[str, Any]:
    # One module's outputs per train; none from a stub or before the
    # module's first reply.
    trains = (outputs or {}).get("trains")
    return trains if isinstance(trains, Mapping) else {}
