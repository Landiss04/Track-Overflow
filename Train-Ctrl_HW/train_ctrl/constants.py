"""Rates, plant figures, detection thresholds and domain vocabulary."""

from .units import KMH_PER_MPS

# ---------------------------------------------------------------- rates
# One fixed step of simulated time, truth D006 / D017: 10x runs more
# ticks per second, never a longer step (REQUIREMENTS.md M11).
TICK_S = 0.1
CONTROL_HZ = 10                 # ticks per second at real time
# D017's clock starts at 05:00:00, counted in seconds since midnight
# as utils/system_clock.py does.
CLOCK_START_S = 5 * 3600.0
UI_HZ = 10
ANNOUNCE_LOCKOUT_MS = 5000
# Automatic lights (REQUIREMENTS.md M8): on at 18:00, off at 06:00,
# in seconds since midnight.
NIGHT_START_S = 18 * 3600.0
NIGHT_END_S = 6 * 3600.0
GAINS_HANDOVER_MS = 1500

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

# ------------------------------- bench simulation (bench_sim.py), and
# the engine-failure rule in control.py, which still uses the mass and
# force cap (OPEN_ISSUES.md #28)
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
# The car's data-sheet top speed: the speed dial's fixed full scale,
# display only, not a cap (REQUIREMENTS.md M1, M14).
MAX_SPEED_MPS = 70 / KMH_PER_MPS
V_FLOOR_MPS = 1.0               # below which F = P / v is capped
SERVICE_DECEL_MPS2 = 1.2
EBRAKE_DECEL_MPS2 = 2.73
# How far over target the train may drift before the brake helps.
# Kept to about a tenth of a mile an hour, so a slow-down settles on
# its target (35 -> 30 mph ends at 30.08 at the 0.1 s step).
SERVICE_BAND_MPS = 0.05
# Rolling resistance, from truth modules/train-model.md. The bench
# simulation applies it only under a brake failure; the controller
# never models it (REQUIREMENTS.md M19).
ROLLING_RESISTANCE_COEFF = 0.002
GRAVITY_MPS2 = 9.81
ROLLING_DECEL_MPS2 = ROLLING_RESISTANCE_COEFF * GRAVITY_MPS2
# Below this the emergency brake may be released (D011).
STANDSTILL_MPS = 0.1
# Below this, with no power applied, the bench simulation settles to
# an exact stand instead of creeping.
SETTLE_MPS = 0.12

# ---------------------------------------------------- failure detection
# The Train Model no longer reports its failures, so the controller
# infers them. Rules and thresholds are this controller's own design;
# see ControllerCore.detect_failures() and OPEN_ISSUES.md.
ENGINE_DETECT_ACCEL_MPS2 = 0.1
ENGINE_DETECT_S = 2.0
ENGINE_RISE_MPS = 0.05

# ---------------------------------------------------------------- gains
# Pull the full 0.5 m/s^2 from a stand, reach 70 km/h in about three
# quarters of a minute, then hold within a tenth of a mph of target.
DEFAULT_KP = 400_000.0          # W per m/s of error
DEFAULT_KI = 8_000.0            # W per (m/s x s) of accumulated error

# -------------------------------------------------------- announcements
# Sent to the Train Model in both modes (REQUIREMENTS.md M7).
ANNOUNCE_ARRIVING_BLOCKS = 3
ANNOUNCE_ARRIVING = "The train {train_id} is arriving soon"
ANNOUNCE_ARRIVED = "The train {train_id} has arrived at {station}"
ANNOUNCE_DEPARTING = "The train {train_id} is departing from {station}"
# Ticks between a command and the Train Model's report of it. On the
# bench the simulation answers on the next tick. Under the central
# harness each module reads the others' outputs from the tick before
# (truth D017): a command sent on one tick is acted on the next, and
# its report arrives the tick after that.
BENCH_ECHO_TICKS = 1
ECHO_TICKS = 2
# Station dwell, fixed (truth D007): the controller holds it
# (REQUIREMENTS.md M6).
DWELL_S = 45.0

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
