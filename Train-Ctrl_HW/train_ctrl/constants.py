"""Rates, plant figures, detection thresholds and domain vocabulary."""

from .units import KMH_PER_MPS

# ---------------------------------------------------------------- rates
# One fixed step of simulated time, truth D006 / D017: 10x runs more
# ticks per second, never a longer step (REQUIREMENTS.md M11).
TICK_S = 0.1
CONTROL_HZ = 10                 # ticks per second at real time
CLOCK_START = (5, 0, 0)         # D017's clock starts at 05:00:00
UI_HZ = 10
ANNOUNCE_LOCKOUT_MS = 5000
GAINS_HANDOVER_MS = 1500
# Station dwell, truth D007: the CTC Office schedules it, and the
# controller enforces it, holding a station stop at least this long
# with the doors open, whatever the Track Signal says meanwhile.
DWELL_S = 45.0

# Truth modules/train-model.md: 4 x 120 kW, the data sheet's 120 kW
# per motor rather than for the whole car (provisional, pending the
# instructor). The car's 0.5 m/s^2 force cap now binds up to about
# 67 km/h, nearly the whole 70 km/h range, as the sheet quotes it.
MAX_POWER_W = 480_000.0

# ---------------------------------------------------------------- cabin
#: Thermostat range, as the operator sets it (degrees F).
CABIN_MIN_F, CABIN_MAX_F = 60.0, 80.0
#: Where a new train's cabin starts, and what it is set to (Celsius).
DEFAULT_CABIN_TEMP_C = 21.1
DEFAULT_TARGET_TEMP_C = 22.2
# The toy cabin closes a hundredth of the gap each control tick,
# capped so a large step still warms or cools gradually.
CABIN_DRIFT_FRACTION = 0.01
CABIN_DRIFT_MAX_C = 0.011

# --------------------------------------- plant model (toy, replaced by
# the Train Model)
#     F = P / v        a = F / M        v = v + a dt
# F = P / v is undefined at a stand, so the division uses a floor
# speed; below it the train pulls its full tractive effort.
# Blackpool Flexity 2 data sheet: 0.5 m/s^2 medium acceleration from
# 0 to 70 km/h, 1.2 m/s^2 on the service brake, 2.73 on the
# emergency brake, 70 km/h maximum. Mass is 40.9 t empty and 56.7 t
# at 4 pass./m^2, and the acceleration figure is quoted at 2/3 load,
# so the plant runs at that mass.
MASS_KG = 51_433.0
MAX_ACCEL_MPS2 = 0.5            # and the car will not exceed it
MAX_FORCE_N = MASS_KG * MAX_ACCEL_MPS2
# The car's data-sheet top speed: no target goes above it, and it is
# the speed dial's fixed full scale (REQUIREMENTS.md M1).
MAX_SPEED_MPS = 70 / KMH_PER_MPS
V_FLOOR_MPS = 1.0               # below which F = P / v is capped
SERVICE_DECEL_MPS2 = 1.2
EBRAKE_DECEL_MPS2 = 2.73
# How far over target the train may drift before the brake helps.
# Kept to about a tenth of a mile an hour, so a slow-down settles on
# its target (35 -> 30 mph ends at 30.08 at the 0.1 s step).
SERVICE_BAND_MPS = 0.05
# Rolling resistance, from truth modules/train-model.md. Applied only
# under an engine or a brake failure for now; see ControllerCore._plant().
ROLLING_RESISTANCE_COEFF = 0.002
GRAVITY_MPS2 = 9.81
ROLLING_DECEL_MPS2 = ROLLING_RESISTANCE_COEFF * GRAVITY_MPS2
# Below this the emergency brake may be released (D011).
STANDSTILL_MPS = 0.1
# Ticks between a command and the Train Model's report of it under the
# central harness: each module reads the others' outputs from the tick
# before (truth D017), so a command sent on one tick is acted on the
# next, and its report arrives the tick after that. A reported
# emergency brake this controller commanded within these ticks is its
# own command coming back, not a passenger pull.
ECHO_TICKS = 2
# Below this, with nothing asked of it, the toy plant settles to an
# exact stand instead of creeping.
SETTLE_MPS = 0.12

