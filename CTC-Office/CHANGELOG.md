# CTC Office — changes for review

Changes to the owner's module code during integration, for review.

---

## 2026-11-11 — The yard as a destination in Manual mode

From Landis.

- **Yard in the destination lists.** The Dispatch train panel's
  Destination station list and the Selected train panel's New
  destination list now start with "Yard · return and retire". Picking
  it sends the train back to the yard through
  `CtcHost.returnToYard()` (R66, D022), as the Return to yard button
  does; the Dispatch train button reads "Return to yard" then. Only a
  train on the track can be sent back, so the button stays disabled
  for one still waiting in the yard, and the Dispatch panel says why.
  The arrival time is ignored for the yard, and there is no speed or
  authority preview, since the yard is not a block.

---

## 2026-11-10 — Selected train: an arrival estimate; occupancy list scrolls

From Landis.

- **Arrival estimate.** The Selected train panel's arrival was the
  time the schedule (or the dispatcher) asked for, which a late train
  showed long after it had passed. It is now an estimate from where the
  train is: the time now plus the run over the rest of its route at the
  suggested speed (`CtcHost.arrivalEstimate()`, for the selected train
  only, re-read each simulated second through `clockSecond`). The time
  asked for moves to a "Due" row, and Deviation shows the minutes
  between the two. The Train occupancy table's Arrive column is still
  the time asked for.
- **Train occupancy window.** `OccupancyWindow.qml`: the train list
  scrolls, so with every train out the footer and its Select train
  button stay in view.
- Tests: `test_ctc_host.py` (the estimate runs from now, moves on while
  the train waits, reads "Arrived" at the destination).

## 2026-11-10 — Fixes from the Schedule v4 integration findings

From the findings of the 2026-11-09 full-system run (C1, C2, C6, C7).

- **C1, a train that overruns past a switch is followed.**
  `ctc/model.py` `_straight_on()`: the block a train runs on into is the
  one the track leads it into. A block that joins its head block at the
  end it came in by (a switch's other connection) is left out, and where
  it faces the points, the switch's reported position decides. Before,
  any block with more than one other neighbour gave no answer and the
  train was lost (R3, in by 15 to 16 and on into 17).
- **C2, authority never ends on a block that locks the switch it waits
  for.** `ctc/routing.py` `authority()`: when the count stops for a
  switch not set for the route, it ends short of the block the switch
  is listed on and of its points block (new
  `TrackGraph.locking_blocks()`), a block further back than before. A
  train standing on either locks the switch, so it could never be set
  for it (G5 on Green 76, R1 on Red 16). `ctc/model.py`
  `_route_requests()` still requests that switch.
- **C6, runs held in the yard leave the schedule's headway apart.**
  `ctc/model.py` `_release()`, new `_too_soon_after()`: a run of the
  schedule leaves no closer behind the last run released on its line
  than their departure times are apart in the schedule. Manual trains
  are not affected.
- **C7.** `tests/test_sim_clock.py` `test_ten_x_runs_faster` only tells
  10x from 1x (5 to 13 simulated seconds in about one real second).
- Tests: `test_ctc_authority.py` (the locking blocks, the request for a
  switch stopped short of; three expectations moved a block back),
  `test_ctc_tracking.py` `OverrunAtASwitchTest`,
  `test_ctc_train_events.py` (headway after a hold).

## 2026-11-04 — An automatic Run waits for the windows

`0345b24` (Kevin, part of the 10x headroom work). A test and
demonstration option only.

- `ctc/module_process.py`: `--run-delay-s` (default 0). With
  `--run-on-ready`, Run is pressed that many seconds after the process
  is ready, not at once (`run_delay_ms`, a single-shot timer), so the
  windows' start-up load is past before the clock runs. The harness
  passes 3 s whenever it presses Run itself (`AUTO_RUN_DELAY_S` in
  `common/harness/app.py`).

## 2026-11-04 — Route requests follow dispatch priority

Checked against Braden's Track Controller HW plan for route requests.

- `ctc/model.py` `_route_requests()`: where two trains want the same
  switch, the most urgent train's request now stands (`_priority`, as for
  contested blocks). Before, it said so but took the lower train ID.
