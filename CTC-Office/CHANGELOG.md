# CTC Office — changes for review

Changes to the owner's module code during integration, for review.

---

## 2026-11-12 — The train in front claims its zone pass first

From Landis's report of zero suggested speeds on both lines. An
investigation of the full-system run found three causes:

- Red: the overrun (previous entry).
- Green, 145–150: the Track Controller SW's loop guard. That is the
  wayside's.
- Green, at 75: this one, from `LOOP_LIMITS` (`a520ee3`).

- **What happened.** G6 stood 618 s at 75 with authority 0 and nothing
  ahead. G9 and G10, behind it, had been sent on their pass into
  section N while G6 was still dwelling at Dormont (73), and took two
  of the loop's four places. They could not pass G6, and G6 waited
  until two trains left the loop. G2, G3, G4, G7 and G8 waited 5 to 9
  minutes at 75 the same way.
- **The fix.** `ctc/scheduler.py` new `_behind_one_to_go()`, read by
  `_blocked()`: a run claims a zone pass only once no train ahead of
  it, between it and the zone, still has that pass to make the same
  way.
- **Hardening.** `planned_route()` now looks for the train's block only
  as far as the run has been sent, as `_locate()` does. A leg can run
  the same blocks twice, and the later pass is not where the train is.
- **Tests.** `tests/test_ctc_green_76.py` `ClaimOrderTest`: G9 behind
  G6 at Dormont does not claim before G6. It fails without the fix.

## 2026-11-12 — The suggested speed leaves room to stop

From Landis, after Red locked up in the full-system run with sidings
on.

- **What happened.** R7 was told to stop at the end of 58 behind R1,
  dwelling at 60. It came into 58 at 13 m/s, the speed from which a
  full train just stops in 58's 75 m, braked for 10 s and rolled onto
  59. The Red wayside holds a train with an occupied neighbour, so it
  held both for good. R1 and R2 overran Herron Ave (16) the same way.
- **The cause.** Both train controllers keep the commanded speed and
  brake only once their authority is 0. A speed with no room left any
  delay before the brake took hold to carry the train a block too
  far: onto a switch it then locked, or next to the train ahead.
- **The fix.** `ctc/model.py` `_suggested_speed_mps()`: the speed v
  from which a full train stops within the blocks ahead after running
  on `STOP_REACTION_S` (3 s, new) at v first. That is,
  v·3 + v²/(2b) = distance, with b the length-weighted service-brake
  rate over those blocks. Flat 100 m: 11 m/s, not 14. This reverses
  the 2026-11-09 decision to add no margin (finding C4).
- **Measured** on the new realistic railway (below), under the train
  controllers' own rule, at reaction delays of 0.5, 1 and 2 s.
  - No margin: Red stuck at every delay.
  - Smaller margins (1–2 s, or 70–90 % of the distance) stuck at 2 s.
  - With 3 s, Red finished every time (about 06:37) with no overruns.
  - Green was unchanged.
  - Keeping two empty blocks between trains deadlocked Red even with
    ideal braking: the sidings could not clear.
- **New tests.**
  - `tests/realistic_railway.py`: trains brake after a reaction delay
    and can run past their authority, occupancy is one block per train
    as the Track Model reports it, and the real Red (Track Controller
    HW) and Green (Track Controller SW starter) programs run the
    waysides.
  - `tests/test_ctc_realistic.py`: both lines' whole schedules under
    both controller rules. Every run finishes with its stops in order.
    No train is frozen beside another, collides, runs through a switch,
    or passes the end of the CTC's authority.
  - Green still has runs past a wayside's cut: the Track Controller
    SW's loop guard for 1–12 drops the authority of trains moving on
    145–150 and throws switch 28 ahead of them. That is the wayside's,
    and is listed in the test's summary only.
- Speeds in `test_ctc_authority.py`, `test_ctc_next_block.py` and
  `test_ctc_tracking.py` are updated for the margin.
- Truth proposal `20261112-1754-suggested-speed-reaction-margin.md`.
  It replaces the unpromoted
  `20261109-1135-suggested-speed-full-train-grade.md`.

## 2026-11-12 — Red passing sidings on

From Landis: "lets turn on the passings". In the 2026-11-12 full-system
run, every Red train waited 7 to 16 minutes at Shadyside (7) while
another train used the one two-way stretch, 16 to 52.

- **On.** `ctc/scheduler.py` `PASSING_SIDINGS = True`. The Red Track
  Controller sets switches 27, 32, 38 and 43 for the CTC's route
  requests (PR #58).
- **Each stretch one way, for every run.** New `WRONG_WAY` and
  `goes_wrong_way()`, used by `leg_route()` in place of `REUSE_COST`.
  - The rule: out toward the loop on the main line (28–32, 39–43),
    back on the sidings (72–76, 67–71), and round the loop 53–66 in at
    53 and out from 66.
  - Why fixed: avoiding only track a run had already run did not split
    16–52. A run's first leg can go out and back (Red 1 runs round the
    loop to Shadyside), and the runs went round the loop both ways. Red
    now has three short two-way stretches: 9–27 (16–27 with the track-
    order test schedule), 33–38 and 44–52.
- **Room on the one-way track beyond.** New `_stretch_after()` and
  `_stretch_full()`, read by `_blocked()`. A train is sent through a
  two-way stretch only if the one-way track it comes out onto has room
  for it: as many trains as it holds a block apart, counting those on
  it and those in the stretch heading onto it. This is the loop rule,
  for any one-way track between two stretches. Without it, on the
  tests' railway all ten Red runs were out at 06:00. The sidings and
  the main line beside them were full both ways, and no train moved
  again.
