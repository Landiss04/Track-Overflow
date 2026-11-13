"""Exceptions raised by the hardware Track Controller.

Every error derives from ``TrackControllerError``, so a caller can catch
the whole module's errors in one clause
(``truth/conventions/identifiers.md``).
"""

from __future__ import annotations


class TrackControllerError(Exception):
    """Base class for every Track Controller error."""


class TerritoryError(TrackControllerError):
    """A wayside database is malformed or cannot be loaded."""


class PlcError(TrackControllerError):
    """A PLC program does not compile or does not fit its wayside.

    ``diagnostics`` holds every message, one per line, so the UI can
    show them all at once.
    """

    def __init__(
        self, message: str, diagnostics: tuple[str, ...] = ()
    ) -> None:
        super().__init__(message)
        self.diagnostics = diagnostics


class InvalidTimeStepError(TrackControllerError):
    """``step`` was given a time step that is not finite and positive."""


class InvalidInputError(TrackControllerError):
    """``step`` was given inputs it must reject."""


class WireFormatError(TrackControllerError):
    """A message from the other process is not in the expected form."""
