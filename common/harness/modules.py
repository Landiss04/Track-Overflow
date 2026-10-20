"""The modules the harness runs, and how it starts them.

Each module runs in a process of its own: the harness runs this same
executable again with ``--module <name>``
(``conventions/files-and-paths``). Module names are the keys of the
modules' ``truth`` shards, in lowercase with hyphens. Every enumerated
value that crosses a module boundary is in capitals
(``conventions/naming``); a module name is a key, not such a value.

``PRODUCERS`` is the system's edge map (D005; Appendix A of
``documents/system-integration-design.md``): for each module, the
modules whose outputs become its inputs.

``WIRED_MODULES`` are the modules wired in so far, which run as
themselves; every other module runs as a stub
(``common.harness.stub_module``). Phase 1 wired in the Train Model and
the Train Controller SW, Phase 2 the Track Model, Phase 3 the Track
Controller SW, and Phase 4 the CTC Office.
"""

from __future__ import annotations

__all__ = [
    "CTC_OFFICE",
    "MODULE_NAMES",
    "PRODUCERS",
    "TRACK_CONTROLLER_HW",
    "TRACK_CONTROLLER_SW",
    "TRACK_MODEL",
    "TRAIN_CONTROLLER_HW",
    "TRAIN_CONTROLLER_SW",
    "TRAIN_MODEL",
    "WIRED_MODULES",
    "ModuleSpec",
    "module_command",
    "module_spec",
    "stub_spec",
    "stub_specs",
    "system_specs",
    "working_directory",
]

import sys
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

CTC_OFFICE = "ctc-office"
TRACK_CONTROLLER_SW = "track-controller-sw"
TRACK_CONTROLLER_HW = "track-controller-hw"
TRACK_MODEL = "track-model"
TRAIN_MODEL = "train-model"
TRAIN_CONTROLLER_SW = "train-controller-sw"
TRAIN_CONTROLLER_HW = "train-controller-hw"

#: Every module, in the order the harness starts and steps them.
MODULE_NAMES = (
    CTC_OFFICE,
    TRACK_CONTROLLER_SW,
    TRACK_CONTROLLER_HW,
    TRACK_MODEL,
    TRAIN_MODEL,
    TRAIN_CONTROLLER_SW,
    TRAIN_CONTROLLER_HW,
)

#: The modules wired in so far (Phase 4); the rest are stubs.
WIRED_MODULES = frozenset({
    CTC_OFFICE,
    TRACK_CONTROLLER_SW,
    TRACK_MODEL,
    TRAIN_MODEL,
    TRAIN_CONTROLLER_SW,
})

#: For each module, the modules whose outputs it reads.
PRODUCERS: Mapping[str, tuple[str, ...]] = {
    CTC_OFFICE: (TRACK_CONTROLLER_SW, TRACK_CONTROLLER_HW, TRACK_MODEL),
    TRACK_CONTROLLER_SW: (CTC_OFFICE, TRACK_MODEL),
    TRACK_CONTROLLER_HW: (CTC_OFFICE, TRACK_MODEL),
    TRACK_MODEL: (TRACK_CONTROLLER_SW, TRACK_CONTROLLER_HW, TRAIN_MODEL),
    TRAIN_MODEL: (TRACK_MODEL, TRAIN_CONTROLLER_SW, TRAIN_CONTROLLER_HW),
    TRAIN_CONTROLLER_SW: (TRAIN_MODEL, TRACK_MODEL),
    TRAIN_CONTROLLER_HW: (TRAIN_MODEL, TRACK_MODEL),
}

# The executable's entry script, run by the interpreter when the
# system runs from source rather than as a built executable.
_REPO_ROOT = Path(__file__).resolve().parents[2]
_ENTRY_SCRIPT = _REPO_ROOT / "track_overflow.py"


@dataclass(frozen=True)
class ModuleSpec:
    """How the harness starts one module.

    Attributes:
        name: The module's name, which its ``READY`` must carry.
        args: Arguments for the executable, starting with
            ``--module``. The harness adds ``--harness <server>``.
    """

    name: str
    args: tuple[str, ...]


def module_command(args: Sequence[str]) -> tuple[str, list[str]]:
    """Return the program and arguments that run this executable.

    Args:
        args: The executable's own arguments, such as
            ``["--module", "stub", "--as", "ctc-office"]``.

    Returns:
        The program to start and its full argument list: the built
        executable itself, or the interpreter and the entry script.
    """
    if getattr(sys, "frozen", False):
        return sys.executable, list(args)
    return sys.executable, [str(_ENTRY_SCRIPT), *args]


def working_directory() -> Path:
    """Return the folder module processes start in.

    The repository root from source, the executable's folder when
    built, so a module starts the same wherever the harness was run
    from.
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return _REPO_ROOT


def module_spec(name: str, *options: str) -> ModuleSpec:
    """Return the spec that runs module ``name`` as itself.

    Args:
        name: One of ``WIRED_MODULES``.
        *options: Further options for that module's process.
    """
    return ModuleSpec(name, ("--module", name, *options))


def stub_spec(name: str, *options: str) -> ModuleSpec:
    """Return the spec of a stub standing in for module ``name``.

    Args:
        name: The module the stub plays.
        *options: Further stub options, such as
            ``"--reject-at-tick", "4"``.
    """
    return ModuleSpec(name, ("--module", "stub", "--as", name, *options))


def stub_specs(
    options: Mapping[str, Sequence[str]] | None = None,
) -> list[ModuleSpec]:
    """Return a stub for every module.

    Args:
        options: Stub options per module name, for the stubs that
            need any.
    """
    options = options or {}
    unknown = set(options) - set(MODULE_NAMES)
    if unknown:
        raise ValueError(f"no such module: {', '.join(sorted(unknown))}")
    return [stub_spec(name, *options.get(name, ())) for name in MODULE_NAMES]


def system_specs(
    options: Mapping[str, Sequence[str]] | None = None,
    wired: Collection[str] = WIRED_MODULES,
) -> list[ModuleSpec]:
    """Return a spec for every module, wired or stub.

    Args:
        options: Options per module name: stub options for a stub,
            the module's own options for a wired module.
        wired: The modules to run as themselves.
    """
    options = options or {}
    unknown = set(options) - set(MODULE_NAMES)
    if unknown:
        raise ValueError(f"no such module: {', '.join(sorted(unknown))}")
    return [
        (module_spec if name in wired else stub_spec)(
            name, *options.get(name, ())
        )
        for name in MODULE_NAMES
    ]
