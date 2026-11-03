# Harness runbook

How to start, operate, stop and check the central harness, and what to do when a run
goes wrong. For how the harness works, see [the README](README.md); for the scripted
two-line review, see [the review runbook](../../documents/review-runbook.md).

Run every command from the repository root.

## 1. Before a run

1. Use the project virtual environment, never the system Python. PySide6 is installed
   only there (`truth/conventions/toolchain.md`). Pick the interpreter once per shell:

   ```sh
   if [ -x .venv/bin/python ]; then PYTHON=.venv/bin/python
   elif [ -x ../.venv/bin/python ]; then PYTHON=../.venv/bin/python
   else echo 'No project venv; set PYTHON to your venv interpreter.' >&2; fi
   ```

2. Check the toolchain minimums: Python 3.10 and PySide6 6.11.

   ```sh
   "$PYTHON" -c "import sys, PySide6; print(sys.version.split()[0], PySide6.__version__)"
   ```

3. Decide which Pis the run uses (section 2). Unless told otherwise, the harness waits
   for both physical USB Pis, with no fallback.

4. On a machine with no display (SSH, CI), add `QT_QPA_PLATFORM=offscreen` in front of
   every command below.

## 2. Pick a launch mode

| Purpose | Command |
| --- | --- |
| Production: both physical Pis, people do every step in the windows | `"$PYTHON" track_overflow.py` |
| Development: both Pis simulated, programs, gains and trains supplied | `"$PYTHON" track_overflow.py --test-pi process --load-starters --engineer-gains 400000 8000 --dispatch G1:Green:65 --dispatch R1:Red:16` |
| Scheduled run, automatic mode | `"$PYTHON" track_overflow.py --test-pi process --load-starters --engineer-gains 400000 8000 --schedule common/harness/scenarios/station-review.json` |
| One Pi simulated, the other physical | `"$PYTHON" track_overflow.py --track-controller-pi process --train-controller-pi physical --load-starters` (swap the two for the other way round) |
| Pi choice from a file | `"$PYTHON" track_overflow.py --pi-config config/pi-testing.json --load-starters` |
| Harness check with no real modules | `"$PYTHON" track_overflow.py --stubs-only` |

Add any of these to a mode:

| Option | Effect |
| --- | --- |
| `--headless` | No operator window. Every event goes to the console, with a status line every 5 s, and the CTC Office presses Run by itself |
| `--auto-run` | In a window run, the CTC Office presses Run once ready. For tests and demonstrations only |
| `--run-seconds N` | Stop by itself after N real seconds |
| `--speedup` | Start at 10x. Functional reviews run at 1x, so leave it off for them |
| `--log-dir DIR` | Write the event log to `DIR` |
| `--test-pi pty` | Simulated Pis over Linux pseudo-terminals instead of processes |

Pi selection, from lowest precedence to highest: physical by default, then
`--pi-config`, then `--test-pi`, then `--track-controller-pi` / `--train-controller-pi`.
`--test-pi` is a development choice, never a stand-in for a missing Pi in a review.

## 3. Operate a run

A run needs three roles. In a development run, the options in brackets play them.

1. **Start.** The harness starts seven module processes, prints the event log's path, and
   logs `MODULE_STARTED` then `MODULE_READY` for each, then `ALL_READY`. The clock starts
   paused.
2. **Load the PLC programs** (`--load-starters`). In each Track Controller window, RUN
   then COMMIT on every wayside, or press **Load starters**. Until every wayside on a line
   is ready, the log shows `WAYSIDES_NOT_READY` and the CTC Office refuses dispatches on
   that line. Expect `WAYSIDES_READY` for Green (`track-controller-sw`) and Red
   (`track-controller-hw`).
3. **Press Run** in the CTC Office window (`--auto-run`, or any headless run). The log
   shows `CLOCK_RESUMED`. Pause and 1x/10x are also in the CTC Office window.
4. **Dispatch** a train in the CTC Office window (`--dispatch TRAIN:LINE:BLOCK`, or
   `--schedule`). The log shows `TRAIN_ADDED`, and the train appears on the yard exit
   block: Green 63, or Red 9.
5. **Set the gains** in the Train Controller's console (`--engineer-gains KP KI`). A
   released train waits at the yard exit until it has gains.

Closing a module window only hides it. Only the harness ends a module.

## 4. Stop a run

- Press Ctrl+C in the terminal, close the operator window and confirm, or let
  `--run-seconds` expire.
- A clean stop logs `MODULE_EXITED: exit code 0` for all seven modules, then
  `HARNESS_STOPPED` listing seven zero exit codes.
