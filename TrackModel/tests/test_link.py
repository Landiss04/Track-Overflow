"""The local-socket link carries steps and UI actions both ways.

Server and client run in one process here, over the real named pipe.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from tests.qt_helpers import dispose, qt_app, wait_for
from test_link.link import LinkClient, LinkServer
from track_model.interface import TrackFailure, TrackModelOutputs
from tests.helpers import DT_S, make_inputs, make_model, report


@pytest.fixture()
def linked() -> Iterator[tuple[LinkServer, LinkClient, list[object]]]:
    """Return a listening server, a connected client and its inbox."""
    qt_app()
    model = make_model()
    server = LinkServer(model)
    assert server.listen()
    client = LinkClient()
    inbox: list[object] = []
    client.outputsReceived.connect(inbox.append)
    client.errorReceived.connect(inbox.append)
    client.connect_to_server()
    assert wait_for(lambda: client.connected and len(inbox) == 1)
    inbox.clear()
    yield server, client, inbox
    # Close the pipe now so the next test cannot reach this server.
    client.close()
    server.close()
    dispose(client, server)


def test_step_round_trips(
    linked: tuple[LinkServer, LinkClient, list[object]],
) -> None:
    """Check a step over the link returns that tick's outputs."""
    _, client, inbox = linked
    assert client.step(DT_S, make_inputs({"T1": report("GREEN A-1", 1.0)}))
    assert wait_for(lambda: bool(inbox))
    outputs = inbox[0]
    assert isinstance(outputs, TrackModelOutputs)
    assert outputs.controller.block_occupancy["GREEN A-1"]


def test_ui_action_is_pushed_between_steps(
    linked: tuple[LinkServer, LinkClient, list[object]],
) -> None:
    """Check a Track Model UI failure reaches the client unprompted."""
    server, _, inbox = linked
    server.model.set_block_failure("GREEN A-1", TrackFailure.POWER)
    server.notify_outputs()
    assert wait_for(lambda: bool(inbox))
    outputs = inbox[0]
    assert isinstance(outputs, TrackModelOutputs)
    assert outputs.controller.failure_status["GREEN A-1"] is (
        TrackFailure.POWER)


def test_rejected_input_comes_back_as_an_error(
    linked: tuple[LinkServer, LinkClient, list[object]],
) -> None:
    """Check a bad step reports an error instead of crashing."""
    _, client, inbox = linked
    client.step(DT_S, make_inputs({"T1": report("NOWHERE 1")}))
    assert wait_for(lambda: bool(inbox))
    assert isinstance(inbox[0], str) and "NOWHERE" in inbox[0]


def test_test_only_commands(
    linked: tuple[LinkServer, LinkClient, list[object]],
) -> None:
    """Check failure, reset and edit requests all answer with outputs."""
    _, client, inbox = linked
    client.set_block_failure("BLUE A-1", TrackFailure.BROKEN_RAIL)
    client.reset()
    assert wait_for(lambda: len(inbox) == 2)
    first, second = inbox
    assert isinstance(first, TrackModelOutputs)
    assert isinstance(second, TrackModelOutputs)
    assert first.controller.failure_status["BLUE A-1"] is (
        TrackFailure.BROKEN_RAIL)
    assert second.controller.failure_status["BLUE A-1"] is TrackFailure.NONE
