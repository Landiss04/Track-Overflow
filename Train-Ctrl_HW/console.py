"""
HW Train Controller — driver / engineer console.
ECE1140 Team 3. Conforms to UI Style Guide v1.2.

    HardwareInterface   lever + e-stop in, power + brakes out
    ControllerCore      PI speed law; safety enforced on a separate path
    Console             the view; reads a snapshot, computes nothing

    python console.py           stub hardware
    python console.py --real    SPI + GPIO on the Pi
"""

import math
import sys
from dataclasses import dataclass, field

from PySide6.QtCore import Qt, QTimer, QTime, QRectF, QPointF, QSize
from PySide6.QtGui import QColor, QPainter, QPen, QFont, QPixmap, QIcon
from PySide6.QtWidgets import (
    QApplication, QButtonGroup, QComboBox, QDialog, QFrame, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QSizePolicy, QVBoxLayout, QWidget,
)

from ui import theme as T
from ui.theme import c

CONTROL_HZ = 20
UI_HZ = 10
MAX_POWER_W = 120_000.0
MPS_TO_MPH = 2.23694
M_TO_FT = 3.28084
ANNOUNCE_LOCKOUT_MS = 5000

ASPECTS = ["RED", "YELLOW", "GREEN", "SUPER GREEN"]
ASPECT_TOKEN = {"RED": "danger", "YELLOW": "warning",
                "GREEN": "success", "SUPER GREEN": "success"}
ASPECT_TEXT = {
    "RED": "Stop here.",
    "YELLOW": "Slow down. Be ready to stop.",
    "GREEN": "Clear. Go at the speed limit.",
    "SUPER GREEN": "Clear well ahead.",
}


# ================================================================ hardware
class HardwareInterface:
    def read_lever(self) -> float: return 0.5
    def read_estop(self) -> bool: return False
    def write_power(self, w: float) -> None: ...
    def write_service_brake(self, on: bool) -> None: ...
    def write_emergency_brake(self, on: bool) -> None: ...
    def close(self) -> None: ...


class PiHardware(HardwareInterface):
    """Lever via SPI ADC, e-stop on GPIO. Only place spidev/gpiozero appear."""
    ADC_CHANNEL, ESTOP_PIN, SERVICE_PIN, EMERGENCY_PIN = 0, 17, 27, 22

    def __init__(self):
        import spidev
        from gpiozero import Button, OutputDevice
        self.spi = spidev.SpiDev()
        self.spi.open(0, 0)
        self.spi.max_speed_hz = 1_350_000
        self._estop = Button(self.ESTOP_PIN, pull_up=True)
        self._service = OutputDevice(self.SERVICE_PIN)
        self._emergency = OutputDevice(self.EMERGENCY_PIN)

    def read_lever(self) -> float:
        r = self.spi.xfer2([1, (8 + self.ADC_CHANNEL) << 4, 0])
        return (((r[1] & 3) << 8) + r[2]) / 1023.0

    def read_estop(self) -> bool: return self._estop.is_pressed
    def write_service_brake(self, on): self._service.value = bool(on)
    def write_emergency_brake(self, on): self._emergency.value = bool(on)
    def close(self): self.spi.close()


# ================================================================ state
@dataclass
class State:
    train_id: str = "T-114"
    line: str = "GREEN LINE"
    manual: bool = False
    engineer: bool = False

    actual_mps: float = 11.6
    commanded_mps: float = 24.6
    target_mps: float = 21.5
    speed_limit_mps: float = 31.3
    authority_m: float = 10000
    accel_mps2: float = 0.0

    power_w: float = 0.0
    service_brake: bool = False
    service_request: bool = False
    emergency_brake: bool = False
    faults: list = field(default_factory=list)

    cabin_temp_f: float = 70.0
    target_temp_f: float = 72.0
    doors_left: bool = False
    doors_right: bool = False
    lights: bool = True
    headlights: bool = True

    next_station: str = "CENTRAL"
    arrives: str = "14:46"
    platform_side: str = "right"
    next_signal: str = "YELLOW"
    signal_block: str = "GREEN J"
    authority_block: str = "GREEN J"
    current_block: str = "GREEN I"

    kp: float = 1200.0
    ki: float = 40.0

    @property
    def actual_mph(self): return self.actual_mps * MPS_TO_MPH
    @property
    def commanded_mph(self): return self.commanded_mps * MPS_TO_MPH
    @property
    def target_mph(self): return self.target_mps * MPS_TO_MPH
    @property
    def limit_mph(self): return self.speed_limit_mps * MPS_TO_MPH


# ================================================================ control
class ControllerCore:
    def __init__(self, hw: HardwareInterface):
        self.hw = hw
        self.state = State()
        self.dt = 1.0 / CONTROL_HZ
        self.integral = 0.0
        self.last_reasons: list[str] = []
        # the controller is inert until an engineer commissions the gains
        self.armed = False

    def step(self) -> None:
        if not self.armed:
            return
        s = self.state
        if not s.manual:
            s.target_mps = min(s.commanded_mps, s.speed_limit_mps)

        error = s.target_mps - s.actual_mps
        self.integral += error * self.dt
        power = s.kp * error + s.ki * self.integral

        if power > MAX_POWER_W:
            power, self.integral = MAX_POWER_W, self.integral - error * self.dt
        elif power < 0.0:
            power, self.integral = 0.0, self.integral - error * self.dt

        s.power_w = power
        s.service_brake = (error < -0.5) or s.service_request

        self.enforce_safety()

        self.hw.write_power(s.power_w)
        self.hw.write_service_brake(s.service_brake)
        self.hw.write_emergency_brake(s.emergency_brake)
        self._plant()

    def enforce_safety(self) -> None:
        """Runs after the PI law and overrides it. Gains change how the train
        drives; they can never change whether it stops."""
        s = self.state
        reasons = []
        if self.hw.read_estop():
            reasons.append("DRIVER E-STOP")
        if s.actual_mps > s.speed_limit_mps * 1.05:
            reasons.append("OVER SPEED LIMIT")
        if s.authority_m <= 0.0:
            reasons.append("AUTHORITY EXCEEDED")
        if s.faults:
            reasons.append("EQUIPMENT FAULT")
        if reasons or s.emergency_brake:
            s.emergency_brake = True
            s.power_w = 0.0
            s.service_brake = True
            self.integral = 0.0
        self.last_reasons = reasons

    def release_emergency(self) -> bool:
        """Latching. Releases only when stopped with nothing still wrong."""
        s = self.state
        s.emergency_brake = False
        self.enforce_safety()
        if abs(s.actual_mps) < 0.1 and not self.last_reasons:
            s.emergency_brake = False
            return True
        s.emergency_brake = True
        return False

    def set_target_mph(self, mph: float) -> None:
        s = self.state
        if s.manual:
            s.target_mps = max(0.0, min(mph, s.limit_mph)) / MPS_TO_MPH

    def _plant(self) -> None:
        """Toy physics until the Train Model is wired in."""
        s = self.state
        a = (s.power_w / MAX_POWER_W) * 1.2
        if s.emergency_brake:
            a = -2.7
        elif s.service_brake:
            a = -1.2
        s.accel_mps2 = a if (s.actual_mps > 0 or a > 0) else 0.0
        s.actual_mps = max(0.0, s.actual_mps + a * self.dt)
        s.authority_m = max(0.0, s.authority_m - s.actual_mps * self.dt)
        drift = s.target_temp_f - s.cabin_temp_f
        s.cabin_temp_f += max(-0.02, min(0.02, drift * 0.01))