- A module that does not quit within 5 s is killed and logged as `MODULE_KILLED`. Treat
  that as a fault to report.

## 5. Read the event log

One CSV per run, with the columns `wall_time, sim_time_s, time_of_day, tick, source,
event, detail`. The harness prints its path at start. By default it is in
`~/.local/share/TrackOverflow/logs` (Linux) or `%LOCALAPPDATA%\TrackOverflow\logs`
(Windows). No run overwrites another's log.

Count the events in a run:

```sh
cut -d, -f5,6 path/to/events-*.csv | sort | uniq -c | sort -rn
```

A healthy run has none of these:

| Event | Meaning |
| --- | --- |
| `TIME_SLIPPED` | The clock fell behind and dropped ticks |
| `REPLY_LATE` | A module took over 1 s to reply; the clock paused and names it |
| `TICK_REJECTED`, `INPUTS_FAILED` | A module refused a tick, or its inputs could not be built |
| `PROTOCOL_ERROR`, `UNEXPECTED_REPLY` | A link fault |
| `EDGES_FAILED` | A mapping between modules raised |
| `TRAIN_LEFT_TRACK` | A train ran off the layout |
| `MODULE_DISCONNECTED`, a non-zero `MODULE_EXITED`, `MODULE_KILLED` | A module died. It is never restarted mid-run, so the clock stays held |
| `STARTUP_TIMEOUT` | A module was not ready within 20 s |
| `PI_LOST`, `PI_HELLO_REJECTED`, `PI_RECOVERY_REJECTED` | A HW module's Pi link failed |

A commanded or active emergency brake is also a failure in a review run.

## 6. When a run goes wrong

First, keep the event log and, for a physical Pi, the Pi's journal. Find the first
fault before the last normal tick, not the last one.

| Symptom | Check |
| --- | --- |
| Nothing moves, the clock reads paused | Was Run pressed? Are all seven modules `MODULE_READY`? Is any module named by `REPLY_LATE` or down? |
| `PI_SEARCH` repeats | It names the module and the USB identity it wants. Connect that Pi, check `PI_HELLO`, then press Run again: a reconnection leaves the run paused |
| `WAYSIDES_NOT_READY` | Load and commit a program on every wayside of the named line |
| A train waits at the yard exit | Set its engineer gains |
| No train released in automatic mode | Check the CTC's automatic mode, dispatch pause, the departure time, and line readiness |
| A train stops with zero authority | Look at the occupancy and the CTC's authority reason for that train (occupied, reserved, switch, closed). Record the train ID, block, clock time and log rows for the module owner. Do not change owner rules to get past it |
| Startup fails or times out | Run `--stubs-only`. If that is clean, the fault is in a real module; read the console for its traceback |

A bounded stall does not prove a permanent deadlock. Open owner questions are in
[the module owner review](../../documents/module-owner-review.md).

## 7. Smoke test after a change

A quick headless check with all seven modules and simulated Pis. It takes about 40 s:

```sh
QT_QPA_PLATFORM=offscreen "$PYTHON" track_overflow.py --test-pi process --load-starters \
  --engineer-gains 400000 8000 --dispatch G1:Green:65 --dispatch R1:Red:16 \
  --headless --run-seconds 40 --log-dir /tmp/harness-smoke
```

Pass: `WAYSIDES_READY` for Green and Red, `TRAIN_ADDED` for G1 and R1, none of the events
in section 5, and seven zero exit codes in `HARNESS_STOPPED`.

## 8. Test suites

```sh
QT_QPA_PLATFORM=offscreen "$PYTHON" -m pytest -q -p no:cacheprovider common utils
```

This takes about 6 minutes. Some tests are opt-in, because they are slow or record open
owner questions rather than pass/fail behaviour:

| Variable | Runs |
| --- | --- |
| `TRACK_OVERFLOW_ROUND_TRIP=1` | `ReturnToYardTest`: a scheduled Green run round the line to the yard |
| `TRACK_OVERFLOW_MULTI_TRAIN=1` | The multi-train scheduled review scenarios; some still fail, recorded as open owner questions |
| `TRACK_OVERFLOW_GREEN_OWNER_DIAGNOSTICS=1` | The Green CTC-2 hold-and-grant observation |

Each module has its own suite under its folder. A change that crosses a module boundary
should also pass that module's suite, for example
`(cd CTC-Office && "$PYTHON" -m pytest -q tests)`.

To time the clock instead of checking behaviour, use
`"$PYTHON" -m common.harness.measure --system --test-pi process --speed 10 --seconds 10`,
and read it as the review runbook describes.
