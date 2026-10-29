# CTC Office — changes for review

Changes to the owner's module code during integration, for review.

---

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
