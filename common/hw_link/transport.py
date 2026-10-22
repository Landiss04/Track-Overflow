"""Event-driven Qt serial, subprocess and Linux raw-pty byte transports."""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, QProcess, QSocketNotifier, QTimer, Signal
from PySide6.QtSerialPort import QSerialPort, QSerialPortInfo

IDENTITIES = {
    "track-controller-hw": {
        "manufacturer": "Track Overflow",
        "product": "Track Overflow Track Controller HW",
        "serial": "TO-TRACK-CTRL-HW-01",
        "vid": 0x1D6B,
        "pid": 0x0104,
    },
    "train-controller-hw": {
        "manufacturer": "Track Overflow",
        "product": "Track Overflow Train Controller HW",
        "serial": "TO-TRAIN-CTRL-HW-01",
        "vid": 0x1D6B,
        "pid": 0x0104,
    },
}
ROOT = Path(__file__).resolve().parents[2]


def matches_identity(info: Any, module: str) -> bool:
    """COM names change; VID, PID and the module serial number do not."""
    identity = IDENTITIES[module]
    return (
        info.hasVendorIdentifier()
        and info.hasProductIdentifier()
        and info.vendorIdentifier() == identity["vid"]
        and info.productIdentifier() == identity["pid"]
        and info.serialNumber() == identity["serial"]
    )


class ByteTransport(QObject):
    """An ordered asynchronous byte stream with connection state."""

    connected = Signal()
    disconnected = Signal()
    received = Signal(bytes)
    diagnostic = Signal(str)

    def start(self) -> None:
        raise NotImplementedError

    def write(self, data: bytes) -> None:
        raise NotImplementedError

    def close(self) -> None:
        raise NotImplementedError


