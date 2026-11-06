# Review scenario evidence — 2026-10-22

This records implementation checks and limitations, not normative facts. The system
was checked on kevin-framework, Linux, with project Python 3.14.4, PySide6 6.11.2,
and PyInstaller 6.22.2, meeting the truth toolchain minima.

The review uses the existing central harness, module specifications, prior-tick edges,
CTC dispatch/schedule options and simulated Pi transport. No second product launcher
was added. CLI passthrough now exposes the CTC's existing `--schedule` and both train
controllers' existing `--engineer-gains`. Kevin explicitly approved those two CLI
changes; no widget or window behavior was changed. `measure --system` without
`--test-pi` prints one console hint and still waits for physical Pis.

Readiness already logs `WAYSIDES_READY`/`WAYSIDES_NOT_READY` with the line;
`Roster.apply` already logs `TRAIN_ADDED` and `TRAIN_REMOVED` exactly when CTC events
are applied. PI diagnostics and protocol faults already enter the same event stream.
Those hooks were reused without duplicate events or a new UI.

## Final verification

The orchestrator reran the final post-closure implementation with these commands
from the repository root (project Python, offscreen Qt):

```sh
PYTHON=/home/kevin/ECE/Trains/.venv/bin/python
TRACK_OVERFLOW_ROUND_TRIP=1 TRACK_OVERFLOW_MULTI_TRAIN=1 QT_QPA_PLATFORM=offscreen \
  "$PYTHON" -m pytest -q common/harness/tests
QT_QPA_PLATFORM=offscreen "$PYTHON" -m pytest -q TrackCtrlHw/tests
QT_QPA_PLATFORM=offscreen "$PYTHON" -m pytest -q common/hw_link/tests
```

| Final scope | Result |
| --- | --- |
| Harness, including both opt-in families | 185 passed, 3 failed, 497 subtests; 296.77 s |
| Track Controller HW | 89 passed, 50,538 subtests; 33.35 s |
| Shared Pi link | 44 passed; 8.15 s |

The three harness failures are the mixed two-train and three-train acceptance probes
and Green-only three-train station completion described below. Green-only two-train
acceptance, the five Green round-trip tests, manual/scheduled process station review
and CLI mapping all passed in that run. These overlapping targeted results must not
be added again to the final harness total.

## Bounded tests

| Check | Observed result |
| --- | --- |
| Manual and scheduled station review, seven real processes and two simulated Pi processes; plus CLI mapping regression | 3 passed in 24.13 s |
| Existing `AutoRunTest` | 5 passed, 2 subtests |
| Script syntax, Python compilation, scoped flake8 (`--jobs 1`), `git diff --check` | passed |
| Two scheduled trains per line, seven real cores, 900 simulated seconds | failed acceptance: max simultaneous Green 2, Red 1; Green 1/2 and Red 1 completed station dwell |
| Three scheduled trains per line, seven real cores, 900 simulated seconds | failed acceptance: max simultaneous Green 3, Red 1; Green 1/2 and Red 1/2 completed station dwell; Green 3 and Red 3 did not complete it before the bound |

The two/three-train tests are explicit opt-in acceptance probes, preserved as failures.
Their schedules release every 180 simulated seconds under the real CTC automatic
scheduler. Every simulated tick checks occupied-block separation, the exclusive union
of each CTC authority's reserved route including the current block, controller emergency
brake and pickup-failure latches, and continuous 45-second station dwell. No earlier
assertion for unsafe overlap, pickup failure or emergency brake failed in those bounded
runs. This is not a claim that the missing endpoints passed.

The dispatcher plans for Red stations 16, 21, 25, 35, 45, 48 and 60 were independently inspected.
For every one, `AutoDispatcher.zones['Red']` includes all blocks 9…66 in one two-way zone.
The route out and back repeats the shared track; the zone rule holds later Red runs until
the current run clears. Changing the destination among those stations does not create
simultaneous Red trains under that rule. No owner arbitration or switching rule was
changed to make the probe pass. The required simultaneous Red 2/3 demonstration remains
an explicit unresolved acceptance item.

Independent Green-only automatic schedules separately established two active trains
and both completed dwells. The initial three-train run reached three active trains
but stopped at its 1,200 simulated-second bound with G1 at 133 returning to the yard,
G2 at 65 after its dwell and G3 waiting at 64. A longer 2,400 simulated-second run
failed in 53.39 s: G1 had retired, but G2 remained at 65 and G3 at 64. No earlier
safety/failure assertion failed. Green three-train station completion is therefore
also an unresolved CTC integration finding; maximum active count alone does not prove
that all three complete their stops. This bounded stall does not establish a permanent
deadlock. The existing endpoint evidence does not record the exact scheduler progress
or authority hold reason at that bound.

Kevin asked that the simultaneous Red question be recorded for the CTC owner on
2026-10-22. The conservative owner logic is retained; this is an open question for
CTC, not a silently weakened test.

## Packaging

`utils/build_linux.sh` builds a one-folder Linux executable outside the checkout.
The latest build completed in about 15 seconds and occupies 494 MiB. It includes HW
UI/data, `common.hw_link`, and the generated manifest used by source/Pi/frozen HELLO
hash validation. The executable's internal `--pi-agent` route reuses the same agent
entry point for explicitly simulated Pis. Build artifacts and logs remain in `/tmp`.

The orchestrator ran the final post-closure binary from `/tmp` for 20 real seconds,
with `QT_QPA_PLATFORM=offscreen`, both explicit process Pis, starter PLCs, gains,
manual G1/R1 dispatches and 10x. The command is the runbook smoke command, using
`--log-dir /tmp/phase6-frozen-events`. It exited 0 after 1,895 ticks. Both lines logged
ready, both trains were added, all seven module processes exited with code 0, and no
fault was recorded. Both Pi HELLO replies carried the same verified manifest hash,
`31fee16e8225461b3cab92baaf77bb059ad766cd7290ac88de97b077441893c0`.
The retained evidence is `/tmp/phase6-frozen-smoke.log` and
`/tmp/phase6-frozen-events/events-20261022-111909.csv`.

The visible measurement runs launched on the real Wayland display at 1x and 10x.
That confirms successful launch and measured execution; no screenshot or visual
inspection of all seven windows was performed. Neither the simulated-Pi smoke nor
these display runs establish physical USB readiness or Windows delivery.
