# Track Model — manual verification script

Run these with both windows open. Each case lists its steps, then what you
should see. Tick the box when it passes; note anything else beside it.

Automated tests first:

```bash
TrackModel/.venv/Scripts/python TrackModel/run_tests.py
```

It prints every automated test with a plain-English description and
PASS / FAIL.

## Setup

From the repository root, in two terminals:

```bash
TrackModel/.venv/Scripts/python TrackModel/main.py           # Track Model window
TrackModel/.venv/Scripts/python TrackModel/test_ui/main.py   # Test UI window
```

**Units.** The test UI shows interface units (m, m/s, deg), except ambient
temperature, which you enter in °F. The Track Model window shows display
units (ft, mph, °F).

**Moving a train quickly.** Leave **Act as the Train Model** ticked. Each
tick the test UI adds speed × 0.1 s to the train's offset, and when the
feed names a new block it moves the train there with offset 0. Every Blue
block is 50 m long. To push a train over a boundary in one tick, set its
`offset` to 49, set its `speed` to 20, and press **Step one
tick** (49 + 2 = 51 ≥ 50).

**Selecting things.** Text fields commit when you press Enter or leave
the field. "Block panel" means **From Track Controller — block**. "Train
panel" means **From Train Model — trains**.

**Choose the line first.** The test UI opens on the GREEN line. The
cases TC-03 to TC-19 use the Blue line, so first set **Block filter →
Line** to **BLUE**. The block pickers, the switch, signal and gate lists,
and the occupancy, failure and device read-back all follow the chosen
line. Rows show short names without the line, e.g. `A-5` for `BLUE A-5`.
Section and **Blocks, e.g. 5-20** narrow the block pickers further.

**Row names.** The test UI shortens row names so they fit:

| Panel | Row | Means |
|---|---|---|
| Train panel | `block`, `offset`, `speed`, `changed`, `capacity` | the Train Model's report |
| Block panel | `speed`, `authority` | commanded speed and authority for the block |
| Gates, heaters panel | `E-19`, `heat B` | a crossing gate (true = closed); section B's heaters |
| Outputs — to Track Controller | `occupied`, `failures`, `heaters on`, `sold now`, `sold total` | read-back; occupancy, failures and heaters cover the chosen line |
| | `trk temp` | track temperature (°C) of the selected block's section |
| | `sw …`, `sig …`, `gate …` | switch, signal light, crossing gate |
| Outputs — to Train Model | `block` … `station` | Track Info |
| | `cmd speed`, `authority` | Track Signal |
| | `beacon`, `boarded` | beacon, passengers boarded |
| Outputs — to Train Controller | `seen now`, `last seen` | signal seen this tick; last colour seen |

Press **Reset module** between cases unless a case says otherwise.

---

### TC-01 Connection, either start order
- [ ] Pass

1. Start the Track Model window, then the test UI.
2. Close both. Start the test UI first, wait 3 s, then start the Track
   Model window.

**Expected**

- Both orders end connected. The test UI header changes from **NOT
  CONNECTED** to **HELD**, and the "Waiting for the Track Model" callout
  disappears.
- The test UI opens on GREEN: **Block filter** reads "150 of 150 GREEN
  blocks". It lists 6 switch rows, 6 signal rows and 2 gate rows, plus
  26 heater rows, one per section (`heat A` … `heat Z`). On BLUE it
  lists 1, 1, 1 and 3 heaters. On RED it lists 7, 7, 2 and 20 heaters.
- The Track Model window header shows **PAUSED** and `00:00:00`.

### TC-02 Clock: step, run, hold, 10×
- [ ] Pass

1. Press **Step one tick**.
2. Set Clock to **Run** and watch for 5 s.
3. Set Rate to **10×** for 5 s, then back to **1×**.
4. Set Clock to **Hold**.

**Expected**

- One step: Tick = 1 and the Track Model window clock still reads
  `00:00:00` (0.1 s).
- Run: the Track Model window shows **RUNNING**, and its clock advances
  at about real time.
- 10×: Tick climbs about ten times faster, and **dt (fixed)** stays at
  `0.100 s`.
- Hold: the Track Model window goes to **PAUSED** within about half a
  second.

### TC-03 Track Controller commands become states
- [ ] Pass

1. With the line set to BLUE, in the switch panel, set `A-5` to
   **REVERSE**.
