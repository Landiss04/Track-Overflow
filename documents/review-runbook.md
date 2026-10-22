# Review runbook

From the repository root, use the project environment. These commands start the
existing harness and seven real modules with two explicit simulated Pi processes;
they verify integration, not physical USB timing.

```sh
PYTHON=/home/kevin/ECE/Trains/.venv/bin/python
"$PYTHON" track_overflow.py --test-pi process --load-starters \
  --engineer-gains 400000 8000 --dispatch G1:Green:65 --dispatch R1:Red:16
```

Press **Run** in CTC; demonstrate its **1x/10x** control. Confirm Green and Red
`WAYSIDES_READY`, then `TRAIN_ADDED` for G1/R1. Follow Green 63→64→65 (GLENBURY)
and Red 9→…→16 (HERRON AVE). Show both trains stopped, each with its platform-side
door open, for **45 simulated seconds**. The manual run then waits for another
CTC destination. No emergency brake, pickup failure, `TRAIN_LEFT_TRACK`, rejected
tick or protocol fault is acceptable.

For the automatic scheduler demonstration, end the first run and launch:

```sh
"$PYTHON" track_overflow.py --test-pi process --load-starters \
  --engineer-gains 400000 8000 --schedule common/harness/scenarios/station-review.json
```

Again press CTC Run. Verify the same stops and dwell; the schedule then sends trains
toward their yards. Add `--auto-run --speedup` for automatic start, or
`--headless --speedup --run-seconds 60 --log-dir /tmp/review-events` for unattended
logging. End through the harness; verify **seven `MODULE_EXITED` records with
`exit code 0`**, followed by `HARNESS_STOPPED` in its CSV.

## If the run stalls

Preserve the CSV and host Pi journals. Check shared-clock pause, seven-module
readiness, and the first fault before the last normal tick. `PI_SEARCH` names the
missing module and USB identity: connect its assigned Pi, check HELLO/recovery,
then explicitly press CTC Run; reconnection leaves the run paused.

For `WAYSIDES_NOT_READY`, load and commit the line’s databases/PLCs. A released train
waiting at the yard exit may need engineer gains. With no automatic release, check
CTC automatic mode, dispatch pause, departure time and line readiness. With zero
authority, inspect occupancy and the switch/authority reason; preserve train ID,
block, clock time and log records for the owner. Do not bypass owner rules.

## Evidence and remaining questions

[Detailed verification and Linux build/smoke evidence](review-scenario-evidence-2026-10-22.md)
records commands, counts and limitations; build with `PYTHON="$PYTHON" bash
utils/build_linux.sh /tmp/track-overflow-build`. [Pi setup and measurements](pi-owner-setup.md)
cover physical hardware. [Harness measurement recipes](../common/harness/README.md)
use explicit `--system --test-pi process` for local simulation.

The opt-in acceptance probes retain failures for simultaneous Red 2/3 trains and
Green three-train station completion. Kevin said: “Note this as an open question
for ctc.” A bounded stall does not prove a permanent deadlock.
