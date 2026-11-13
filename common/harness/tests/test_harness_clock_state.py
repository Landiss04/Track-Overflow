"""HW hosts receive actual clock state independently of simulation ticks."""
from PySide6.QtCore import QCoreApplication

from common.harness.core import Harness
from common.harness.modules import (
    CTC_OFFICE, TRACK_CONTROLLER_HW, TRAIN_CONTROLLER_HW, module_spec,
)
from common.harness.supervisor import ModuleSupervisor
from utils.event_log import EventLog
from utils.harness_protocol import encode, state_message

APP = QCoreApplication.instance() or QCoreApplication([])
HW = (TRACK_CONTROLLER_HW, TRAIN_CONTROLLER_HW)


def test_initial_pause_and_every_transition_without_advancing_clock(
    tmp_path, monkeypatch,
):
    ready, sent = [], []
    monkeypatch.setattr(ModuleSupervisor, "ready_modules",
                        property(lambda _self: tuple(ready)))
    monkeypatch.setattr(ModuleSupervisor, "send",
                        lambda _self, name, message:
                        sent.append((name, message)) or True)
    with EventLog(tmp_path / "events.csv") as log:
        harness = Harness([module_spec(name) for name in (CTC_OFFICE, *HW)],
                          log)
        try:
            for name in (CTC_OFFICE, *HW):
                ready.append(name)
                harness._on_module_ready(name)
            assert [name for name, _ in sent] == list(HW)
            for _, message in sent:
                encode(message)
                assert message["state"] == {
                    "clock_paused": True, "clock_speedup": False,
                }
            harness._all_ready = True
            for controls, expected in (
                ({"clock_paused": False}, (False, False)),
                ({"clock_speedup": True}, (False, True)),
                ({"clock_paused": True}, (True, True)),
            ):
                before = len(sent)
                harness._on_message(CTC_OFFICE, state_message(0, controls))
                assert len(sent) == before + len(HW)
                for name, message in sent[before:]:
                    assert name in HW
                    assert message["tick"] == 0
                    assert tuple(message["state"].values()) == expected
            assert harness.clock.tick_count == 0
            # A newly ready host gets the current state, even at 10x.
            harness._on_module_ready(TRACK_CONTROLLER_HW)
            assert sent[-1][1]["state"] == {
                "clock_paused": True, "clock_speedup": True,
            }
        finally:
            harness.stop()
