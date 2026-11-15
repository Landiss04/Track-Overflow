# Commits on `10x-pi-speed` that change code outside the Pi-link and harness tooling

**Status:** a list for review, not a decision. None of these has been reviewed by the module's owner. The truth index lists no owner for some of these modules, so "owner" below means whoever is assigned to the module. Commit hashes are from this branch; each commit is self-contained and can be reverted alone (`git revert <hash>`), except where the note says otherwise. Older commits cannot be re-labelled without rewriting history, so this file is the mark; newer ones also carry a `Needs-review:` trailer in the commit message.

## Behaviour changes in another module's own code (review before merging to `development`)

| Commit | Module | Files | What changed | Measured effect | Undo |
| --- | --- | --- | --- | --- | --- |
| `1861469` | TrackCtrlHw (vital PLC logic) | `TrackCtrlHw/track_ctrl_hw/plc.py`, `TrackCtrlHw/tests/test_plc.py` | Channel A's trees are run as one generated Python expression per statement (`_flat_walker`, falls back to `_walker`) instead of nested functions. Channels A and B are meant to be diverse; the owner decides whether this keeps them diverse enough, and whether `eval` is allowed in vital code. Proposal text and the evidence: `plc-channel-a-flat-proposal.md`. | See `10x-log.md` once measured on the Pi. | revert the commit |
| `b066cde` | CTC Office | `CTC-Office/ctc/module_process.py`, `CTC-Office/tests/test_module_process.py` | While the clock is at 10x the window redraws every 1000 ms instead of 200 ms (`WINDOW_REFRESH_MS_AT_SPEEDUP`). The window then shows data up to 1 s old at 10x: a UI decision. | all-simulated: CTC p99 about 40 to 9-17 ms, 9.8x to 10.00x; Track Pi physical: speed unchanged (8.45x), tail smaller | revert, or set the constant to 200 |
| `7474cc4` | Train Model | `TrainModel/train_model/module_process.py`, `TrainModel/tests/test_view_interval.py` | Redraws 4 a second instead of 20 when the harness found software rendering (`TRACK_OVERFLOW_LOW_FRAME_RATE`). | See `10x-log.md` | revert the commit |

## Shared code used by every module, or by the harness (review by the harness / link owner)

| Commit | Files | What changed |
| --- | --- | --- |
| `3929c46` | `track_overflow.py`, `utils/process_cores.py`, `utils/tests/test_process_cores.py` | Pins the harness off the last cores and each Pi link process onto them; `TRACK_OVERFLOW_NO_PIN=1` turns it off; nothing is pinned with fewer than four cores. Changes how the launcher starts every process. |
| `bf21405` | `common/harness/app.py`, `utils/render_check.py`, tests | Warns at startup when Qt Quick renders in software; sets `TRACK_OVERFLOW_LOW_FRAME_RATE` for the modules it starts. |
| `2604414` | `common/hw_link/cores.py` (Track core) | The checkpoint leaves out the compiled PLC programs and rebuilds them on restore (vital state handling). |
| `d7ba26e` | `common/hw_link/cores.py` (Train core) | `TrainCore.step` rolls back the roster instead of deep-copying the fleet; adds a regression test for the all-or-nothing STEP. |

## Pi-link tooling (this branch's own work; listed so the scope is clear)

`common/hw_link/` (agent, bringup, provision, tests), `common/harness/measure.py` and its tests, `bench/`, `bench/pi_hw_results/`. The agent's wire protocol is unchanged (agent hash 0a7cf856 until `1861469`, 8d1c457a from it on: the hash covers the core code, so the Track Pi bundle must be reinstalled).

## Not done

Nothing is proposed to the `truth` branch, and nothing was pushed or merged into the user's repository beyond fast-forward merges the user made from the bundles.