- **The model keeps a run to its plan.** `ctc/model.py`: a train
  standing on the planned way (at a stop) no longer sends a run the
  wrong way round. Red 2 and 3 went into the loop at 66 toward Red 1
  dwelling at 60. A closed or failed block on the plan still lets it
  take another way.
- **On the tests' railway**, all ten Red runs make their stops in the
  file's order and are done at 06:42. Before, they were done at 10:27.
  The longest waits are now about 17 minutes, on the 72–76 siding.
- **Tests.** `test_ctc_scheduler.py`:
  - new `EndToEndTest.test_all_red_runs_pass_at_the_sidings` and
    `ZoneTest.test_no_pass_onto_one_way_track_with_no_room`; both fail
    without the room rule;
  - updated `test_the_zones`, and the loop tests for the new loop
    direction: a train waits at 65, not 54.
  - A train waiting at the loop's end holds back only its own stretch:
    R3 now leaves and passes it at a siding.

  `test_ctc_train_events.py` `RetireTest`: the run is placed at its
  plan's last 56. Its plan passes 56 and 57 before, and with sidings on
  the model follows the plan.
- Truth proposal `20261112-1551-two-way-zone-passing-sidings.md`. It
  replaces the unpromoted `20261112-1433-two-way-zone-pass-can-stop.md`.
  Which way each stretch runs, and the room rule, are proposed and
  await Landis's confirmation.

## 2026-11-12 — A train gives up a pass only if it can stop short

From Landis: the confirmation run of `a520ee3` deadlocked at 76.

- **What happened.** G3 was on 75 at line speed with authority into
  section N when G1 started waiting at 99. G3 gave up its pass, and its
  authority dropped to 0. It could not stop and ran on onto 76, the
  block switch 76 is listed on. G1 then had N, came down to 78 and
  needed 76 reverse, which the wayside holds normal while a train is
  on 76. Neither moved again.
- **The fix.** `ctc/scheduler.py` new `_gives_up()`, `World.can_stop_by`,
  and `ctc/model.py` new `_can_stop_by()`. A train gives up a pass only
  if, at the speed it was last suggested, it can stop by the end of the
  block where it would wait short of the zone. That speed must be no
  more than the one suggested with its authority ending there. A train
  too close or too fast keeps the pass and goes through. The returning
  train waits for it, as before. A train held at low speed still gives
  way, as G10 on 148 did at the 1–12 loop.
- **Tests.** `tests/test_ctc_green_76.py` `GiveWayTest`: sent up N from
  66, a train gives way and waits at 75. On 75 at speed, it keeps its
  pass. The second test fails without the fix.
- Truth proposal `20261112-1433-two-way-zone-pass-can-stop.md`. It
  replaces the unpromoted `20261112-1334-two-way-zone-pass-and-loop-limit.md`.

## 2026-11-12 — A pass not yet used gives way; four trains in section N's loop

From Landis, after the Schedule v4 full-system run of 2026-11-12, in
which Green stopped for good at the 1–12 loop.

- **A pass a train is not in yet gives way.** `ctc/scheduler.py`
  `_reach()`, new `_awaited()` and `_gives_way()`. Once a train waits
  round a loop to come back into a two-way zone, a train sent into the
  zone the other way that is not in it yet gives up its pass and waits
  short of the zone. Before, only a run still in the yard did
  (`eea89f8`). A train already in the zone keeps its pass.
  - **The run's deadlock:** G10 had the pass into 13–28 on its way to
    the loop and stood on 148, held there by the Green Track
    Controller's D–F loop guard while trains were in 7–12. G1 waited at
    2 for G10's pass, and the wayside set switch 28 for G1, against the
    CTC's request. Nothing moved again.
  - **The same rule at section N:** a run no longer keeps a pass into N
    claimed from far off (G7 from block 59) while a train waits at 99.
- **Four trains in the loop through section N.** `ctc/scheduler.py`
  new `LOOP_LIMITS`, read by `_loop_room()`: Green's loop through
  section N takes 4 trains, not the 7 it holds. The Green Track
  Controller holds the train on 75 while more than 5 of blocks 76–100
  are occupied, which the CTC cannot see. With 7 let in, a train with
  the pass into N could be held on 75 while the trains round the loop
  waited for N.
- **Tests.** New `tests/test_ctc_green_76.py`:
  - section N both ways: the switch 76 requests, holds at 75 and 99,
    and following trains;
  - the loop limit;
  - the whole Green schedule on a railway that sets switches only as
    the CTC requests and holds 75 as the wayside does. All ten runs
    finish, no train stands over 600 s with no authority near 76, and
    76–100 never holds more than 5 trains.
- Truth proposal `20261112-1334-two-way-zone-pass-and-loop-limit.md`.
  It replaces the unpromoted `20261112-1045-two-way-zone-yard-pass.md`.

## 2026-11-12 — A run still in the yard gives up its zone pass

From Landis, after the Green Line locked up at section N in the
Schedule v4 run (every module, both lines).

- **The lock-up.** G9 was ordered out through N (77 to 85) while
  still in the yard, held there by the yard headway. That order
  counted as its pass through N, so G4, waiting at 99 to come back
  through N, stayed held. G1, G2 and G3, on their next lap, were held
  at 75 for G4, and G9 came out behind them. G4 waited for G9, G9
  behind G1, G1 for G4: nothing moved again from 05:44.
- **The fix** (`ctc.scheduler`). A run with its order that the model
  has not yet released from the yard gives up its pass, and waits in
  the yard, once the first zone pass on its way is blocked, as when a
  train waits round a loop to come back. This is the rule as decided
  (the next runs wait in the yard), now also for a run ordered before
  the other train got there. A run the model has already released
  keeps its pass: it is coming out. The model passes the released runs
  to the scheduler (`World.released`).
- Tests: `ZoneTest` in `tests/test_ctc_scheduler.py` (2 new).

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
