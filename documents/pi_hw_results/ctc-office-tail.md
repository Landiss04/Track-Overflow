# The CTC Office tail under the stress schedule

**Status:** a measurement with suggestions, not a change. Nothing in `CTC-Office/` is modified on branch `10x-pi-speed`. The truth index lists the CTC Office owner as unassigned, so this needs someone to take it.

## What we saw

With `utils/schedule_stress.json` at 10x (14 Green trains and 4 Red trains), the CTC Office's reply to a STEP is 4.5 ms at the median but p95 14-26 ms and p99 25-48 ms on the Windows host, with hundreds of stalls of 50-190 ms in a 600 s run (291 in the Train-Pi run). It is the slowest module in 5-7% of ticks and, in 6-12% of ticks, the reason a tick goes over its 10 ms slot while the Track Controller is not. This is independent of the Pis: the same shape (reply p99 about 40 ms) appears in a sandbox with both Pis simulated.

## Where the time goes (sandbox, `py-spy` on the CTC Office process, 200 samples a second, idle included, 44 s, stress schedule, both Pis simulated)

The process is busy 54% of the time. Share of its busy time:

| What | Share |
| --- | --- |
| `StubCtcOffice.step` | 65% |
| its authority computation (`_retire` -> `_authorities` -> `_compute_authorities`) | 50-55% |
| route search inside it (`TrackGraph.route`, `turns_back`, `neighbors`, `can_run`; `_choose_route` calls it) | 40% |
| window refresh (`CtcHost._refresh`, about 27 ms each time, five times a second) | 25% (14% of the process's wall time) |

Uninterrupted busy stretches: 1,540 in 44 s, median 10 ms, p90 35, p99 70, max 125 ms; 170 longer than 30 ms and 67 longer than 50 ms. Of the 170, **95 were the window refresh and 75 were the step** (the route computation; the longest, 90-125 ms). A busy stretch longer than the 10 ms tick spacing delays the next STEP's reply, which is the clusters of spikes in the hardware runs (for example around t = 123-136 s in the 600 s Train-Pi run).

Inside `_refresh`, 93% of the time is the two signal emissions (`clockChanged` 53%, `stateChanged` 40%): the slots they run read the host's properties (`throughput`, `trains`, `blockStates`, ...), each of which calls `module.snapshot()`. `snapshot()` is called about twice per tick (6,204 times in 30 s) at 0.21 ms, 1.3 s in all, so caching it alone would save under 10% of the busy time.

## Experiments (sandbox, stress schedule, 40 s, both Pis simulated, runs alternated as-is against the change)

| | As-is | One signal per event-loop turn | Window refresh off (upper bound) |
| --- | --- | --- | --- |
| CTC reply p95 / p99 / max (ms) | 11.3, 10.6 / 42.3, 38.5 / 89, 72 | 19.8, 18.4 / 29.5, 24.5 / 62, 40 | 8.2-8.5 / 11.2 / 17-20 |
| System round trip p95 / p99 (ms) | 24.4, 22.4 / 44.3, 39.1 | 22.2, 20.4 / 32.6, 28.0 | 13.7-15.1 / 26.0-27.7 |
| System round trip mean (ms) | 9.04, 8.18 | 8.97, 8.30 | 7.75-8.23 |
| Speed | 9.73x, 10.00x | 9.85x, 9.99x | 10.00x, 10.00x |

Turning the refresh off removes the CTC tail (p99 11 ms) and about half the system's tail; the system then reaches 10.00x in the sandbox. Emitting one signal per event-loop turn halves the worst stalls but moves work into more ticks (CTC p95 roughly doubles). The Track Controller's reply is unchanged by either.

## Suggestions for the owner (none applied)

1. Make the refresh cheaper: the expensive part is the slots behind `stateChanged` and `clockChanged`, not the snapshot or the comparison. Look at `throughput` and the models rebuilt on every change; update what changed.
2. Refresh less when nobody is looking, or slower at 10x (`WINDOW_REFRESH_MS` is 200).
3. Cache the route search by train block and destination until the graph or occupancy changes, or compute authorities only for trains that moved. It is 40% of the busy time and the source of the step stalls of 90-125 ms.
4. If the refresh must stay as it is, split it across event-loop turns (partial, as above).

## Caveats

Sandbox, Qt offscreen, so the refresh here is model work only; on the Windows host the CTC window may paint as well. Windows host numbers (CTC p99 25-48 ms) are consistent with the sandbox's (about 40 ms). One profile of one run; the A/B has two runs per row and the means differ run to run by about 0.4 ms.

## Experiment applied: redraw every 1000 ms at 10x (commit `d660690`)

`CTC-Office/ctc/module_process.py`: new constant `WINDOW_REFRESH_MS_AT_SPEEDUP = 1000`, used instead of `WINDOW_REFRESH_MS` (200) while the clock is at 10x. One commit, one test; `git revert d660690` removes it, or set the constant to 200 to turn it off.

Sandbox, stress schedule, 40 s, both Pis simulated, alternated, two runs each:

| | As-is | 1000 ms at 10x |
| --- | --- | --- |
| Speed | 9.78x, 9.86x | 10.00x, 10.00x |
| System round trip p95 / p99 (ms) | 25.3, 23.1 / 42.6, 40.8 | 14.3, 15.4 / 32.4, 32.0 |
| CTC reply p95 / p99 (ms) | 11.1, 11.1 / 40.8, 39.4 | 7.8, 8.5 / 13.1, 16.5 |

The CTC tail goes away (p99 about 40 to 13-16 ms); the Track Controller's tail (p99 about 25) is now what is left. The window shows 1 s old data at 10x, which is a UI decision for the CTC Office owner. Not yet measured on the Windows host or with a Pi.