# ---------------------------------------------------- failure detection
# The Train Model no longer reports its failures, so the controller
# infers them. Rules and thresholds are this controller's own design;
# see ControllerCore.detect_failures() and OPEN_ISSUES.md.
BRAKE_DETECT_S = 0.5
# Engine failure (Kevin Schillinger, 2026-10-21): flag falling speed
# with power commanded and no brake anywhere in the window, never a
# train holding its target. A failed engine zeroes traction (truth
# modules/train-model.md), so the slowest a real failure can show is
# rolling resistance alone on the flat: C_rr x g = 0.0196 m/s^2. Any
# up-grade makes it faster, and it never lets up.
#
# The window: a few seconds longer than the old 2 s, so one tick's
# jitter cannot carry it, and long enough that rolling resistance
# alone loses about twice ENGINE_FALL_MPS across it. 60 steps.
ENGINE_DETECT_S = 6.0
# The window is read as half-second means (5 steps each), so a
# tick-to-tick wobble in the reported speed cancels out instead of
# reading as a fall.
ENGINE_SMOOTH_S = 0.5
# The fall that counts, first mean to last: more than the control
# band, the most the PI lets the speed wander while holding a target,
# so a train doing what it was told never reaches it. Rolling
# resistance alone loses 0.108 m/s across the 5.5 s between the first
# and last means, about twice this.
ENGINE_FALL_MPS = SERVICE_BAND_MPS
# And the fall has to be steady: every mean within this fraction of
# the fall of the straight line from the first mean to the last. A
# dead engine leaves a constant resistance and so a straight fall.
# Running onto a grade (Green 7 is 5 %) the speed sags too, with power
# on and no brake, by up to half a metre a second, but the PI catches
# it within a few seconds, so the sag curves out and never reads as
# straight across a 6 s window (tests/test_engine_detection.py).
ENGINE_STRAIGHT_FRACTION = 0.1
# Within this of its target the train is holding the speed it was
# told to: never an engine failure, whatever the power (the control
# band again).
ENGINE_HOLD_BAND_MPS = SERVICE_BAND_MPS
PICKUP_DETECT_MIN_BLOCKS = 2
# Stand-in block length for the toy plant's authority countdown.
BLOCK_LENGTH_M = 100.0

# ---------------------------------------------------------------- gains
# Pull the full 0.5 m/s^2 from a stand, reach 70 km/h in about three
# quarters of a minute, then hold within a tenth of a mph of target.
DEFAULT_KP = 400_000.0          # W per m/s of error
DEFAULT_KI = 8_000.0            # W per (m/s x s) of accumulated error

# ----------------------------------------------------------- vocabulary
ASPECTS = ["RED", "YELLOW", "GREEN", "SUPER GREEN"]
ASPECT_TEXT = {
    "RED": "Stop.",
    "YELLOW": "Slow down.",
    "GREEN": "Continue to cruise.",
    "SUPER GREEN": "All clear ahead.",
}

#: The Train Model's three failures (truth modules/train-model.md),
#: in the order the bench lists them.
FAILURES = ("engine", "signal_pickup", "brake")
FAILURE_TEXT = {
    "engine": "engine failure",
    "signal_pickup": "signal pickup failure",
    "brake": "brake failure",
}

#: Beacon platform sides (truth signals/beacon.md).
BEACON_SIDES = ("L", "R", "LR")

#: Lines a train can be spawned on, and the id prefix each one uses.
LINES = {"GREEN LINE": "T", "RED LINE": "R"}

#: Real time per simulated second, as the bench offers it.
SIM_RATES = (1, 10)