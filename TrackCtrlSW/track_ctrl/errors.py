"""Errors the Track Controller (Software) module raises.

Every error derives from :class:`TrackControllerError`, so a caller such
as the central harness can catch the whole module's errors in one
clause (``truth/conventions/identifiers.md``). The two that existed
before this module had a boundary, a bad layout and a bad program, were
``ValueError`` and still are, so code that caught them that way keeps
working.
"""

from __future__ import annotations


class TrackControllerError(Exception):
    """Base class for every error this module raises."""


class InvalidInputError(TrackControllerError, ValueError):
    """An input or command was rejected; no state was changed."""


class UnknownIdError(InvalidInputError, KeyError):
    """A name that does not exist in the loaded track was used.

    Raised for a wayside, switch or block the module does not govern,
    when the caller named it as a command target. ``KeyError`` is a base
    so existing lookups that expected one still work; its ``str`` is
    overridden below because ``KeyError`` would quote the message.
    """

    def __str__(self) -> str:
        return Exception.__str__(self)


class InvalidProgramError(TrackControllerError, ValueError):
    """A PLC program was refused: it has errors, warnings or no fit."""


class WireFormatError(TrackControllerError, ValueError):
    """A message from another process was not exactly the expected shape."""
