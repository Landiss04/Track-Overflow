# Train Model open issues

The Train Model simulates physics. Control logic belongs to the Train
Controller, as clarified by Kevin Schillinger on 2026-09-30.

## Configured speed is not enforced here

`TrainConfig.v_max_mps` records 70 km/h (19.444... m/s), but does not limit
the simulated velocity. Commanded speed and track speed limits are passed
to the Train Controller; they do not govern motion in this module.
Sustained power can therefore accelerate the model beyond the configured
speed. Speed regulation and enforcement belong to the Train Controller.
Verify that behavior during controller integration rather than adding a
velocity clamp to the physics.

## Vehicle calibration

The force and resistance parameters still need calibration against the
Blackpool FLEXITY 2 datasheet. Its 0.5 m/s² figure is an average acceleration
from 0 to 70 km/h at two-thirds load; using it to derive a maximum traction
force does not establish that the simulated acceleration curve matches the
vehicle. Rolling resistance is assumed, aerodynamic drag is absent, and
reference mass excludes crew while operating mass includes crew. Validate
acceleration, braking and grade performance across loads before treating
the model as a calibrated representation of the vehicle.

## Displayed power consumption

The overview's "power consumption" is the commanded power capped to the
configured maximum (and displayed as zero on engine failure). It is not a
measurement of mechanical or electrical consumption. In particular,
traction-limited operation need not use all commanded power. Actual power
accounting, losses and regeneration are not modeled. Decide whether to
relabel this readout as commanded power or supply a separately defined
physical power measurement.