2. In the signal panel, set `A-4` to **GREEN**.
3. In **From Track Controller — gates, heaters**, set `A-3` to true and
   `heat A` to true.
4. Step one tick, then step a second time without changing anything.

**Expected**

- In **Outputs — to Track Controller**: `sw A-5` = REVERSE,
  `sig A-4` = GREEN, `gate A-3` = true, and
  `heaters on` shows `A`.
- The values are unchanged after the second step: commands persist.
- In the Track Model window, choose **Switches & Lights**, then Line
  **BLUE**. The `BLUE A-5` row shows REVERSE, and the `BLUE A-4` light
  shows GREEN. Back on **Blocks**, click `BLUE A-3`; under **Selected**,
  Crossing reads **Gates down**.

### TC-04 Train placement and the Train Model feed
- [ ] Pass

1. In the train panel, set New train ID to `T1` and Start block to
   `BLUE A-1`, then press **Add train**.
2. Step one tick.

**Expected**

- `occupied` = `A-1`.
- In **Outputs — to Train Model, T1**:
  - `block` = BLUE A-1
  - `limit` = 13.889 (50 km/h)
  - `polarity` = false
  - `station` = none
  - `beacon` = none
  - `boarded` = 0
- The Track Model window's **Trains on track** lists T1 in BLUE A-1, with
  offset 0 ft.

### TC-05 Commanded speed and authority are per block
- [ ] Pass

1. Continue from TC-04. In the block panel, pick `BLUE A-1`. Set
   `speed` to 10 and `authority` to `BLUE A-5`.
2. Step one tick.
3. In the block panel, pick `BLUE A-2`. Set its speed to 5 and its
   authority to `BLUE B-10`.
4. Move T1 into A-2: offset 49, speed 20, then step.
5. Still on `BLUE A-2` in the block panel, set authority to `BLUE Z-99`
   and step.

**Expected**

- The speed field takes whole numbers only, because commanded speed is
  an int.
- After step 2: `cmd speed` = 10 and
  `authority` = BLUE A-5.
- After step 4: the feed reads BLUE A-2, commanded speed 5 and authority
  BLUE B-10. Both change with the block the train is in.
- Step 5: the callout **Rejected by the Track Model** names `BLUE Z-99`,
  and nothing else changes. Clear the authority field afterwards.

### TC-06 Movement, occupancy and polarity
- [ ] Pass

1. In the Track Model window, choose Line **BLUE**. Add T1 at `BLUE A-1`,
   set `speed` to 20, and set Clock to **Run**.
2. Watch about 15 s, then set Clock to **Hold**.

**Expected**

- T1 crosses one block every 2.5 s: A-1 → A-2 → A-3 → A-4 → A-5 → B-6 →
  … → B-10. The switch is NORMAL, so it takes the B leg.
- `occupied` always names exactly the one block T1 is in. The
  Track Model window's **Occ** column follows it, and the old block
  clears.
- `polarity` flips on every block change.
- At B-10, the end of the branch, T1 stays put while its offset keeps
  growing. This dead-end behaviour is expected.

### TC-07 The train takes the leg the switch is set to
- [ ] Pass

1. Set switch `BLUE A-5` to **REVERSE**.
2. Add T1 at `BLUE A-4` with speed 20, and Run until T1 passes A-5.

**Expected**

- T1 goes A-4 → A-5 → **C-11** → C-12 … C-15.
- `sw A-5` stays REVERSE the whole time. The Track Model never
  moves a switch itself.

### TC-08 A signal is seen once, on entry
- [ ] Pass

1. Set signal `BLUE A-4` to **YELLOW**.
2. Add T1 at `BLUE A-3`. Set offset 49 and speed 20, then Step once.
3. Step again.
4. Set signal `BLUE A-4` to **GREEN**, then Step.

**Expected**

- After step 2, T1 is in A-4. Under **Outputs — to Train Controller**:
  `seen now` = YELLOW and `last seen` = YELLOW.
- After step 3: `seen now` = none, and `last seen` is still YELLOW.
- After step 4: `sig A-4` (Track Controller output) = GREEN, but
  `seen now` stays none and `last seen` stays YELLOW. The train cannot
  see the change behind it.
- Entering an ordinary block, such as A-2 or A-3, never produces a
  `seen now`.

