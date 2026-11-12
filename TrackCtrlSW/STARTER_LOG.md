# Starter program log

The starter program is the PLC code a wayside opens with. It is generated from the wayside's own
layout by `default_program_source` and `_switch_rule` in `track_ctrl/controller.py`. Two versions
exist in the repo. **This branch keeps the new one.** Read this file before merging `development`
(or any branch that touches `controller.py`) into `Track-Ctrl-SW`.

Decided by Harry, 2026-10-30: keep the new starter. This log exists so a merge cannot overwrite it
silently.

## The two versions

| | Original starter | Current starter (keep) |
|---|---|---|
| Where | `origin/development`, `controller.py` as of commit `3b0e170` ("match language to hw", 2026-10-20) | `Track-Ctrl-SW`, from `234c353` (2026-10-21, "set each switch for the train coming (Q7)"), carried on through `e5e51d4` and the work after it |
| Switch rule | One line: `SW_s := OCC_leg AND NOT OCC_point AND NOT OCC_normal AND NOT MAINT`, so the switch is reverse only while a train waits on the reverse leg and the main line is clear, else normal. Reverse end not on this wayside: `SW_s := 0`. | `_switch_rule`: set the switch for the train coming. Works out the fixed side of the points from `next_blocks`, then `WANT_N_s`, `WANT_R_s`, `HOLD_s := OCC_point OR (WANT_N_s AND WANT_R_s)`, `SW_s := (HOLD_s AND SWREV_s) OR (NOT HOLD_s AND NOT MAINT AND move)`. Held where it stands (`SW_s := SWREV_s`) if the points or the way in belong to another wayside, or the layout gives no direction. |
| Follower case | Commands normal. | Held while the points are occupied; a train coming for each position holds it where it stands. |
| Inputs it reads | `OCC`, `CLOSED`, `MAINT` | the same, plus, when the wayside has a switch, `SWREV_s` (the read-back) and `CTCSW_s`, `CTCREV_s` (the CTC Office's command, obeyed first) and `REQSW_s`, `REQREV_s` (its route request, obeyed next) |
| Signals, crossings | `AHEAD` = blocks `point+1`, `point+2`; crossing = its block and `number ± 1` | **Not the same code any more:** since 2026-10-30 these and the separation rule use the layout's physical neighbours (`config.neighbours`, `config.within`), not block numbers. Block 101 joins block 77. |
| Separation | `AUTH_n := NOT neighbour` for neighbours `n ± 1`, so an empty block beside a train is held | `AUTH_n := NOT (OCC_n AND next block)`: only a block with a train in it is held, and only for the block ahead of it (from the layout's `next_blocks`). An empty block passes the CTC Office's preloaded suggestion. |

The original starter's separation and neighbour rules were already replaced on this branch before
today; the switch rule is the one most at risk in a merge.

## Fingerprints of the current starter

SHA-256 (first 12 hex digits) of the generated starter source for the default Green and Red
layouts, as of branch commit `e5e51d4` plus the uncommitted work on 2026-10-30 (the neighbour and CTC-command
changes included). Regenerate and update this table whenever the starter is changed on purpose.

| Wayside | Fingerprint | Lines | Switches |
|---|---|---|---|
| GTC-01 | f800be9a413f | 68 | 12 |
| GTC-02 | 03521ed70810 | 64 | 28 |
| GTC-03 | cc2f362bc3ef | 81 | 58, 62 |
| GTC-04 | 998414455400 | 76 | 76, 85 |
| GTC-05 | f2ac5c30c278 | 40 | none |
| GTC-06 | a13ce33ac008 | 41 | none |
| RTC-01 | a2130ba5d790 | 72 | 9, 15 |
| RTC-02 | 2b7896c407b0 | 49 | 27 |
| RTC-03 | bdc197605153 | 87 | 32, 38, 43 |
| RTC-04 | e9471cc143fb | 53 | 52 |
| RTC-05 | 6af88a2d8c5b | 26 | none |

Regenerate them from `TrackCtrlSW` with a script that builds the default module without programs
(`tests/rig.py`, `default_module(programs=False)`) and hashes `default_program_source(controller)`
for each controller.

## Before merging

1. See whether the merge touches the starter:

   ```bash
   git diff HEAD...origin/development -- TrackCtrlSW/track_ctrl/controller.py
   ```

2. Look at `default_program_source`, `_switch_rule` and `_coming_off` in that diff. If the incoming
   side shows the original one-line switch rule (`OCC_leg AND NOT OCC_point ...`), keep this
   branch's version when resolving the conflict.
3. After the merge, regenerate the fingerprints. Every row should be unchanged. Run
   `tests/test_starter_switches.py`, which pins the switch behaviour (follower case included).
4. If the starter is meant to change, change it on purpose, then update the table and add a line
   here saying what changed and why.

## History

- 2026-11-13: loop guard N replaced by a count guard. GTC-04 tells GTC-03 how many of its blocks are
  occupied (`PEER_CNT_GTC04_0..4`); over 5, GTC-03 holds the train on 75 (`AUTH_75 := NOT FULL_GTC04`).
  Switches 76 and 85 are no longer forced, and GTC-04 is no longer told 71..75 (so the test ranking no
  longer sees a train on 75 for switch 76). The top-loop guard is unchanged. GTC-03 and GTC-04 have new
  fingerprints.
- 2026-11-13: loop guard N watches 82..87 (was 86..91) and acts only while 99 is occupied too:
  `DRAIN_N := (82..87) AND OCC_99 AND (71..75)`. GTC-03 is told 82..87 and 99. GTC-03 and GTC-04 have
  new fingerprints.
- 2026-11-13 (latest): the test ranking is back, alongside the relaxed vital lock: the starter's own
  rule, while it sees a train (`ACT_s`), outranks the CTC Office's route request, and a leg's approach
  block is read over the peer link (GTC-04 sees 75 for switch 76). Fingerprints as in the first test.
- 2026-11-13 (later): the test ranking is undone. The CTC Office's route request ranks above the
  starter's own rule again, and the starter no longer reads a leg's approach block over the peer
  link. The 8 waysides with switches are back to their loop-guard fingerprints.
- 2026-11-13 (test): the CTC Office's route request ranks below the starter's own rule while that rule
  sees a train it sets the switch for, or holds it (`ACT_s := HOLD_s OR WANT_N_s OR WANT_R_s`); with
  no train seen, the request still sets the switch. A trailing train's approach block is also read
  over the peer link where the wayside is told it (GTC-04: `PEER_OCC_75` for switch 76). Order now:
  points lock (vital), maintenance command, loop guard, own rule while active, route request, own
  rule at rest. The 8 waysides with switches have new fingerprints.
- 2026-11-13: loop guards (`DRAIN_N`, `DRAIN_DEF`), over a reopened peer link (`PEER_OCC_n`). While a
  train is in 86..91 and another on 71..76, 71..76 are held and switches 85 and 76 set reverse; while a
  train is in 12..7 and another on 145..150, 145..150 are held, switch 12 set reverse and 28 normal.
  The guard ranks below a maintenance command and above a route request. Revised the same day: the N
  approach is 71..75 (a train on 76 locks switch 76, the way out, so it goes on), and the switches
  are set only while the two-way section is clear (`SET_g`; 76..85 for N, 13..28 for the top loop),
  so a train already in it finishes first. GTC-01, -02, -03, -04 and -06 have new fingerprints.
- 2026-11-13: S1 of the Schedule v4 findings. The switch rule no longer sets a switch for a train on
  its fixed side where the layout runs that block both ways into the points (Green 76 from 78, 28 from
  27, 12 from 14, 85 from 84, and Red 9/15 where the same holds). A train there may be heading away,
  and the starter threw switch 76 reverse behind outbound trains. The CTC Office's route request sets
  those switches now. GTC-01, GTC-02, GTC-04 and RTC-01 have new fingerprints.
- 2026-11-12 (later): the section N priority rules are taken out of the starter again. They fought the
  CTC Office's own routing and deadlocked G1 on 99 against G6 on 75. Which train goes first is the
  CTC Office's. The peer occupancy inputs (`PEER_OCC_n`) stay available to programs; the starter does
  not read them. GTC-03 and GTC-04 are back to their 2026-11-10 fingerprints. The peer link itself
  was removed afterwards (see the CHANGELOG): `PEER_OCC_n` no longer exists.
- 2026-11-12: contested section N (Green 77..85, single track used both ways). GTC-03 is told the
  occupancy of 98, 99, 100 and 76 and GTC-04 of 75 (`PEER_OCC_n`, over the link between track
  controllers). A train on 99 or 100 goes first; one on 98 goes unless one is on 76; otherwise one on
  75/76 goes. While side 98..100 goes, `AUTH_75` and `AUTH_76` are 0 and switches 76 and 85 are set
  reverse; while 75/76 goes they are set normal. GTC-03 and GTC-04 have new fingerprints; the other
  nine are unchanged.
- 2026-11-10: the switch rule reads the CTC Office's route request (`REQSW_s`, `REQREV_s`) after the
  maintenance command and before its own rule, and skips a request whose target leg is `CLOSED_n`.
  The 8 waysides with switches have new fingerprints (GTC-05, GTC-06 and RTC-05 are unchanged).
- 2026-11-03: separation is direction-aware. `AUTH_n := NOT (OCC_n AND <next blocks of n>)`, with the
  next blocks from the layout's `next_blocks`, so a train is held only for the block ahead of it.
  Before, it was held for either neighbour, and a convoy of adjacent trains (Green 62, 63, 64) held
  each other for good. Where the layout joins two blocks both ways (Green 13..28 and 77..85) the
  program cannot tell the direction, so each block still holds for the other there. All 11
  fingerprints regenerated.
- 2026-11-03: the CTC-command wrapper in the switch rule now parenthesises the starter's own
  expression: `(CTCSW AND CTCREV) OR (NOT CTCSW AND (own))`. Without the brackets the second half of
  `own` applied even while the CTC was commanding. Fingerprints of the 8 waysides with switches
  regenerated.
- 2026-10-30: the starter reads the CTC Office's switch command (`CTCSW_s`, `CTCREV_s`) and obeys it
  first, whatever else it would do; the vital code no longer applies the command itself. Every
  wayside with a switch has new fingerprints (GTC-05, GTC-06 and RTC-05 have no switch and are
  unchanged).
- 2026-10-30: neighbours in the starter (signal look-ahead, crossing approach, separation) follow the
  layout, not block numbers. Fingerprints regenerated.
- 2026-10-21: `234c353`, the original one-line switch rule replaced by `_switch_rule`.
- 2026-10-20: `3b0e170`, the original starter (on `development`).
