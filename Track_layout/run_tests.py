"""Run the Track Model test suite and print a readable report.

Every automated test is listed under its area with the one-line
description from its docstring, then PASS, FAIL or SKIP. Failures are
followed by pytest's own detail. Run from anywhere::

    TrackModel/.venv/Scripts/python TrackModel/run_tests.py
    TrackModel/.venv/Scripts/python TrackModel/run_tests.py -k switch

Extra arguments are passed to pytest. Exits non-zero if anything fails.
"""

from __future__ import annotations

import os
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

import pytest

MODULE_DIR = Path(__file__).resolve().parent

#: Report headings, in the order the areas are printed.
AREAS: dict[str, str] = {
    "test_layout.py": "Layout loading and track graph",
    "test_wiring.py": "Inputs reach outputs (module)",
    "test_green_line.py": "Green line: layout, devices and the course route",
    "test_green_direction.py": "Green line: direction of travel",
    "test_heaters_and_failures.py": "Heaters, track temperature, failures",
    "test_contract.py": "Module contract",
    "test_harness_edges.py": "Harness edges (what other modules call)",
    "test_codec.py": "Test link: JSON encoding",
    "test_link.py": "Test link: local socket",
    "test_end_to_end.py": "End to end: test UI drives the Track Model",
    "test_block_filter.py": "Test UI: block filter",
}


class _Report:
    """pytest plugin that records each test's description and outcome."""

    def __init__(self) -> None:
        self.docs: dict[str, str] = {}
        self.order: list[str] = []
        self.outcomes: dict[str, str] = {}
        self.details: dict[str, str] = {}

    def pytest_collection_finish(self, session: Any) -> None:
        """Record every selected test and its docstring."""
        for item in session.items:
            doc = (getattr(item, "function", None).__doc__ or "").strip()
            self.docs[item.nodeid] = doc.splitlines()[0] if doc else ""
            self.order.append(item.nodeid)

    def pytest_runtest_logreport(self, report: Any) -> None:
        """Keep the worst outcome across setup, call and teardown."""
        if report.failed:
            self.outcomes[report.nodeid] = "FAIL"
            self.details[report.nodeid] = report.longreprtext
        elif report.skipped and report.nodeid not in self.outcomes:
            self.outcomes[report.nodeid] = "SKIP"
        elif report.when == "call" and report.passed:
            self.outcomes.setdefault(report.nodeid, "PASS")


def _label(nodeid: str) -> str:
    # "tests/test_x.py::test_name[param]" -> "test name [param]"
    name = nodeid.split("::", 1)[1]
    base, _, param = name.partition("[")
    text = base.removeprefix("test_").replace("_", " ")
    return f"{text} [{param}" if param else text


def main(argv: list[str]) -> int:
    """Run pytest quietly, then print the grouped report."""
    os.chdir(MODULE_DIR)
    report = _Report()
    code = pytest.main(["-q", "-p", "no:cacheprovider", "--no-header",
                        "--tb=short", "-rN", *argv], plugins=[report])
    print("\n" + "=" * 72)
    print("TRACK MODEL TEST REPORT")
    print("=" * 72)

    grouped: dict[str, list[str]] = defaultdict(list)
    for nodeid in report.order:
        grouped[Path(nodeid.split("::")[0]).name].append(nodeid)
    files = [f for f in AREAS if f in grouped]
    files += sorted(f for f in grouped if f not in AREAS)

    totals: dict[str, int] = defaultdict(int)
    for file in files:
        print(f"\n{AREAS.get(file, file)}  ({file})")
        for nodeid in grouped[file]:
            outcome = report.outcomes.get(nodeid, "NOT RUN")
            totals[outcome] += 1
            print(f"  {outcome:<5} {_label(nodeid)}")
            if report.docs.get(nodeid):
                print(f"        {report.docs[nodeid]}")

    failed = [n for n in report.order if report.outcomes.get(n) == "FAIL"]
    for nodeid in failed:
        print("\n" + "-" * 72 + f"\nFAILED {nodeid}\n" + "-" * 72)
        print(report.details[nodeid])

    summary = ", ".join(f"{n} {k.lower()}" for k, n in sorted(totals.items()))
    print("\n" + "=" * 72 + f"\n{summary}\n" + "=" * 72)
    return int(code)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