# ================================================================ helpers
def hbox(parent=None, spacing=T.SPACE_3, margins=(0, 0, 0, 0)):
    lay = QHBoxLayout(parent)
    lay.setSpacing(spacing)
    lay.setContentsMargins(*margins)
    return lay


def vbox(parent=None, spacing=T.SPACE_3, margins=(0, 0, 0, 0)):
    lay = QVBoxLayout(parent)
    lay.setSpacing(spacing)
    lay.setContentsMargins(*margins)
    return lay


# ================================================================ widgets
class Readout(QFrame):
    """§6.5 telemetry readout."""

    def __init__(self, label: str, unit: str, hero: bool = True):
        super().__init__()
        self.setObjectName("readout")
        lay = vbox(self, T.SPACE_2, (T.SPACE_3,) * 4)
        lay.setAlignment(Qt.AlignCenter)
        cap = QLabel(label.upper(), objectName="roLabel", alignment=Qt.AlignCenter)
        cap.setFont(T.font("label"))
        self.val = QLabel("—", objectName="roValue" if hero else "roValueSm",
                          alignment=Qt.AlignCenter)
        self.val.setMinimumHeight(T.TYPE["hero" if hero else "h1"][0] + 6)
        self.unit = QLabel(unit, objectName="roUnit", alignment=Qt.AlignCenter)
        for w in (cap, self.val, self.unit):
            lay.addWidget(w)
        self._hero = hero
        self.setMinimumHeight(150 if hero else 96)

    def set(self, v):
        self.val.setText(str(v))

    def set_compact(self, compact: bool):
        """Shrink to the H1 size when the numbers drawer is showing the same
        values, so the panels below keep their room."""
        if self._hero:
            self.val.setObjectName("roValueSm" if compact else "roValue")
            self.val.style().unpolish(self.val)
            self.val.style().polish(self.val)
            size = T.TYPE["h1" if compact else "hero"][0]
            self.val.setMinimumHeight(size + 6)
            self.setMinimumHeight(104 if compact else 150)


class Panel(QFrame):
    def __init__(self, title: str, meta: str = "", fill: bool = False):
        super().__init__()
        self.setObjectName("panel")
        outer = vbox(self, T.SPACE_3, (T.SPACE_4, T.SPACE_3, T.SPACE_4, T.SPACE_4))
        head = hbox(spacing=T.SPACE_2)
        t = QLabel(title.upper(), objectName="panelTitle")
        t.setFont(T.font("label"))
        head.addWidget(t)
        head.addStretch(1)
        self.meta = QLabel(meta, objectName="panelMeta")
        head.addWidget(self.meta)
        self.dot = Dot("text-muted")
        head.addWidget(self.dot)
        outer.addLayout(head)
        self.body = vbox(spacing=T.SPACE_3)
        outer.addLayout(self.body, 1 if fill else 0)
        if not fill:
            outer.addStretch(1)


class Segmented(QWidget):
    """Caption above a two-option pill. The caption height is fixed so two of
    these sit on a shared baseline in the header."""

    CAP_H = 14

    def __init__(self, caption: str, left: str, right: str, on_change=None,
                 preselect: bool = True):
        super().__init__()
        self.on_change = on_change
        lay = vbox(self, T.SPACE_1)
        cap = QLabel(caption.upper(), objectName="label")
        cap.setFont(T.font("label"))
        cap.setFixedHeight(self.CAP_H)
        lay.addWidget(cap)
        row = hbox(spacing=0)
        self.left = QPushButton(left, objectName="segLeft", checkable=True,
                                checked=preselect)
        self.right = QPushButton(right, objectName="segRight", checkable=True)
        grp = QButtonGroup(self)
        grp.setExclusive(True)
        for b in (self.left, self.right):
            b.setFixedHeight(T.CONTROL_H_MD)
            grp.addButton(b)
            row.addWidget(b)
        lay.addLayout(row)
        self.left.clicked.connect(lambda: self._fire(False))
        self.right.clicked.connect(lambda: self._fire(True))

    def _fire(self, right: bool):
        if self.on_change:
            self.on_change(right)

    def set_right(self, right: bool):
        (self.right if right else self.left).setChecked(True)