class SerialTransport(ByteTransport):
    """Production USB transport; wait for the assigned Pi identity."""

    def __init__(self, module: str, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.module = module
        self.port = QSerialPort(self)
        self.port.setBaudRate(115200)
        self.port.readyRead.connect(
            lambda: self.received.emit(self.port.readAll().data())
        )
        self.port.errorOccurred.connect(self._error)
        self.retry = QTimer(self)
        self.retry.setInterval(300)
        self.retry.timeout.connect(self._find)
        self._open = False
        self._last_search: tuple[str, ...] | None = None
        self._last_search_at = 0.0

    def start(self) -> None:
        self.retry.start()
        self._find()

    def _find(self) -> None:
        if self._open:
            return
        ports = [
            info
            for info in QSerialPortInfo.availablePorts()
            if matches_identity(info, self.module)
        ]
        matches = tuple(sorted(info.systemLocation() for info in ports))
        now = time.monotonic()
        if matches != self._last_search or now - self._last_search_at >= 5.0:
            self._last_search, self._last_search_at = matches, now
            identity = IDENTITIES[self.module]
            self.diagnostic.emit(
                f"PI_SEARCH module={self.module} "
                f"manufacturer={identity['manufacturer']!r} "
                f"product={identity['product']!r} "
                f"serial={identity['serial']} "
                f"vid:pid={identity['vid']:04x}:{identity['pid']:04x} "
                f"matches={len(matches)} ports={list(matches)!r}"
            )
        if len(ports) != 1:
            return
        self.port.setPort(ports[0])
        if self.port.open(QSerialPort.OpenModeFlag.ReadWrite):
            self._open = True
            self.connected.emit()

    def _error(self, error: QSerialPort.SerialPortError) -> None:
        if self._open and error in (
            QSerialPort.SerialPortError.ResourceError,
            QSerialPort.SerialPortError.DeviceNotFoundError,
            QSerialPort.SerialPortError.ReadError,
            QSerialPort.SerialPortError.WriteError,
        ):
            self._open = False
            self.port.close()
            self.disconnected.emit()

    def write(self, data: bytes) -> None:
        if self._open:
            self.port.write(data)

    def close(self) -> None:
        self.retry.stop()
        self._open = False
        self.port.close()


class ProcessTransport(ByteTransport):
    """Explicit development Pi; restart keeps its durable journal."""

    def __init__(
        self,
        module: str,
        journal: Path,
        *,
        raw_pty: bool = False,
        fault_args: list[str] | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.module, self.journal = module, journal
        self.raw_pty = raw_pty
        self.fault_args = fault_args or []
        self.process = QProcess(self)
        self.process.setWorkingDirectory(str(ROOT))
        self.process.readyReadStandardOutput.connect(self._read_stdout)
        self.process.readyReadStandardError.connect(self._read_stderr)
        self.process.started.connect(self._started)
        self.process.finished.connect(self._ended)
        self.process.errorOccurred.connect(self._process_error)
        self._closing = False
        self._online = False
        self._master: int | None = None
        self._slave: int | None = None
        self._notifier: QSocketNotifier | None = None
        self._pending = bytearray()
        self._write_timer = QTimer(self)
        self._write_timer.setInterval(1)
        self._write_timer.timeout.connect(self._flush_pty)

    def start(self) -> None:
        if (
            self._closing
            or self.process.state() != QProcess.ProcessState.NotRunning
        ):
            return
        args = [
            "-m",
            "common.hw_link.agent",
            "--module",
            self.module,
            "--journal",
            str(self.journal),
            "--log",
            str(self.journal.with_suffix(".log")),
            *self.fault_args,
        ]
        if self.raw_pty:
            import pty
            import tty

            self._master, self._slave = pty.openpty()
            tty.setraw(self._slave)
            os.set_blocking(self._master, False)
            args += ["--device", os.ttyname(self._slave)]
        self.process.start(sys.executable, args)

    def _started(self) -> None:
        self._online = True
        if self._master is not None:
            self._notifier = QSocketNotifier(
                self._master, QSocketNotifier.Type.Read, self
            )
            self._notifier.activated.connect(self._read_pty)
        self.connected.emit()

    def _process_error(self, error: QProcess.ProcessError) -> None:
        if error == QProcess.ProcessError.FailedToStart:
            self.diagnostic.emit(self.process.errorString())
            self._ended()

    def _read_stdout(self) -> None:
        data = self.process.readAllStandardOutput().data()
        if not self.raw_pty and data:
            self.received.emit(data)

    def _read_stderr(self) -> None:
        data = self.process.readAllStandardError().data()
        if data:
            self.diagnostic.emit(bytes(data).decode("utf-8", "replace"))

    def _read_pty(self, *_args: Any) -> None:
        if self._master is None:
            return
        try:
            data = os.read(self._master, 65536)
        except BlockingIOError:
            return
        except OSError:
            return
        if data:
            self.received.emit(data)

    def write(self, data: bytes) -> None:
        if not self._online:
            return
        if self._master is None:
            self.process.write(data)
        else:
            self._pending.extend(data)
            self._flush_pty()

    def _flush_pty(self) -> None:
        if self._master is None or not self._pending:
            self._write_timer.stop()
            return
        try:
            count = os.write(self._master, self._pending)
            del self._pending[:count]
        except BlockingIOError:
            pass
        except OSError:
            return
        if self._pending:
            self._write_timer.start()

    def _ended(self, *_args: Any) -> None:
        was_online, self._online = self._online, False
        self._write_timer.stop()
        self._pending.clear()
        if self._notifier:
            self._notifier.setEnabled(False)
            self._notifier.deleteLater()
            self._notifier = None
        for name in ("_master", "_slave"):
            fd = getattr(self, name)
            if fd is not None:
                os.close(fd)
                setattr(self, name, None)
        if not self._closing and was_online:
            self.disconnected.emit()

    def close(self) -> None:
        self._closing = True
        self.process.terminate()
        if not self.process.waitForFinished(1000):
            self.process.kill()
            self.process.waitForFinished(1000)
        self._ended()
