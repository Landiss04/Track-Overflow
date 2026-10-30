# Review runbook

For everyday runs, the event log and troubleshooting, see
[the harness runbook](../common/harness/RUNBOOK.md).

From the repository root, use the project environment. These commands start the
existing harness and seven real modules with two explicit simulated Pi processes;
they verify integration, not physical USB timing.

The functional review runs at **1x**: `--speedup` is deliberately omitted, so the
clock targets one simulated second per wall second. Require no event-log faults,
including `TIME_SLIPPED`, `TRAIN_LEFT_TRACK`, rejected ticks and protocol faults.
The process tests also reject commanded or active emergency braking; pickup and
other controller failures are checked through their failure-braking response.
Process step replies do not expose the internal pickup-failure latch. These
safety and protocol checks remain in force at 1x.

The review host is provisional: for now this review runs on **`kevin-framework`**.
That is a session check, not a policy decision; the 10x/speed trade-off stays open
pending real-Pi measurements (see [Optional 10x performance measurement](#optional-10x-performance-measurement)).

Use a virtual-environment interpreter. A caller-supplied `PYTHON` takes precedence;
otherwise select the project venv at `.venv/bin/python` in the repo root or
`../.venv/bin/python` beside it:

```sh
case ${PYTHON:-} in
  "" )
    if [ -x .venv/bin/python ];      then PYTHON=.venv/bin/python
    elif [ -x ../.venv/bin/python ]; then PYTHON=../.venv/bin/python
    else
      echo 'No project venv found; set PYTHON to your venv interpreter.' >&2
      exit 1
    fi ;;
esac
echo "using $PYTHON"   # on kevin-framework this is the project venv beside the repo

"$PYTHON" track_overflow.py --test-pi process --load-starters \
  --engineer-gains 400000 8000 --dispatch G1:Green:65 --dispatch R1:Red:16
```

Press **Run** in CTC. Confirm Green and Red `WAYSIDES_READY`, then `TRAIN_ADDED`
for G1/R1. Follow Green 63→64→65 (GLENBURY) and Red 9→…→16 (HERRON AVE). Show both
trains stopped, each with its platform-side door open, for **45 simulated seconds**,
which at 1x takes about 45 wall seconds or a little more. The manual run then waits
for another CTC destination. No emergency brake, pickup failure, `TRAIN_LEFT_TRACK`,
rejected tick, `TIME_SLIPPED` or protocol fault is acceptable.

For the automatic scheduler demonstration, end the first run and launch:

```sh
"$PYTHON" track_overflow.py --test-pi process --load-starters \
  --engineer-gains 400000 8000 --schedule common/harness/scenarios/station-review.json
```

Again press CTC Run. Verify the same stops and dwell; the schedule then sends trains
toward their yards. End the interactive run through the harness.

For an unattended start at 1x, use:

```sh
"$PYTHON" track_overflow.py --test-pi process --load-starters \
  --engineer-gains 400000 8000 --schedule common/harness/scenarios/station-review.json \
  --headless --run-seconds 300 --log-dir /tmp/review-events
```

A headless run always presses CTC Run by itself, so no extra `--auto-run` is needed;
there is deliberately no `--speedup`, keeping the run at 1x. The 300-s wall bound
allows startup, outbound travel and each 45-s station dwell, followed by scheduled
return travel. It does not guarantee yard retirement. The harness stops automatically
at the bound. Verify **seven `MODULE_EXITED` records with `exit code 0`**, followed
by `HARNESS_STOPPED` in its CSV, and confirm no event-log faults.

## Optional 10x performance measurement

Measure 10x separately from the functional review on the provisional host. Any
optimization or speed trade-off waits for real-Pi measurements; the functional
review remains at 1x.

Use the existing `common.harness.measure` runner with `--system --test-pi process`,
rather than adding another transport or harness:

```sh
"$PYTHON" -m common.harness.measure --system --test-pi process \
  --speed 10 --seconds 10
```

`--speed 10` is the measure tool's default; state it explicitly so the record is
unambiguous. Read the report as distinct quantities — do not collapse them:

- **completed / due ticks** (`ticks: N of M due`) — how well the run kept up with the
  clock, at the chosen speed and payload.
- **dropped backlog** (`ticks slipped:`) — ticks abandoned past the catch-up band,
  reported as `TIME_SLIPPED`; zero late replies alone does not establish that the
  run kept up.
- **late replies** (`late replies:`) — replies exceeding the configured timeout,
  separate from the clock's tick budget.

Record the host (expected to be `kevin-framework`), revision, speed, payload and all
three numbers. These simulated-Pi measurements describe this host and workload;
they do not establish physical USB readiness or replace real-Pi measurements. See
[harness measurement recipes](../common/harness/README.md) for the broader budget
tables and limitations.

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

[Current Phase 7 source verification](integration-handover.md#phase-7-handover) records the
current commands, results and limitations. The
[2026-10-22 evidence](review-scenario-evidence-2026-10-22.md) is historical Phase 6
verification and Linux build/smoke evidence. Build with `PYTHON="$PYTHON" bash
utils/build_linux.sh /tmp/track-overflow-build`. [Pi setup and measurements](pi-owner-setup.md)
cover physical hardware. [Harness measurement recipes](../common/harness/README.md)
use explicit `--system --test-pi process` for local simulation.

The open owner requests — including the retained opt-in failures for simultaneous Red
2/3 trains and Green three-train station completion (kept as “an open question for
ctc”) and Braden's required review of the neighbor closures — live in one place: the
shared [module owner review](module-owner-review.md). A bounded stall does not prove
a permanent deadlock.