class SpeedDial(QWidget):
    """Rotary speed dial. The centre reads the target; the ring fills to the
    actual speed. Drag or click the ring to set the target in Manual."""

    SWEEP = 270
    START = 225

    def __init__(self, on_set=None):
        super().__init__()
        self.on_set = on_set
        self.target, self.actual, self.limit = 48.0, 26.0, 70.0
        self.interactive = False
        self.setMinimumSize(190, 190)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def set_values(self, target, actual, limit, interactive):
        self.target, self.actual, self.limit = target, actual, limit
        self.interactive = interactive
        self.update()

    def _center_radius(self):
        side = min(self.width(), self.height())
        return QPointF(self.width() / 2, self.height() / 2), side / 2 - 8

    def _value_to_angle(self, v):
        frac = 0.0 if self.limit <= 0 else max(0.0, min(1.0, v / self.limit))
        return self.START - frac * self.SWEEP

    def _angle_to_value(self, deg):
        delta = (self.START - deg) % 360
        if delta > self.SWEEP + (360 - self.SWEEP) / 2:
            delta = 0.0
        return max(0.0, min(1.0, delta / self.SWEEP)) * self.limit

    def mousePressEvent(self, e):
        self._from_mouse(e)

    def mouseMoveEvent(self, e):
        self._from_mouse(e)

    def _from_mouse(self, e):
        if not self.interactive:
            return
        ctr, _ = self._center_radius()
        dx = e.position().x() - ctr.x()
        dy = ctr.y() - e.position().y()
        deg = math.degrees(math.atan2(dy, dx)) % 360
        if self.on_set:
            self.on_set(round(self._angle_to_value(deg)))

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        ctr, r = self._center_radius()
        box = QRectF(ctr.x() - r, ctr.y() - r, r * 2, r * 2)
        w = max(12, int(r * 0.16))

        p.setPen(QPen(QColor(c("bg-sunken")), w, Qt.SolidLine, Qt.FlatCap))
        p.drawArc(box, int(self.START * 16), int(-self.SWEEP * 16))

        frac = 0.0 if self.limit <= 0 else max(0.0, min(1.0, self.actual / self.limit))
        p.setPen(QPen(QColor(c("accent")), w, Qt.SolidLine, Qt.FlatCap))
        p.drawArc(box, int(self.START * 16), int(-self.SWEEP * frac * 16))

        p.setPen(QPen(QColor(c("border-strong")), 1))
        for i in range(int(self.limit // 10) + 1):
            a = math.radians(self._value_to_angle(i * 10))
            r0, r1 = r - w - 2, r - w - 8
            p.drawLine(QPointF(ctr.x() + r0 * math.cos(a), ctr.y() - r0 * math.sin(a)),
                       QPointF(ctr.x() + r1 * math.cos(a), ctr.y() - r1 * math.sin(a)))

        a = math.radians(self._value_to_angle(self.target))
        hr = r - w / 2
        p.setBrush(QColor(c("text-primary") if self.interactive else c("text-muted")))
        p.setPen(QPen(QColor(c("bg-surface")), 3))
        p.drawEllipse(QPointF(ctr.x() + hr * math.cos(a), ctr.y() - hr * math.sin(a)),
                      w * 0.6, w * 0.6)

        f = QFont()
        f.setFamilies(T.FONT_UI_FAMILIES)
        f.setPixelSize(T.TYPE["label"][0])
        f.setWeight(T.W_BOLD)
        p.setFont(f)
        p.setPen(QColor(c("text-muted")))
        p.drawText(QRectF(box.x(), ctr.y() - r * 0.56, box.width(), 16),
                   Qt.AlignHCenter, "TARGET SPEED")

        f2 = QFont()
        f2.setFamilies(T.FONT_MONO_FAMILIES)
        f2.setPixelSize(max(32, int(r * 0.60)))
        f2.setWeight(T.W_BOLD)
        p.setFont(f2)
        p.setPen(QColor(c("text-primary")))
        p.drawText(QRectF(box.x(), ctr.y() - r * 0.34, box.width(), r * 0.72),
                   Qt.AlignHCenter | Qt.AlignVCenter, f"{round(self.target)}")

        f3 = QFont()
        f3.setFamilies(T.FONT_MONO_FAMILIES)
        f3.setPixelSize(13)
        p.setFont(f3)
        p.setPen(QColor(c("text-muted")))
        p.drawText(QRectF(box.x(), ctr.y() + r * 0.34, box.width(), 16),
                   Qt.AlignHCenter, "MPH")
        p.end()


def dot_pixmap(token: str, d: int = 11) -> QPixmap:
    """A filled status dot. Always paired with text — never the only signal (§2)."""
    pm = QPixmap(d + 2, d + 2)
    pm.fill(Qt.transparent)
    q = QPainter(pm)
    q.setRenderHint(QPainter.Antialiasing)
    q.setBrush(QColor(c(token)))
    q.setPen(QPen(QColor(c("bg-surface")), 1))
    q.drawEllipse(1, 1, d, d)
    q.end()
    return pm


def dot_icon(token: str, d: int = 11) -> QIcon:
    return QIcon(dot_pixmap(token, d))


class Dot(QLabel):
    """Standalone status dot for panel headers."""

    def __init__(self, token="text-muted", d=11):
        super().__init__()
        self._d = d
        self.setFixedSize(d + 2, d + 2)
        self.set(token)

    def set(self, token):
        self.setPixmap(dot_pixmap(token, self._d))


class TempDial(QWidget):
    """Thermostat dial. Drag the ring to set the target; the centre reads the
    setpoint and the word above says whether it is heating or cooling."""

    SWEEP = 300
    START = 240
    LO, HI = 60.0, 80.0

    def __init__(self, on_set):
        super().__init__()
        self.on_set = on_set
        self.target = 72.0
        self.actual = 70.0
        self.interactive = True
        self.setMinimumSize(150, 150)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def set_values(self, target, actual, interactive):
        self.target, self.actual, self.interactive = target, actual, interactive
        self.update()

    def mode(self):
        if self.target > self.actual + 0.5:
            return "HEATING", "warning"
        if self.target < self.actual - 0.5:
            return "COOLING", "accent"
        return "HOLDING", "text-muted"

    def _center_radius(self):
        side = min(self.width(), self.height())
        return QPointF(self.width() / 2, self.height() / 2), side / 2 - 6

    def _value_to_angle(self, v):
        frac = (v - self.LO) / (self.HI - self.LO)
        return self.START - max(0.0, min(1.0, frac)) * self.SWEEP

    def mousePressEvent(self, e): self._from_mouse(e)
    def mouseMoveEvent(self, e): self._from_mouse(e)

    def _from_mouse(self, e):
        if not self.interactive:
            return
        ctr, _ = self._center_radius()
        deg = math.degrees(math.atan2(ctr.y() - e.position().y(),
                                      e.position().x() - ctr.x())) % 360
        delta = (self.START - deg) % 360
        if delta > self.SWEEP + (360 - self.SWEEP) / 2:
            delta = 0.0
        frac = max(0.0, min(1.0, delta / self.SWEEP))
        self.on_set(round(self.LO + frac * (self.HI - self.LO)))

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        ctr, r = self._center_radius()
        word, token = self.mode()

        # tick ring, the way a thermostat face reads
        n = 60
        for i in range(n + 1):
            frac = i / n
            a = math.radians(self.START - frac * self.SWEEP)
            value = self.LO + frac * (self.HI - self.LO)
            on = value <= self.target + 1e-6
            p.setPen(QPen(QColor(c(token if on else "border")), 3 if on else 2))
            r0, r1 = r, r - (14 if i % 15 == 0 else 9)
            p.drawLine(QPointF(ctr.x() + r0 * math.cos(a), ctr.y() - r0 * math.sin(a)),
                       QPointF(ctr.x() + r1 * math.cos(a), ctr.y() - r1 * math.sin(a)))

        # setpoint marker
        a = math.radians(self._value_to_angle(self.target))
        p.setPen(QPen(QColor(c("text-primary")), 4))
        p.drawLine(QPointF(ctr.x() + r * math.cos(a), ctr.y() - r * math.sin(a)),
                   QPointF(ctr.x() + (r - 18) * math.cos(a), ctr.y() - (r - 18) * math.sin(a)))

        box = QRectF(ctr.x() - r, ctr.y() - r, r * 2, r * 2)
        f = QFont(); f.setFamilies(T.FONT_UI_FAMILIES)
        f.setPixelSize(T.TYPE["label"][0]); f.setWeight(T.W_BOLD)
        p.setFont(f); p.setPen(QColor(c(token)))
        p.drawText(QRectF(box.x(), ctr.y() - r * 0.52, box.width(), 16),
                   Qt.AlignHCenter, word)

        f2 = QFont(); f2.setFamilies(T.FONT_MONO_FAMILIES)
        f2.setPixelSize(max(30, int(r * 0.66))); f2.setWeight(T.W_BOLD)
        p.setFont(f2); p.setPen(QColor(c("text-primary")))
        p.drawText(QRectF(box.x(), ctr.y() - r * 0.30, box.width(), r * 0.70),
                   Qt.AlignHCenter | Qt.AlignVCenter, f"{round(self.target)}")

        f3 = QFont(); f3.setFamilies(T.FONT_MONO_FAMILIES); f3.setPixelSize(12)
        p.setFont(f3); p.setPen(QColor(c("text-muted")))
        p.drawText(QRectF(box.x(), ctr.y() + r * 0.34, box.width(), 15),
                   Qt.AlignHCenter, "°F TARGET")
        p.end()


class SignalHead(QWidget):
    """Four lamps, one per aspect. Position identifies the state and the lit
    lamp is a solid fill, so it reads without colour (§2, §8)."""

    def __init__(self):
        super().__init__()
        self.aspect = "YELLOW"
        self.setMinimumSize(86, 150)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)

    def set_aspect(self, a):
        if a != self.aspect:
            self.aspect = a
            self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        pitch = self.height() / 4.5
        lamp_r = min(pitch * 0.36, self.width() * 0.26)
        body_w = lamp_r * 2 + 24
        body = QRectF((self.width() - body_w) / 2, 0, body_w, self.height())

        p.setPen(QPen(QColor(c("border-strong")), 1))
        p.setBrush(QColor(c("bg-sunken")))
        p.drawRoundedRect(body.adjusted(1, 1, -1, -1), T.RADIUS_MD, T.RADIUS_MD)

        cx = self.width() / 2
        top = (self.height() - pitch * 4) / 2
        for i, name in enumerate(ASPECTS):
            cy = top + pitch / 2 + i * pitch
            lit = name == self.aspect
            if lit:
                p.setBrush(QColor(c(ASPECT_TOKEN[name])))
                p.setPen(QPen(QColor(c(ASPECT_TOKEN[name])), 2))
            else:
                p.setBrush(QColor(c("bg-surface")))
                p.setPen(QPen(QColor(c("border-strong")), 1))
            p.drawEllipse(QPointF(cx, cy), lamp_r, lamp_r)
            if name == "SUPER GREEN":
                p.setBrush(Qt.NoBrush)
                p.setPen(QPen(QColor(c(ASPECT_TOKEN[name]) if lit else c("border-strong")), 2))
                p.drawEllipse(QPointF(cx, cy), lamp_r + 4, lamp_r + 4)
        p.end()


class GainsDialog(QDialog):
    """Engineer-only, and one-shot: gains are commissioned once at start-up and
    frozen for the run. Opens when the operator switches to ENGINEER."""

    def __init__(self, core: "ControllerCore", parent=None):
        super().__init__(parent)
        self.core = core
        self.locked = False
        self.on_locked = None          # console hooks this to retire the role
        self.setWindowTitle("Control gains")
        self.setModal(False)
        self.setFixedWidth(360)

        lay = vbox(self, T.SPACE_3, (T.SPACE_5,) * 4)
        title = QLabel("CONTROL GAINS", objectName="panelTitle")
        title.setFont(T.font("label"))
        lay.addWidget(title)
        lay.addWidget(QLabel("Set once at start-up. Cannot be changed afterwards.",
                             objectName="muted", wordWrap=True))

        self.in_kp = QLineEdit(f"{core.state.kp:.0f}")
        self.in_ki = QLineEdit(f"{core.state.ki:.0f}")
        self._steps = []
        for text, field, step in (("Kp — proportional gain", self.in_kp, 50.0),
                                  ("Ki — integral gain", self.in_ki, 5.0)):
            cap = QLabel(text.upper(), objectName="label")
            cap.setFont(T.font("label"))
            lay.addWidget(cap)
            row = hbox(spacing=T.SPACE_2)
            minus = QPushButton("−", objectName="step")
            plus = QPushButton("+", objectName="step")
            self._steps += [minus, plus]
            field.setAlignment(Qt.AlignCenter)
            minus.clicked.connect(lambda _=False, f=field, d=-step: self._bump(f, d))
            plus.clicked.connect(lambda _=False, f=field, d=step: self._bump(f, d))
            row.addWidget(minus)
            row.addWidget(field, 1)
            row.addWidget(plus)
            lay.addLayout(row)

        lay.addWidget(QLabel(
            "Changes how quickly the train reaches its target speed. The brake "
            "path is independent, so gains can never change whether it stops.",
            objectName="muted", wordWrap=True))

        self.applied = QLabel("", objectName="muted", wordWrap=True)
        lay.addWidget(self.applied)

        btns = hbox(spacing=T.SPACE_2)
        close = QPushButton("Close")
        close.setMinimumHeight(T.CONTROL_H_MD)
        close.clicked.connect(self.hide)
        self.apply = QPushButton("Set gains", objectName="primary")
        self.apply.setMinimumHeight(T.CONTROL_H_LG)
        self.apply.clicked.connect(self._apply)
        btns.addWidget(close, 1)
        btns.addWidget(self.apply, 2)
        lay.addLayout(btns)

    @staticmethod
    def _bump(field: QLineEdit, delta: float):
        try:
            v = float(field.text())
        except ValueError:
            v = 0.0
        field.setText(f"{max(0.0, v + delta):.0f}")

    def lock(self):
        self.locked = True
        for w in [self.in_kp, self.in_ki, self.apply] + self._steps:
            w.setEnabled(False)

    def _apply(self):
        if self.locked:
            return
        s = self.core.state
        try:
            s.kp = float(self.in_kp.text())
            s.ki = float(self.in_ki.text())
            self.core.integral = 0.0
            self.core.armed = True          # commissioning starts the run
            self.lock()
            self.applied.setText(
                f"Set to Kp {s.kp:.0f}, Ki {s.ki:.0f}. Fixed for this run — "
                f"this panel cannot be reopened.")
            if self.on_locked:
                QTimer.singleShot(1500, self.on_locked)   # let them read it first
        except ValueError:
            self.applied.setText("Kp and Ki must be numbers.")


class KVPanel(QFrame):
    """Titled block of label/value rows — the numbers drawer."""

    def __init__(self, title: str, rows: list):
        super().__init__()
        self.setObjectName("panel")
        lay = vbox(self, 0, (T.SPACE_3, T.SPACE_2, T.SPACE_3, T.SPACE_2))
        t = QLabel(title.upper(), objectName="panelTitle")
        t.setFont(T.font("label"))
        lay.addWidget(t)
        lay.addSpacing(T.SPACE_2)
        self.values = {}
        for i, key in enumerate(rows):
            row = QFrame(objectName="kvRow" if i < len(rows) - 1 else "kvRowLast")
            r = hbox(row, T.SPACE_2, (0, 4, 0, 4))
            k = QLabel(key, objectName="small")
            v = QLabel("—", objectName="mono")
            v.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            r.addWidget(k)
            r.addStretch(1)
            r.addWidget(v)
            lay.addWidget(row)
            self.values[key] = v

    def set(self, key, text):
        self.values[key].setText(text)


# ================================================================ window
class Console(QWidget):
    def __init__(self, core: ControllerCore):
        super().__init__()
        self.core = core
        self.setWindowTitle("HW Train Controller")
        self.setFixedSize(1440, 900)
        self._announce_locked = False
        self.operator = None          # None | "driver" | "engineer"
        self._build()
        self.gains_dialog = GainsDialog(self.core, self)
        self.gains_dialog.on_locked = self._retire_engineer
        self._apply_gating()
        self._update_train_dot()
        self.setFocus()          # no control starts focused, so none looks chosen

        self.t_control = QTimer(self)
        self.t_control.timeout.connect(self.core.step)
        self.t_control.start(int(1000 / CONTROL_HZ))

        self.t_ui = QTimer(self)
        self.t_ui.timeout.connect(self.refresh)
        self.t_ui.start(int(1000 / UI_HZ))

        self.elapsed = QTime(0, 0, 0)

    # ------------------------------------------------------------ build
    def _build(self):
        root = vbox(self, 0)
        root.addWidget(self._header())

        # shown on its own until an operator signs in
        self.signin = QLabel("Select an operator to unlock the console.",
                             objectName="signinNote", alignment=Qt.AlignCenter)
        root.addWidget(self.signin, 1)

        # everything else lives in here so it can be hidden as one block
        self.body_area = QWidget()
        body = vbox(self.body_area, 0)
        readouts = self._readouts()
        body.addWidget(self._disclosure())
        content = vbox(spacing=T.SPACE_4, margins=(T.SPACE_4,) * 4)
        content.addWidget(self.numbers)
        content.addLayout(readouts)
        content.addLayout(self._panels(), 1)
        body.addLayout(content, 1)
        root.addWidget(self.body_area, 1)

    def _header(self):
        bar = QFrame(objectName="header")
        bar.setFixedHeight(72)
        lay = hbox(bar, T.SPACE_5, (T.SPACE_5, 0, T.SPACE_5, 0))
        lay.setAlignment(Qt.AlignVCenter)
        lay.addWidget(QLabel("HW TRAIN CONTROLLER", objectName="appTitle"))
        lay.addStretch(1)

        self.seg_operator = Segmented("Operator", "DRIVER", "ENGINEER",
                                      self.set_engineer, preselect=False)
        self.seg_mode = Segmented("Operating mode", "AUTOMATIC", "MANUAL", self.set_manual)
        for seg in (self.seg_operator, self.seg_mode):
            seg.setFixedWidth(200)
            for b in (seg.left, seg.right):
                b.setFixedHeight(T.CONTROL_H_MD)

        pick = vbox(spacing=T.SPACE_1)
        cap = QLabel("CURRENT SELECTED TRAIN", objectName="label")
        cap.setFont(T.font("label"))
        cap.setFixedHeight(Segmented.CAP_H)
        self.train_pick = QComboBox()
        self.train_pick.addItems(["T-114 · GREEN LINE", "T-142 · GREEN LINE", "R-301 · RED LINE"])
        self.train_pick.setFixedWidth(181)
        self.train_pick.setFixedHeight(T.CONTROL_H_MD)
        self.train_dot = Dot("green-line", 14)
        self.train_pick.currentIndexChanged.connect(self._update_train_dot)
        picker_row = hbox(spacing=T.SPACE_1)
        picker_row.addWidget(self.train_pick)
        picker_row.addWidget(self.train_dot)
        pick.addWidget(cap)
        pick.addLayout(picker_row)

        # no fixed height here: the pills and combo need their full sizeHint,
        # which is what was clipping their bottoms
        group = hbox(spacing=T.SPACE_5)
        group.addWidget(self.seg_operator)
        group.addWidget(self.seg_mode)
        group.addLayout(pick)
        wrap = QWidget()
        wrap.setLayout(group)
        lay.addWidget(wrap, 0, Qt.AlignVCenter)

        lay.addSpacing(T.SPACE_5)
        self.clock = QLabel("00:00:00", objectName="clock")
        lay.addWidget(self.clock)
        return bar

    def _disclosure(self):
        self.btn_numbers = QPushButton("▾  SHOW ALL NUMBERS", objectName="disclosure")
        self.btn_numbers.setCheckable(True)
        self.btn_numbers.toggled.connect(self._toggle_numbers)

        self.kv_motion = KVPanel("Motion", [
            "Current speed", "Target speed", "Commanded speed · CTC",
            "Speed limit · GREEN I", "Acceleration"])
        self.kv_engine = KVPanel("Engine & brakes", [
            "Power command", "Max engine power", "Service brake",
            "Emergency brake", "Gains · Kp / Ki"])
        self.kv_status = KVPanel("Equipment status", [
            "Engine", "Brake", "Signal pickup", "Authority", "Cabin setpoint"])

        self.numbers = QWidget()
        nl = hbox(self.numbers, T.SPACE_4)
        for w in (self.kv_motion, self.kv_engine, self.kv_status):
            nl.addWidget(w, 1)
        self.numbers.setVisible(False)
        return self.btn_numbers

    def _toggle_numbers(self, open_):
        self.btn_numbers.setText(
            f"{'▴' if open_ else '▾'}  {'HIDE' if open_ else 'SHOW'} ALL NUMBERS")
        self.numbers.setVisible(open_)
        for r in (self.ro_speed, self.ro_limit, self.ro_temp, self.ro_stop):
            r.set_compact(open_)

    def _readouts(self):
        row = hbox(spacing=T.SPACE_4)
        self.ro_speed = Readout("Your speed", "MPH")
        self.ro_limit = Readout("Speed limit", "MPH")
        self.ro_temp = Readout("Cabin temperature", "°F")
        self.ro_stop = Readout("Stop in", "FT")
        for r in (self.ro_speed, self.ro_limit, self.ro_temp, self.ro_stop):
            row.addWidget(r)
        return row

    COL_W = (1440 - 2 * T.SPACE_4 - 3 * T.SPACE_4) // 4   # 340 px

    def _panels(self):
        """Fixed-width columns. Nothing in a panel can change the layout of
        another panel, so the console never shifts under the operator's hand."""
        row = hbox(spacing=T.SPACE_4)
        for build in (self._speed_panel, self._stop_panel,
                      self._cabin_panel, self._signal_column):
            w = build()
            w.setFixedWidth(self.COL_W)
            row.addWidget(w)
        row.addStretch(0)
        return row

    # -------------------------------------------------- speed
    def _speed_panel(self):
        """Commanded speed reads above; the dial sets the target below."""
        panel = Panel("Speed", "FROM CTC", fill=True)
        self.ro_cmd = Readout("Commanded speed · CTC", "MPH", hero=False)
        panel.body.addWidget(self.ro_cmd)

        self.dial = SpeedDial(on_set=self.core.set_target_mph)
        panel.body.addWidget(self.dial, 1)

        self.lbl_dial_hint = QLabel("", objectName="muted",
                                    alignment=Qt.AlignCenter, wordWrap=True)
        self.lbl_dial_hint.setFixedHeight(34)   # two lines, always
        panel.body.addWidget(self.lbl_dial_hint)
        self.speed_panel = panel
        return panel

    def _update_train_dot(self, _index=0):
        """Line identity at a glance: green dot for the green line, red for red."""
        text = self.train_pick.currentText()
        self.train_dot.set("red-line" if "RED" in text else "green-line")

    def _bump_field(self, field: QLineEdit, delta: float):
        try:
            v = float(field.text())
        except ValueError:
            v = 0.0
        field.setText(f"{max(0.0, v + delta):.0f}")

    # -------------------------------------------------- stop
    def _stop_panel(self):
        panel = Panel("Stop the train", fill=True)
        self.stop_panel = panel
        self.btn_estop = QPushButton("EMERGENCY BRAKE", objectName="estop")
        self.btn_estop.setMinimumSize(T.SAFETY_MIN_W, T.SAFETY_MIN_H)
        self.btn_estop.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.btn_estop.setCheckable(True)
        self.btn_estop.clicked.connect(self.toggle_estop)
        panel.body.addWidget(self.btn_estop, 3)

        panel.body.addSpacing(T.SPACE_5)          # §7 separation

        self.btn_service = QPushButton("SERVICE BRAKE", objectName="svc")
        self.btn_service.setMinimumHeight(T.SAFETY_MIN_H)
        self.btn_service.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.btn_service.setCheckable(True)
        self.btn_service.clicked.connect(self.toggle_service)
        panel.body.addWidget(self.btn_service, 2)

        self.lbl_brake = QLabel("", objectName="muted", wordWrap=True,
                                alignment=Qt.AlignHCenter)
        self.lbl_brake.setFixedHeight(34)     # two lines, always — never resizes
        panel.body.addWidget(self.lbl_brake)
        return panel

    # -------------------------------------------------- doors, cabin, lights
    def _cabin_panel(self):
        panel = Panel("Doors, cabin & lights", fill=True)
        panel.body.setSpacing(T.SPACE_2)
        self.cabin_panel = panel

        doors = hbox(spacing=T.SPACE_2)
        self.btn_left = QPushButton("OPEN LEFT", objectName="tile", checkable=True)
        self.btn_right = QPushButton("OPEN RIGHT", objectName="tile", checkable=True)
        tile_w = (self.COL_W - 2 * T.SPACE_4 - T.SPACE_2) // 2
        for b in (self.btn_left, self.btn_right):
            b.setMinimumHeight(52)
            b.setFixedWidth(tile_w)
            b.setIconSize(QSize(11, 11))
            b.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
            doors.addWidget(b, 1)
        panel.body.addLayout(doors, 2)

        self.temp_dial = TempDial(self.set_temp)
        panel.body.addWidget(self.temp_dial, 5)

        lights = hbox(spacing=T.SPACE_2)
        self.btn_lights = QPushButton("LIGHTS ON", objectName="tile",
                                      checkable=True, checked=True)
        self.btn_head = QPushButton("HEADLIGHTS ON", objectName="tile",
                                    checkable=True, checked=True)
        for b in (self.btn_lights, self.btn_head):
            b.setMinimumHeight(52)
            b.setFixedWidth(tile_w)
            b.setIconSize(QSize(11, 11))
            b.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
            lights.addWidget(b, 1)
        panel.body.addLayout(lights, 2)
        return panel

    # -------------------------------------------------- announce + signal
    def _signal_column(self):
        st = self.core.state
        col = QWidget()
        lay = vbox(col, T.SPACE_4)

        ann = Panel("Announcements", f"NEXT: {st.next_station}")
        ann.dot.hide()
        self.btn_announce = QPushButton(
            f"Announce now\n{st.next_station.title()} · arrives {st.arrives}")
        self.btn_announce.setMinimumHeight(64)
        self.btn_announce.clicked.connect(self.announce)
        ann.body.addWidget(self.btn_announce)
        lay.addWidget(ann)

        sig = Panel("Next signal", st.signal_block, fill=True)
        sig.dot.hide()
        self.signal_panel = sig
        self.head = SignalHead()
        holder = hbox(spacing=0)
        holder.addStretch(1)
        holder.addWidget(self.head, 1)
        holder.addStretch(1)
        sig.body.addLayout(holder, 1)
        self.lbl_aspect = QLabel(st.next_signal, objectName="aspect", alignment=Qt.AlignCenter)
        self.lbl_aspect_note = QLabel(ASPECT_TEXT[st.next_signal], objectName="small",
                                      alignment=Qt.AlignCenter, wordWrap=True)
        self.lbl_aspect_note.setFixedHeight(34)
        sig.body.addWidget(self.lbl_aspect)
        sig.body.addWidget(self.lbl_aspect_note)
        lay.addWidget(sig, 1)
        return col

    # ------------------------------------------------------------ actions
    def set_manual(self, manual):
        self.core.state.manual = manual
        self.seg_mode.set_right(manual)
        self._apply_gating()

    def _apply_gating(self):
        """Nothing exists until an operator signs in. After that the driver may
        only act in Manual; Automatic locks the console. The emergency brake
        stays live for any signed-in operator, in either mode (§7)."""
        signed_in = self.operator is not None
        driving = signed_in and self.operator == "driver" and self.core.state.manual

        self.signin.setVisible(not signed_in)
        self.body_area.setVisible(signed_in)
        self.seg_mode.setEnabled(signed_in)
        self.train_pick.setEnabled(signed_in)
        if not signed_in:
            return

        self.btn_numbers.setEnabled(True)

        for w in (self.btn_left, self.btn_right, self.btn_lights, self.btn_head,
                  self.btn_announce, self.btn_service):
            w.setEnabled(driving)
        self.temp_dial.setEnabled(driving)
        self.temp_dial.interactive = driving
        self.btn_estop.setEnabled(True)      # pullable in Automatic too

    def set_engineer(self, engineer):
        # gains are commissioned once; after that the engineer role is spent
        if engineer and self.gains_dialog.locked:
            self.seg_operator.set_right(False)
            self.operator = "driver"
            self.core.state.engineer = False
            self._apply_gating()
            return

        self.operator = "engineer" if engineer else "driver"
        self.core.state.engineer = engineer
        self._apply_gating()
        if engineer:
            self.gains_dialog.in_kp.setText(f"{self.core.state.kp:.0f}")
            self.gains_dialog.in_ki.setText(f"{self.core.state.ki:.0f}")
            self.gains_dialog.applied.setText("")
            self.gains_dialog.show()
            self.gains_dialog.raise_()
        else:
            self.gains_dialog.hide()

    def _retire_engineer(self):
        """Once the gains are committed: close the panel, disable the ENGINEER
        role for the rest of the run and hand the console to the driver. The
        option stays visible but disabled, never hidden (§8)."""
        self.gains_dialog.hide()
        self.seg_operator.right.setEnabled(False)
        self.seg_operator.right.setToolTip("Gains are set for this run.")
        self.seg_operator.set_right(False)
        self.operator = "driver"
        self.core.state.engineer = False
        self._apply_gating()


    def set_temp(self, value):
        self.core.state.target_temp_f = max(60.0, min(80.0, float(value)))

    def toggle_estop(self):
        """One button engages and releases. §7 keeps engagement immediate;
        release is refused unless the train is stopped and the fault is gone."""
        s = self.core.state
        if not s.emergency_brake:
            s.emergency_brake = True
            self.lbl_brake.setText("Emergency brake engaged. Press again to release.")
        elif self.core.release_emergency():
            self.lbl_brake.setText("")
        else:
            why = ", ".join(self.core.last_reasons).lower() or "the train is still moving"
            self.lbl_brake.setText(f"Cannot release: {why}.")

    def toggle_service(self):
        self.core.state.service_request = not self.core.state.service_request

    def announce(self):
        self._announce_locked = True
        self.btn_announce.setEnabled(False)
        self.btn_announce.setText("Announcing…")
        QTimer.singleShot(ANNOUNCE_LOCKOUT_MS, self._announce_done)

    def _announce_done(self):
        self._announce_locked = False
        st = self.core.state
        self.btn_announce.setText(
            f"Announce now\n{st.next_station.title()} · arrives {st.arrives}")
        self.btn_announce.setEnabled(True)

    # ------------------------------------------------------------ refresh
    def refresh(self):
        s = self.core.state

        self.ro_speed.set(round(s.actual_mph))
        self.ro_limit.set(round(s.limit_mph))
        self.ro_temp.set(round(s.cabin_temp_f))
        self.ro_stop.set(f"{round(s.authority_m * M_TO_FT):,}")

        self.ro_cmd.set(round(s.commanded_mph))
        self.dial.set_values(s.target_mph, s.actual_mph, s.limit_mph, s.manual)
        self.lbl_dial_hint.setText(
            "Waiting for the engineer to set the control gains."
            if not self.core.armed else
            "Drag the dial to set your target speed."
            if s.manual else
            f"Set by the CTC. Switch to Manual Mode to take control.")
        self.speed_panel.meta.setText("DRIVER" if s.manual else "FROM CTC")

        # every control says its state in words AND carries a matching dot (§2)
        s.lights = self.btn_lights.isChecked()
        s.headlights = self.btn_head.isChecked()
        s.doors_left = self.btn_left.isChecked()
        s.doors_right = self.btn_right.isChecked()

        self.btn_lights.setText(f"LIGHTS {'ON' if s.lights else 'OFF'}")
        self.btn_lights.setIcon(dot_icon("success" if s.lights else "text-muted"))
        self.btn_head.setText(f"HEADLIGHTS {'ON' if s.headlights else 'OFF'}")
        self.btn_head.setIcon(dot_icon("success" if s.headlights else "text-muted"))

        self.btn_left.setText(("CLOSE" if s.doors_left else "OPEN") + " LEFT")
        self.btn_left.setIcon(dot_icon("info" if s.doors_left else "text-muted"))
        self.btn_right.setText(("CLOSE" if s.doors_right else "OPEN") + " RIGHT")
        self.btn_right.setIcon(dot_icon("info" if s.doors_right else "text-muted"))

        self.temp_dial.set_values(s.target_temp_f, s.cabin_temp_f,
                                  self.temp_dial.interactive)

        # panel header dots
        self.speed_panel.dot.set("accent" if s.manual else "text-muted")
        self.stop_panel.dot.set("brake-emergency" if s.emergency_brake
                                else "brake-service" if s.service_request
                                else "success")
        if self.btn_left.isEnabled():
            self.cabin_panel.dot.set("info" if (s.doors_left or s.doors_right) else "success")
        else:
            self.cabin_panel.dot.set("text-muted")   # locked: not reachable now


        if self.operator == "driver" and not s.manual:
            self.btn_announce.setText(
                f"Announced automatically\n{s.next_station.title()} · arrives {s.arrives}")
        elif not self._announce_locked:
            self.btn_announce.setText(
                f"Announce now\n{s.next_station.title()} · arrives {s.arrives}")

        self.btn_estop.setChecked(s.emergency_brake)
        self.btn_service.setChecked(s.service_request)
        if s.emergency_brake:
            self.lbl_brake.setText(self.lbl_brake.text() or
                                   "Emergency brake engaged. Press again to release.")
        elif s.service_request:
            self.lbl_brake.setText("Service brake engaged. Press again to release.")
        elif self.lbl_brake.text().startswith("Service"):
            self.lbl_brake.setText("")

        self.head.set_aspect(s.next_signal)
        self.lbl_aspect.setText(s.next_signal)
        self.lbl_aspect_note.setText(
            f"{ASPECT_TEXT[s.next_signal]}   {round(s.authority_m * M_TO_FT):,} FT away")

        if self.numbers.isVisible():
            self.kv_motion.set("Current speed", f"{round(s.actual_mph)} MPH")
            self.kv_motion.set("Target speed", f"{round(s.target_mph)} MPH")
            self.kv_motion.set("Commanded speed · CTC", f"{round(s.commanded_mph)} MPH")
            self.kv_motion.set("Speed limit · GREEN I", f"{round(s.limit_mph)} MPH")
            self.kv_motion.set("Acceleration", f"{s.accel_mps2:.1f} M/S²")
            self.kv_engine.set("Power command", f"{s.power_w:,.0f} W")
            self.kv_engine.set("Max engine power", f"{MAX_POWER_W:,.0f} W")
            self.kv_engine.set("Service brake", "ENGAGED" if s.service_brake else "RELEASED")
            self.kv_engine.set("Emergency brake", "ENGAGED" if s.emergency_brake else "RELEASED")
            self.kv_engine.set("Gains · Kp / Ki", f"{s.kp:.0f} / {s.ki:.0f}")
            self.kv_status.set("Engine", "FAULT" if s.faults else "NORMAL")
            self.kv_status.set("Brake", "NORMAL")
            self.kv_status.set("Signal pickup", "NORMAL")
            self.kv_status.set("Authority", f"→ {s.authority_block}")
            self.kv_status.set("Cabin setpoint", f"{round(s.target_temp_f)} °F")

        if self.core.armed:
            self.elapsed = self.elapsed.addMSecs(int(1000 / UI_HZ))
        self.clock.setText(self.elapsed.toString("HH:mm:ss"))


# ================================================================ main
def main() -> int:
    hw = PiHardware() if "--real" in sys.argv else HardwareInterface()
    core = ControllerCore(hw)
    app = QApplication(sys.argv)
    app.setStyleSheet(T.build_qss())
    win = Console(core)
    win.show()
    try:
        return app.exec()
    finally:
        hw.close()


if __name__ == "__main__":
    raise SystemExit(main())