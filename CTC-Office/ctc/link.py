"""The test UI's link to the CTC Office.

The CTC test UI stands in for the Track Controller and the Track Model.
It reaches the CTC Office only through this link, which exposes exactly
the module boundary: ``step(dt, CtcInputs)`` returning ``CtcOutputs``,
``set_inputs`` for whatever steps the module, plus the dispatcher
actions the real CTC UI issues.

Once the system is integrated, the central harness calls the module's
own ``step`` in place of this link (decision D005), and the test UI and
this file are removed with no change to the module.

``LocalLink`` hosts the module inside the test UI's process, where no
clock runs, so ``set_inputs`` steps one fixed tick. ``SocketLink``
(``ctc.socket_link``) reaches the module in the CTC window, whose clock
steps it.
"""

from __future__ import annotations

from typing import Callable, Protocol

from ctc.interface import (
    CtcInputs,
    CtcOffice,
    CtcOutputs,
    CtcSnapshot,
    SwitchPosition,
)
from ctc.model import StubCtcOffice

#: The fixed time step (decision D006), used when no clock is running.
STANDALONE_DT_S = 0.1


class CtcLink(Protocol):
    """What the test UI can do to the CTC Office."""

    #: True when a CTC UI owns some controls (maintenance mode), so the
    #: test UI must only display them.
    ctc_ui_attached: bool

    @property
    def connected(self) -> bool:
        ...

    def step(self, dt: float, inputs: CtcInputs) -> CtcOutputs:
        ...

    def snapshot(self) -> CtcSnapshot:
        ...

    def set_inputs(self, inputs: CtcInputs) -> None:
        """Replace the inputs the CTC window's clock steps with."""
        ...

    def dispatch(self, train_id: str, line: str,
                 destination_block_id: str,
                 arrival_s: float | None = None) -> None:
        ...

    def cancel_dispatch(self, train_id: str) -> None:
        ...

    def set_block_closed(self, line: str, block_id: str,
                         closed: bool) -> None:
        ...

    def set_switch(self, line: str, switch_id: str,
                   position: SwitchPosition) -> None:
        ...

    def release_switch(self, line: str, switch_id: str) -> None:
        ...

    def set_maintenance_mode(self, active: bool) -> None:
        ...

    def set_clock_speedup(self, active: bool) -> None:
        ...

    def reset(self) -> None:
        """Test only: replace the module with a fresh instance."""
        ...


class LocalLink:
    """A ``CtcLink`` to a CTC Office in this process."""

    #: No CTC UI is attached, so the test UI drives every control.
    ctc_ui_attached = False

    def __init__(
        self, factory: Callable[[], CtcOffice] = StubCtcOffice
    ) -> None:
        self._factory = factory
        self._module: CtcOffice = factory()

    @property
    def connected(self) -> bool:
        return True

    def step(self, dt: float, inputs: CtcInputs) -> CtcOutputs:
        return self._module.step(dt, inputs)

    def snapshot(self) -> CtcSnapshot:
        return self._module.snapshot()

    def set_inputs(self, inputs: CtcInputs) -> None:
        # No clock runs in this process, so new inputs take one tick.
        self._module.step(STANDALONE_DT_S, inputs)

    def dispatch(self, train_id: str, line: str,
                 destination_block_id: str,
                 arrival_s: float | None = None) -> None:
        self._module.dispatch(train_id, line, destination_block_id,
                              arrival_s)

    def cancel_dispatch(self, train_id: str) -> None:
        self._module.cancel_dispatch(train_id)

    def set_block_closed(self, line: str, block_id: str,
                         closed: bool) -> None:
        self._module.set_block_closed(line, block_id, closed)

    def set_switch(self, line: str, switch_id: str,
                   position: SwitchPosition) -> None:
        self._module.set_switch(line, switch_id, position)

    def release_switch(self, line: str, switch_id: str) -> None:
        self._module.release_switch(line, switch_id)

    def set_maintenance_mode(self, active: bool) -> None:
        self._module.set_maintenance_mode(active)

    def set_clock_speedup(self, active: bool) -> None:
        self._module.set_clock_speedup(active)

    def reset(self) -> None:
        self._module = self._factory()