### TC-09 Rollback to the previous block
- [ ] Pass

1. Add T1 at `BLUE A-3`, then move it into A-4 (offset 49, speed 20,
   step).
2. Set speed 0 and offset -1, then Step.

**Expected**

- T1 goes back to **BLUE A-3**, which is the block it came from, and
  `polarity` flips again.

### TC-10 Beacons next to stations
- [ ] Pass

1. Set **Block filter → Line** to GREEN, add T1 at `GREEN A-1`, and
   Step.
2. Set the train's `block` to `GREEN A-2` (the PIONEER station block)
   and Step.
3. Set `block` to `BLUE A-2` and Step.

**Expected**

- At GREEN A-1: `beacon` = `PIONEER / L`.
- At GREEN A-2: `beacon` = none and `station` = PIONEER.
  The beacons sit on the station's neighbours.
- At BLUE A-2: `beacon` = none.

### TC-11 Ticket sales and boarding
- [ ] Pass

1. Run the clock for about 30 s with no trains, then Hold.
2. In the Track Model window, choose Line **BLUE** and look at **Waiting
   at stations**.
3. Add T1 at `BLUE B-10` (station B) with speed 0. Set
   `capacity` to 2, then Step.
4. Set speed 5 and Step.

**Expected**

- While running, `sold total` climbs, and `sold now` occasionally shows
  e.g. `B+1`. These outputs go to the Track Controller only.
- Waiting at stations shows counts for B and C.
- Step 3: `boarded` = 2, or fewer if fewer were waiting, and
  station B's waiting count drops by the same amount.
- Step 4: `boarded` = 0, because a moving train does not
  board.

### TC-12 Murphy failure from the Track Model window reaches the test UI at once
- [ ] Pass

1. Make sure the clock is held. Do not step during this case.
2. In the Track Model window, choose Line BLUE, click `BLUE A-2`, and set
   **Failure (Murphy)** to **Circuit**.
3. Set it back to **None**.

**Expected**

- With no step, the test UI's `failures` immediately shows
  `A-2 TRACK_CIRCUIT`, and `occupied` shows `A-2`: a failed track
  circuit reads as occupied.
- The Track Model window header reads `BLUE · 1 FAILED`, and A-2's row
  shows OCC and TRACK_CIRCUIT.
- Setting None clears all of these.

### TC-13 Power failure from the test UI
- [ ] Pass

1. With the line set to BLUE, set signal `A-4` to **GREEN** and `heat A`
   to true, then Step twice.
2. In the block panel, pick `BLUE A-4`. Choose **POWER** under **Test
   only** and press **Set failure**.
3. Set signal `A-4` to **YELLOW** and Step.
4. Choose **NONE** and press **Set failure**, then Step.

**Expected**

- After step 2: `failures` shows `A-4 POWER`, and `occupied` shows
  `A-4`. `sig A-4` reads **RED**: a light without power is RED, even
  though GREEN was commanded. `heaters on` no longer lists `A`, because
  section A has lost power. The Track Model window shows POWER on A-4.
- After step 3: `sig A-4` stays RED. The new command is stored, but the
  light has no power.
- After step 4: `sig A-4` shows **YELLOW**, the last command, and
  `heaters on` lists `A` again.

### TC-14 Test-only block edit
- [ ] Pass

1. In the block panel, pick `BLUE A-1`. Under **Test only**, set Length
   (m) to 10, leave the other fields blank, and press **Edit selected
   block**.
2. Add T1 at `BLUE A-1`. Set offset 9 and speed 20, then Step.

**Expected**

- In the Track Model window, BLUE A-1's length reads **33 ft** (10 m).
  The other values are unchanged.
- T1 moves to BLUE A-2 after one step, because 9 + 2 ≥ 10.

### TC-15 A train runs into the yard
- [ ] Pass

1. Set switch `GREEN I-57` to **REVERSE**.
2. Add T1 at `GREEN I-56`. Set offset 9999 and speed 0, then Step. T1 is
   now in I-57.
3. Set offset 9999 again and Step.

**Expected**

- After step 3, T1 is gone. It has left the train list, no block is
  occupied, and the Track Model window's **Trains on track** is empty.

### TC-16 Invalid input is rejected whole
- [ ] Pass

