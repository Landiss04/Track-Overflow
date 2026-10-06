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
velocity clamp to the physics. The course instructor confirmed on 2026-10-02
that the Train Model does not enforce the maximum speed.

## Vehicle calibration

The force and resistance parameters still need calibration against the
Blackpool FLEXITY 2 datasheet. Its 0.5 m/s² figure is an average acceleration
from 0 to 70 km/h at two-thirds load; using it to derive a maximum traction
force does not establish that the simulated acceleration curve matches the
vehicle. All three forces derive from a 51,433 kg reference mass, 2/3 of the
datasheet load between 40.9 t empty and 56.7 t loaded: 25,717 N traction,
61,720 N service and 140,413 N emergency, matching the instructor's values. Rolling resistance is assumed, aerodynamic drag is absent, and
reference mass excludes crew while operating mass includes crew. Validate
acceleration, braking and grade performance across loads before treating
the model as a calibrated representation of the vehicle.

## Door interlock ownership

The door interlock (a door opens only at 0 mph and closes once the train
moves) is commented out of `train_model/model.py`, not deleted. Whether the
Train Model enforces it is with the course instructor; Kevin believes it does
not (2026-10-06). Until that is answered the doors follow Door Command at any
speed and nothing in the Train Model keeps a door shut while moving: a known
gap. Passengers still board only at rest, and the disembark draw happens on
the first tick at rest with a door open. The interlock's tests are skipped,
not deleted (`INTERLOCK_OFF` in `tests/test_physics_extended.py`). If the
instructor puts the interlock back in the Train Model, uncomment it and drop
the skips; otherwise it belongs with the Train Controller.

## Train ID, line and arrival time have no source

The Train Model window's header and Position card show a dash for the train
ID, the line and the next arrival time. No defined interface supplies them:
the Train Model's inputs (`train_model/interface.py`) carry none of them, and
no `truth/signals/` entry names a producer. Decide which module sends each one
(the CTC Office dispatches trains and knows their IDs, lines and schedules)
and add it to the interface before the window can show them.
