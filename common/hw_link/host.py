"""Host hardware-module processes: existing windows plus a USB Pi relay."""

from __future__ import annotations

import argparse
import importlib.util
import signal
import sys
import os
from datetime import datetime, timezone
import tempfile
from pathlib import Path
from typing import Any

from PySide6.QtCore import QTimer, QStandardPaths
from PySide6.QtGui import QGuiApplication
from utils.module_link import ModuleLink
from utils.module_window import keep_windows_open
from . import protocol as p
from .cores import ROOT
from .relay import HardwareRelay
from .transport import ByteTransport, ProcessTransport, SerialTransport


def main(argv: list[str] | None = None) -> int:
    """Run one host relay; simulated agents require an explicit test option."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--as", dest="module", choices=p.MODULES, required=True
    )
    parser.add_argument("--harness", required=True)
    parser.add_argument(
        "--test-pi",
        choices=("process", "pty"),
        help="tests only; never selected automatically",
    )
    parser.add_argument("--load-starters", action="store_true")
    parser.add_argument(
        "--pi-log", type=Path, help="durable host recovery trace"
    )
    parser.add_argument("--engineer-gains", type=float, nargs=2)
    for flag in ("delay-ms", "jitter-ms"):
        parser.add_argument("--pi-" + flag, type=float, default=0)
    for flag in ("drop-after", "reboot-at-tick"):
        parser.add_argument("--pi-" + flag, type=int)
    options = parser.parse_args(argv)
    if not options.test_pi and any(
        getattr(options, "pi_" + key.replace("-", "_"))
        for key in ("delay-ms", "jitter-ms", "drop-after", "reboot-at-tick")
    ):
        parser.error("Pi fault injection requires explicit --test-pi")
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    track_window: Any = None
    scratch = (
        tempfile.TemporaryDirectory(prefix="track-overflow-pi-")
        if options.test_pi
        else None
    )

    def make_relay(app: QGuiApplication) -> HardwareRelay:
        transport: ByteTransport
        if options.test_pi:
            assert scratch is not None
            fault_args = []
            for flag in (
                "delay-ms", "jitter-ms", "drop-after", "reboot-at-tick"
            ):
                value = getattr(options, "pi_" + flag.replace("-", "_"))
                if value is not None and value != 0:
                    fault_args.extend(["--" + flag, str(value)])
            transport = ProcessTransport(
                options.module,
                (
                    options.pi_log.with_suffix(".agent.jsonl")
                    if options.pi_log
                    else Path(scratch.name) / "agent.jsonl"
                ),
                raw_pty=options.test_pi == "pty",
                fault_args=fault_args,
                parent=app,
            )
        else:
            transport = SerialTransport(options.module, app)
        return HardwareRelay(options.module, transport, app)

    relay: HardwareRelay
    remote: Any
    if options.module == "track-controller-hw":
        from .remote_track import RemoteTrackController
        from track_ctrl_hw.state import TrackControllerState

        def make_state() -> TrackControllerState:
            # Window calls this only after constructing its application.
            nonlocal relay, remote
            application = QGuiApplication.instance()
            assert isinstance(application, QGuiApplication)
            relay = make_relay(application)
            remote = RemoteTrackController(relay)
            state = TrackControllerState(controller=remote)
            relay.viewChanged.connect(lambda _view: state.refresh())
            return state

        source = ROOT / "TrackCtrlHw" / "ui" / "app.py"
        spec = importlib.util.spec_from_file_location(
            "_track_hw_host_window", source
        )
        assert spec is not None and spec.loader is not None
        window_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(window_module)
        track_window = window_module.Window(
            sys.argv[:1], state_factory=make_state
        )
        app = track_window.app
    else:
        from .remote_train import RemoteTrainFleet

        app = QGuiApplication.instance() or QGuiApplication(sys.argv[:1])
        assert isinstance(app, QGuiApplication)
        relay = make_relay(app)
        remote = RemoteTrainFleet(relay)
    keep_windows_open(app)
    link = ModuleLink(
        options.module,
        options.harness,
        lambda *_args: {},
        app,
        deferred_handler=relay.submit_step,
    )
    relay.reply.connect(
        lambda reply: (
            link.reply_outputs(reply["id"], reply["tick"], reply["outputs"])
            if reply["op"] == "OUTPUTS"
            else link.reply_rejected(
                reply["id"], reply["tick"], reply["reason"]
            )
        )
    )
    if hasattr(link, "clockStateChanged"):
        link.clockStateChanged.connect(relay.set_clock_state)
    log_path = options.pi_log or (
        Path(scratch.name) / (options.module + ".log")
        if scratch
        else Path(
            QStandardPaths.writableLocation(
                QStandardPaths.StandardLocation.AppLocalDataLocation
            )
        )
        / "logs"
        / (options.module + "-pi.log")
    )
    log_path.parent.mkdir(parents=True, exist_ok=True)

    def record_event(text: str) -> None:
        stamp = datetime.now(timezone.utc).isoformat()
        with log_path.open("a", encoding="utf-8") as stream:
            stream.write(f"{stamp} {options.module} {text}\n")
            stream.flush()
            os.fsync(stream.fileno())
        event, _, detail = text.partition(" ")
        link.push_state({
            "module": options.module,
            "pi_event": {"event": event, "detail": detail},
        })

    relay.diagnosticEvent.connect(record_event)
    record_event("PI_TRACE " + str(log_path))
    initialized = False

    def ready() -> None:
        nonlocal initialized
        if initialized:
            return
        initialized = True
        if options.module == "track-controller-hw" and options.load_starters:
            from track_ctrl_hw.territory import load_territory_file

            for file in sorted(
                (ROOT / "TrackCtrlHw/data/waysides").glob(
                    "red_*_integration_test.json"
                )
            ):
                territory = load_territory_file(file)
                remote.load_territory(territory)
                program = ROOT / "TrackCtrlHw/data/plc" / (file.stem + ".plc")
                remote.load_program(
                    territory.wayside_id, program.read_text(), program.name
                )
        if options.module == "train-controller-hw" and options.engineer_gains:
            relay.call_action(
                "test_engineer_gains",
                dict(zip(("kp", "ki"), options.engineer_gains)),
            )
        link.announce_ready()

    relay.ready.connect(ready)
    link.quitRequested.connect(lambda: app.exit(0))
    link.harnessLost.connect(lambda: app.exit(2))
    link.connect_to_harness()
    QTimer.singleShot(0, relay.start)
    if options.module == "train-controller-hw":
        from train_ctrl.app import run

        exit_code = run(console=True, bench=False, fleet=remote)
    else:
        exit_code = app.exec()
        track_window.shutdown()
    relay.close()
    link.close()
    if scratch:
        scratch.cleanup()
    return exit_code