1. Add T1 at `BLUE A-1` and Step once. Note the Track Model window clock.
2. Set the train's `block` to `NOWHERE 1` and Step.

**Expected**

- The callout **Rejected by the Track Model** names `NOWHERE 1`.
- The Track Model window clock and every output stay as they were.
- The test UI's Tick still counts up, because it counts ticks sent, not
  ticks accepted.

### TC-17 Display units in the Track Model window
- [ ] Pass

1. In the Track Model window, choose Line GREEN and click `GREEN A-1`.
2. In the test UI's **Environment** panel, set `ambient` to 32 °F and
   Step.

**Expected**

- GREEN A-1 shows Length **328 ft** (100 m), Grade **0.29°** (0.5 %),
  and Speed limit **28 mph** (45 km/h).
- Conditions shows **32 °F**. The value went to the Track Model as 0 °C
  and came back.

### TC-18 The test UI is removable
- [ ] Pass

1. With the clock running and a train on the track, close the test UI.
2. Reopen the test UI and Step once.

**Expected**

- The Track Model window keeps running and shows **PAUSED** within about
  half a second.
- The reopened test UI reconnects by itself. Its inputs start fresh, so
  after the first step the old train is no longer reported and leaves
  the track.

### TC-19 Reset
- [ ] Pass

1. Set switch `BLUE A-5` to REVERSE, add a train, and Step a few times.
2. Press **Reset module**, then Step.

**Expected**

- Tick returns to 0, then 1.
- The train list is empty.
- `sw A-5` is back to **NORMAL**, both in the test UI's switch
  panel and in the outputs.
- The Track Model window clock restarts from `00:00:00`.

---

## Green line

The Green line is the main line in use. Set **Block filter → Line** in
the test UI back to **GREEN** (it opens there), and choose Line **GREEN**
in the Track Model window for these cases.

### TC-20 A train out of the yard heads onto the line
- [ ] Pass

1. Add T1 at `GREEN K-63`, which is where the yard joins the line. Set
   speed 0 and offset -1, then Step.
2. Set offset 99 and speed 20, then Step.
3. Set speed 0 and offset -1, then Step. Then set offset -1 again and
   Step once more.

**Expected**

- Step 1: T1 stays at K-63. A train that has just come out of the yard
  does not roll back into it.
- Step 2: T1 moves to **GREEN K-64**, not J-62.
- Step 3: the first rollback returns T1 to K-63. The second keeps going
  back, through the switch at 63 as it is set: NORMAL leads to **J-62**.
  A train keeps rolling back; it does not bounce between two blocks.

### TC-21 The full course loop
- [ ] Pass

1. In the switch panel, set:
   - `GREEN N-85` = NORMAL
   - `GREEN N-77` = REVERSE
   - `GREEN F-28` = NORMAL
   - `GREEN D-13` = NORMAL
   - `GREEN I-57` = REVERSE
2. Add T1 at `GREEN K-63` with speed 50. Set Rate to **10×** and Clock to
   **Run**.
3. Watch **Trains on track** in the Track Model window, or
   `block` in the test UI. The loop takes about half a
   minute at 10×.

**Expected**

- T1 runs 63 → 64 … 100, then **85** (back through the switch) → 84 …
  77, then **101** → … 150, then **28** → 27 … 1, then **13** → 14 … 57,
  and then leaves into the yard. It disappears from the train list and
  no block stays occupied.
- Exactly one block is occupied at a time, all the way round.
- No switch position changes by itself.

### TC-22 Taking the other leg at 77 and 57
- [ ] Pass

1. Repeat TC-21 with `GREEN I-57` = NORMAL.
2. Then set `GREEN N-77` = NORMAL and watch the return trip from 85.

**Expected**

- With 57 NORMAL, T1 continues 57 → 58 … 62 → 63 → 64 and starts round
  again instead of entering the yard.
- With 77 NORMAL, coming back from 78 T1 goes to **76**, not 101.

### TC-23 Green signals are seen on entry
- [ ] Pass

1. Set signal `GREEN N-78` to YELLOW and `GREEN N-84` to GREEN.
2. Run T1 from `GREEN K-63` with the TC-21 switch settings, at 1×. Watch
   **Outputs — to Train Controller**.

**Expected**

- `last seen` becomes YELLOW as T1 enters N-78, then GREEN as it enters
  N-84.