- `tests/test_ctc_authority.py` `RouteRequestTest`: the switch an
  authority stops short of is requested; the urgent train has it.
- Truth proposal `20261104-1038-switch-route-request.md`.

## 2026-11-03 — Runs stop at their stations in the file's order

From Landis: a run stops at the stations its schedule lists, in that
order, whatever is efficient. Green 1's first stop is Pioneer, with no
stop before it.

- `ctc/scheduler.py` `plan_run()`: stations in the file's order, not
  track order from the yard. A station the track reaches only after a
  lap (Green Edgebrook after Pioneer) costs that lap.
- Two-way zones, so the longer runs do not jam: a run leaves the yard
  only when the first zone on its way is free for it; elsewhere it waits
  on one-way track a block short of a zone in use the other way; it
  claims only the next zone ahead; no more trains go toward a loop than
  it holds (Green 1 to 12 jammed with all ten runs in it); a pass counts
  as coming back only right after the same zone. A train is shown held
  only while it waits.
- `route_requests` (each switch's position for the train routed over it)
  and `PASSING_SIDINGS` (off) are in, for the Track Controller to use.
- In the scheduler's own simulated railway all 10 runs finish on both
  lines (Green by 08:35, Red by 10:26 from a 05:00 start). Tests: plan
  tests read the file order; zone tests run a track-ordered copy of the
  schedule (`TRACK_SCHEDULE`).

## 2026-11-03 — A schedule starts when the clock runs with it

From Landis: loaded five minutes in, a schedule dispatched every run due
in those five minutes at once, piling them up on the yard exit.

- `ctc/model.py`: a schedule's time zero is the moment the clock runs
  with it loaded: at Run (`set_clock_paused(False)`, or the first step),
  or at once if loaded while the clock runs. The runs are planned again
  from it (`plan_run(start_s=...)`). `CtcSnapshot.schedule_start_s`
  reports it; the Auto dispatch panel shows "T = 0 at …".
- Tests: `ScheduleStartTest`; `RetireTest` now starts the clock before it
  sets a run's progress by hand.

## 2026-11-02 — Switch commands outlast maintenance mode

From Landis (INPUT-1, relayed by Kevin 2026-11-02, and confirmed directly):
a switch set in maintenance mode holds through Automatic and Manual until
the dispatcher, back in maintenance mode, releases it.

- `ctc/model.py` `set_maintenance_mode()`: leaving maintenance mode no
  longer clears the switch commands. `release_switch()` now requires
  maintenance mode, as `set_switch()` does.
- Panel texts, the README and `tests/test_ctc_boundary.py` follow.
  Truth: proposal `20261102-0829-maintenance-switches-persist.md` on
  `claude/quirky-fermi-sickg4`.

## 2026-10-30 — Windows GUI walkthrough fixes (CTC)

From Landis's review of the CTC findings in
`documents/central-harness-windows-gui-2026-10-28.md`.

- F32: a block closes at once, even with a train in it. The pending
  "closing" state is gone from `ctc/model.py`, `CtcSnapshot`
  (`pending_closures`), the wire format, the host and the panels; it was
  already locked and refused authority exactly like a closed block. Truth
  proposals `20261030-1447-*` on `claude/ctc-harness-findings` supersede
  `block-closure` and `no-authority-into-unusable-block`.
- F20: `preview_dispatch()` (model and `CtcOffice`) and
  `CtcHost.dispatchPreview()`: the Dispatch panel shows the suggested
  speed and authority as soon as line, train and destination are picked,
  counted from the yard exit block for a train still in the yard.
- F21: the Dispatch panel's error clears as soon as any field changes.
  Every CTC time display already wraps at midnight; a test now says so.
- Maintenance block picker: `BlockField.qml` takes a typed block number
  as well as a pick from the list (Close block, and Set authority).
- Switch labels: every switch reads "normal; reverse"; Red 9, Green 58
  and Green 62, listed by their yard leg alone, get their main-line leg
  (`_switch_legs()` in `ctc_host.py`).
- F22: the always-empty Trains /hr tile is dropped, so the two ticket
  tiles show up to six digits in full; trains per hour stays in the table.
- F31: the minimized Train occupancy pill sits in the track view's bottom
  row instead of over the legend.
- F32b: the Close block panel is wider, so "YES, CLOSE BLOCK" shows in
  full.

## 2026-10-28 — The gap is kept at a switch set against the route

From Landis and Harry Tye's agreement on CTC-3, relayed by Kevin: a
switch's blocks are next to each other whatever position it reports.

- `ctc/routing.py` `authority()`: an authority that stops at a switch not
  set for the route now keeps the gap too. Before, it returned without
  `keep_gap()`. With switch 76 reverse and a train on 77, a follower on 75
  was given 76, where the wayside's switch lock on 76 then held the switch
  reverse under it for good once the head left for 101. It now waits on 75.
- `tests/test_ctc_authority.py`: `GapTest` gains the case.

## 2026-10-28 — The gap is kept against every other train

From Landis's reply, relayed by Kevin: keep the one empty block, and never
give a train authority that would put it next to another train; the
waysides hold two adjacent trains, which deadlocks them.

- `ctc/routing.py` `keep_gap()`: an authority is pulled back until its last
  block is next to no block another train occupies (or a failed block) and
  none another train's authority holds, along the route or off it (a
  switch's other leg). This now covers another train's authority (two
  trains head on stopped one block apart before), a train just past the
  destination, and the hold round a loop (`ctc/model.py`). The reason names
  the block the authority would have been next to.

## 2026-10-27 — One empty block between trains

From Braden Bosilovich and Harry Tye's answer to the module owner review
(CTC-1, CTC-2), relayed by Kevin; Landis has not agreed yet.

- `ctc/routing.py` `authority()`: before an occupied block (a train, or a
  failed block) authority now ends two blocks short of it, so one empty block
  stays between trains. A wayside has no direction or memory, so it holds a
  train while a block it could move into is occupied; with no gap it holds a
  follower and its leader together. Closed and closing blocks, another
  train's authority and switches not set still stop it one block short.

## 2026-10-25 — Owner review answers: zones by direction, Red yard exit

From Landis's replies to `documents/module-owner-review.md` (CTC-1, SW-2,
LAYOUT-1), relayed by Kevin.

