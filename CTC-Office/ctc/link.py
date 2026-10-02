"""The test UI's link to the CTC Office.

The CTC test UI stands in for the Track Controller, the Track Model
and the clock. It reaches the CTC Office only through this link, which
exposes exactly the module boundary: ``step(dt, CtcInputs)`` returning
``CtcOutputs``, plus the dispatcher actions the real CTC UI will issue.

Once the system is integrated, the central harness calls the module's
own ``step`` in place of this link (decision D005), and the test UI and
this file are removed with no change to the module.

``LocalLink`` hosts the module inside the test UI's process. A socket
link to a CTC Office running in its own process can implement the same
``CtcLink`` protocol later without touching the test UI or the module.
"""

from __future__ import annotations

from typing import Callable, Protocol

from ctc.interface import CtcInputs, CtcOffice, CtcOutputs, CtcSnapshot
from ctc.model import StubCtcOffice


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

    def dispatch(self, train_id: str, destination_block_id: str) -> None:
        ...

    def cancel_dispatch(self, train_id: str) -> None:
        ...

    def set_block_closed(self, block_id: str, closed: bool) -> None:
        ...

    def set_maintenance_mode(self, active: bool) -> None:
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

    def dispatch(self, train_id: str, destination_block_id: str) -> None:
        self._module.dispatch(train_id, destination_block_id)

    def cancel_dispatch(self, train_id: str) -> None:
        self._module.cancel_dispatch(train_id)

    def set_block_closed(self, block_id: str, closed: bool) -> None:
        self._module.set_block_closed(block_id, closed)

    def set_maintenance_mode(self, active: bool) -> None:
        self._module.set_maintenance_mode(active)

    def reset(self) -> None:
        self._module = self._factory()