- On the way back the order reverses: GREEN at N-84, then YELLOW at N-78.
- Changing a light after T1 has entered its block never changes what T1
  has seen.

### TC-24 Green track circuit, beacons and stations
- [ ] Pass

1. Pick `GREEN M-76` in the block panel. Set speed 12 and authority
   `GREEN O-88`.
2. Add T1 at `GREEN M-76` and Step.
3. Run the clock for about 20 s with no other changes, then Hold. Set
   T1's `block` to `GREEN P-96`, set speed 0 and capacity 4, then
   Step.

**Expected**

- At M-76: commanded speed **12**, authority **GREEN O-88**, and beacon
  **MT LEBANON / LR**, because MT LEBANON at N-77 has platforms on both
  sides.
- At P-96: `station` = CASTLE SHANNON, and
  `boarded` = 4, or fewer if fewer were waiting.

### TC-25 Direction of travel
- [ ] Pass

1. In the Track Model window, choose Line GREEN and look at the **Dir**
   column. Click `GREEN C-10`, then `GREEN D-15`.
2. In the test UI, add T1 at `GREEN C-10`. Set offset 99 and speed 20,
   then Step.

**Expected**

- Dir shows `↔` on 13–28 and 77–85, and `→ <next block>` everywhere
  else: C-10 shows `→ C-9`, A-1 shows `→ D-13`, Z-150 shows `→ F-28`,
  and I-57 shows `→ J-58, YARD`.
- The selected block's Direction row reads "One way to GREEN C-9" for
  C-10, and "Both ways: GREEN D-14, GREEN D-16" for D-15.
- T1 moves from C-10 to **C-9**, down toward A, not up to 11.
- On Line BLUE or RED, the Dir column is blank: those lines are not
  annotated yet.

### TC-26 Block filter
- [ ] Pass

1. With Line GREEN, set Section to **B**.
2. Set Section back to **All**, type `20-25` in **Blocks, e.g. 5-20**,
   and press Enter.
3. Type `9-3` and press Enter.
4. Press **Clear**, then set Line to **RED**.

**Expected**

- Step 1: the summary reads "3 of 150 GREEN blocks", and the block
  picker offers only B-4, B-5 and B-6. The selected block jumps to B-4.
- Step 2: the pickers offer GREEN 20 to 25, which run across sections E
  and F.
- Step 3: the callout reports that the range runs backwards, and the
  filter keeps 20–25.
- Step 4: all 150 GREEN blocks come back. Then on RED, only Red blocks
  and Red devices show, e.g. switch rows `F-16`, `H-27` and so on.

### TC-27 Heaters warm their section; ambient stays put
- [ ] Pass

1. With Line GREEN, set `ambient` to 32 °F. In the block panel, pick
   `GREEN B-5`. Set `heat B` to true.
2. Set Rate to **10×**, Clock to **Run** for 60 s (10 simulated
   minutes), then **Hold**.
3. Set `heat B` to false, and run another 60 s at 10×.

**Expected**

- After step 2: `trk temp` (section B) reads about **8.6 °C**, up from
  0 °C. In the Track Model window's **Switches, lights & heaters** view,
  section B shows Heater ON and about 47.6 °F, and every other section
  stays at 32.0 °F. **Conditions → Ambient temperature** still reads
  32 °F.
- During step 3: section B cools back toward 32 °F.
- Selecting any block in section B shows its Heater and Track temp in
  the Selected panel.

### TC-28 Failure effects on a train
- [ ] Pass

1. With Line GREEN, pick `GREEN C-9` in the block panel and set its
   speed to 12. Add T1 at `GREEN C-9` and Step.
2. Set a **BROKEN_RAIL** failure on `GREEN C-9` and Step.
3. Set the failure back to **NONE** and Step.

**Expected**

- Step 1: T1's `cmd speed` is 12.
- Step 2: `cmd speed` is 0 and `authority` is none, because a broken
  rail cuts the track circuit. `occupied` lists C-9.
- Step 3: `cmd speed` is 12 again.

---

## Known, intended for this round

These are not failures. See the README's "Provisional" list.

- The heater rise (10 °C) and how fast the track warms (5-minute time
  constant) are placeholders until the team picks real values.
- Boarding happens whenever a train is stopped (speed 0) in a station
  block; door state is not known to the Track Model.