- `ctc/scheduler.py`: two-way zones are reserved by direction, not by train.
  Trains going the same way share a zone; a train waits only for trains in it
  the other way. Loops are no longer folded into a zone (Red 53–66, Green
  86–100 and 1–12 are one way), so the zones are Green 77–85 and 13–28 and
  Red 16–52 on the default schedule. A train that has turned keeps its order
  on, but its authority stops round the loop a block short of the loop's end
  (`AutoDispatcher.hold_at`, authority reason `held`; its route ends there so
  it claims no switch beyond). It comes back into the zone once the trains
  following it are through. While it waits there, no train enters the zone
  the other way for the first time (no new release from the yard). A zone
  that ends at the yard entry block is still held until the run is back in
  the yard.
- `ctc/tracking.py` (`YARD_EXIT_FROM`), `ctc/model.py`, `ctc/scheduler.py`: a
  train leaving the yard heads out the fixed side of the yard switch, as the
  Track Model runs it: Red 9 on to 10, never back to 8 (the Track Model's
  layout reading is the master). The default Red run now goes 9→10…16, up to
  52, round the loop, back down to 16 and through Shadyside (7) to 9; its
  stations in track order are 16, 21, 25, 35, 45, 48, 60, 7.

## 2026-10-22 — Red yard return

Correction commit: `5d51051` (course data restoration and reader agreement).

`ctc/track_layout.py:120–121` interprets the Red yard at block 9 and hardcodes Red
`to_yard` to finish there. This preserves the course data and agrees with
the other readers. Landis and the Track Model owner should review this
implementation assumption: point 9, NORMAL to 8, REVERSE to yard, fixed
side 10 and light on 10. Kevin established the physical connection at
block 9 in section C; the leg geometry remains unconfirmed.
