"""Exceptions raised by the Train Controller module.

Per ``truth/conventions/identifiers.md``, the module has one base
exception, so callers can catch all of its errors in one clause.
"""

from __future__ import annotations


class TrainControllerError(Exception):
    """Base class for every Train Controller error."""


class InvalidBlockError(TrainControllerError):
    """A block ID is unknown or out of order on the route."""


class InvalidSignalAspectError(TrainControllerError):
    """A signal aspect is not one of the recognised values."""
