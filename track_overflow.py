"""Track Overflow: the one executable for the whole system.

Run with no arguments, it starts the central harness. The harness
starts every module by running this same program again with
``--module <name>`` (``conventions/files-and-paths``; G-RUN-2 in
``documents/system-integration-design.md``).

In Phase 0 the only module is ``stub``, which stands in for any of the
seven; the real modules are wired in from Phase 1.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable, Sequence

EXIT_USAGE = 2


def main(argv: Sequence[str] | None = None) -> int:
    """Start the harness, or one module with ``--module <name>``.

    Args:
        argv: The command line after the program name; defaults to
            ``sys.argv[1:]``.

    Returns:
        The exit code.
    """
    args = list(sys.argv[1:] if argv is None else argv)
    parser = argparse.ArgumentParser(add_help=False, allow_abbrev=False)
    parser.add_argument("--module")
    known, rest = parser.parse_known_args(args)
    if known.module is None:
        # Imported here, so a module process loads only its own code.
        from common.harness import app

        return app.main(rest)
    run_module = _MODULES.get(known.module)
    if run_module is None:
        print(
            f"track_overflow: no module {known.module!r} yet; "
            f"modules: {', '.join(sorted(_MODULES))}",
            file=sys.stderr,
        )
        return EXIT_USAGE
    return run_module(rest)


def _run_stub(args: list[str]) -> int:
    # Imported on use, which also lets a frozen build find it.
    from common.harness import stub_module

    return stub_module.main(args)


# Every module this executable can run, by its --module name.
_MODULES: dict[str, Callable[[list[str]], int]] = {
    "stub": _run_stub,
}


if __name__ == "__main__":
    sys.exit(main())
