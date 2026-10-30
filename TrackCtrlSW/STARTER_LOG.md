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
| Inputs it reads | `OCC`, `CLOSED`, `MAINT` | the same, plus, when the wayside has a switch, `SWREV_s` (the read-back) and `CTCSW_s`, `CTCREV_s` (the CTC Office's command, obeyed first) |
| Signals, crossings | `AHEAD` = blocks `point+1`, `point+2`; crossing = its block and `number ± 1` | **Not the same code any more:** since 2026-10-30 these and the separation rule use the layout's physical neighbours (`config.neighbours`, `config.within`), not block numbers. Block 101 joins block 77. |
| Separation | `AUTH_n := NOT neighbour` for neighbours `n ± 1`, so an empty block beside a train is held | `AUTH_n := NOT (OCC_n AND neighbour)`: only a block with a train in it is held. An empty block passes the CTC Office's preloaded suggestion. Neighbours come from the layout. |

The original starter's separation and neighbour rules were already replaced on this branch before
today; the switch rule is the one most at risk in a merge.

## Fingerprints of the current starter

SHA-256 (first 12 hex digits) of the generated starter source for the default Green and Red
layouts, as of branch commit `e5e51d4` plus the uncommitted work on 2026-10-30 (the neighbour and CTC-command
changes included). Regenerate and update this table whenever the starter is changed on purpose.

| Wayside | Fingerprint | Lines | Switches |
|---|---|---|---|
| GTC-01 | 5df41fe67971 | 60 | 12 |
| GTC-02 | d5f67e9af784 | 56 | 28 |
| GTC-03 | 19df36ed3a76 | 73 | 58, 62 |
| GTC-04 | a5df0b60c2ca | 73 | 76, 85 |
| GTC-05 | 4facfa4cbfe0 | 40 | none |
| GTC-06 | 578c45905306 | 36 | none |
| RTC-01 | f12a22eb164f | 69 | 9, 15 |
| RTC-02 | 392b6b05a776 | 47 | 27 |
| RTC-03 | c64bf40ba58f | 83 | 32, 38, 43 |
| RTC-04 | 3543c23b9713 | 51 | 52 |
| RTC-05 | f88f0e81ba95 | 26 | none |

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

- 2026-10-30: the starter reads the CTC Office's switch command (`CTCSW_s`, `CTCREV_s`) and obeys it
  first, whatever else it would do; the vital code no longer applies the command itself. Every
  wayside with a switch has new fingerprints (GTC-05, GTC-06 and RTC-05 have no switch and are
  unchanged).
- 2026-10-30: neighbours in the starter (signal look-ahead, crossing approach, separation) follow the
  layout, not block numbers. Fingerprints regenerated.
- 2026-10-21: `234c353`, the original one-line switch rule replaced by `_switch_rule`.
- 2026-10-20: `3b0e170`, the original starter (on `development`).
