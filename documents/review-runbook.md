# Review runbook

Use the project virtual environment from the repository root. The existing
`track_overflow.py` executable starts the harness and its seven modules. Its two
hardware hosts require the assigned USB Pis unless `--test-pi` explicitly chooses
simulation. These examples use separate simulated Pi processes, the same serial
codec and relay, and actual module implementations. They do not validate USB timing.

```sh
PYTHON=/home/kevin/ECE/Trains/.venv/bin/python
"$PYTHON" track_overflow.py --test-pi process --load-starters \
  --engineer-gains 400000 8000 --dispatch G1:Green:65 --dispatch R1:Red:16
```

The clock starts paused. Press Run in CTC; use its 1x/10x control. Verify Green and
Red `WAYSIDES_READY`, `TRAIN_ADDED` for G1/R1, Green travel 63→64→65 and Red 9→…→16,
and a platform-side door open at each station at rest. Each door must remain open
for 45 simulated seconds. End through the harness and verify seven `MODULE_EXITED`
records with `exit code 0`, then `HARNESS_STOPPED`. No emergency brake, pickup failure,
`TRAIN_LEFT_TRACK`, rejected tick or protocol fault is acceptable.

For a repeatable automatic run through the CTC scheduler:

```sh
"$PYTHON" track_overflow.py --test-pi process --load-starters \
  --engineer-gains 400000 8000 --schedule common/harness/scenarios/station-review.json
```

For unattended evidence add `--headless --speedup --run-seconds 60 --log-dir
/tmp/review-events`. Window demonstrations can add `--auto-run --speedup` to press
Run automatically. The scheduled run proceeds to the yard after its stop; the manual
run waits for a dispatcher destination. The tests observe each station for its entire
dwell and stop the same harness through its normal shutdown API:

```sh
QT_QPA_PLATFORM=offscreen "$PYTHON" -m pytest -q \
  common/harness/tests/test_review_scenarios.py -k 'not multiple'
TRACK_OVERFLOW_MULTI_TRAIN=1 QT_QPA_PLATFORM=offscreen "$PYTHON" -m pytest -q \
  common/harness/tests/test_review_scenarios.py -k multiple
```

The latter checks two and three scheduled trains **on each line**, including actual
concurrent count, authority route exclusivity, block separation and controller failure
latches. It is an acceptance probe: a failure is a review finding, never permission
to alter owner arbitration. The final run retains failures for mixed Red 2/3 concurrency
and Green-only three-train station completion. See the
[dated scenario evidence](review-scenario-evidence-2026-10-22.md) for exact bounds and
results. A bounded waiting train is not proof of a permanent deadlock.

Existing event logging covers line readiness, roster additions/removals, missing-Pi
`PI_SEARCH` with module and USB identity, and protocol faults. The harness window
already lists these events. `measure --system` prints a console hint when physical
Pis are required. Use explicit simulation for a local budget sample:

```sh
"$PYTHON" -m common.harness.measure --system --test-pi process --speed 1 --seconds 15
"$PYTHON" -m common.harness.measure --system --test-pi process --speed 10 --seconds 15
```

Add `--window` for the visible harness; run samples sequentially on an idle machine.

Build and smoke the Linux one-folder executable outside the checkout:

```sh
PYTHON="$PYTHON" bash utils/build_linux.sh /tmp/track-overflow-build
cd /tmp
QT_QPA_PLATFORM=offscreen /tmp/track-overflow-build/dist/track-overflow/track-overflow \
  --headless --speedup --test-pi process --load-starters \
  --engineer-gains 400000 8000 --dispatch G1:Green:65 --dispatch R1:Red:16 \
  --run-seconds 20 --log-dir /tmp/review-frozen-events
```

The build includes all module code, HW UI/data, the shared Pi link, and a generated
Pi source manifest used by HELLO hash verification. It routes simulated agents back
through the same executable. Keep generated outputs outside the repository. Inspect
the log for both lines, both releases, all seven clean exits, and no faults. A Linux
smoke does not establish Windows packaging or physical-Pi timing.

## Recovering a stalled run

Keep the current CSV and the host Pi journal before restarting. Check whether the
shared clock is paused, whether all seven modules are ready, and the first fault
before the last normal tick. `PI_SEARCH` names the missing module and USB identity;
connect that assigned Pi, and check for `PI_HELLO`/recovery diagnostics. A reconnect
holds the run paused: use CTC Run explicitly after the Pi has recovered.

If a line is `WAYSIDES_NOT_READY`, load and commit every required database/PLC for
that line. If a released train waits at the yard exit with no fault, set its engineer
gains in its train controller. If the clock runs but no automatic train is released,
check CTC automatic mode, dispatch pause, schedule departure time and line readiness.
If the train is waiting with zero authority, inspect occupancy and the reported
switch/authority reason; do not bypass the owner rules to force motion. Save the
train ID, block, clock time and relevant CSV/journal records for its module owner.

Kevin's answer for the multi-train Red limitation was: “Note this as an open question
for ctc.” The two/three-train acceptance probes preserve that finding; they do not
change the scheduler's conservative two-way-zone ownership.
