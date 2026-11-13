"""Run existing simulated Pi fault checks through their shared helpers."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys

from .transport import ROOT

CHECKS = {
    "reboot-drop": [
        "common/harness/tests/test_harness_hw_system.py::"
        "test_pi_loss_holds_then_recovers_pending_step",
    ],
    "gains": [
        "common/hw_link/tests/test_transports_recovery.py::"
        "test_reboot_repeats_pending_from_durable_cache_and_gain_policy",
        "common/hw_link/tests/test_transports_recovery.py::"
        "test_same_boot_unplug_resends_running_gains_only",
    ],
    "pty": [
        "common/hw_link/tests/test_raw_gadget.py::"
        "test_raw_device_reopens_same_session_without_traceback",
    ],
    "missing": [
        "common/hw_link/tests/test_transports_recovery.py::"
        "test_missing_production_pi_holds_readiness_without_fallback",
        "common/hw_link/tests/test_transports_recovery.py::"
        "test_missing_or_ambiguous_pi_names_identity_and_repeats",
    ],
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", choices=("all", *CHECKS), default="all")
    options = parser.parse_args()
    selected = (
        CHECKS.values()
        if options.scenario == "all"
        else [CHECKS[options.scenario]]
    )
    tests = [test for group in selected for test in group]
    return subprocess.call(
        [sys.executable, "-m", "pytest", "-q", *tests],
        cwd=ROOT,
        env=dict(os.environ, QT_QPA_PLATFORM="offscreen"),
    )


if __name__ == "__main__":
    raise SystemExit(main())
