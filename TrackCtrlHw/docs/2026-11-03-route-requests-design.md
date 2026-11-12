# Route requests for the Red passing sidings — design

Date: 2026-11-03 · Owner: Braden (Track Controller HW) · Status: draft
for approval · Branch: `feature/TrackCtrl-HW-route-requests` (from
`79f383b`)

Source: Landis's request "Red line passing sidings: Track Controller
request", 2026-11-03.

## Intent

Red trains can only pass each other between 27 and 44 if a train can
be routed *into* a siding (72–76 beside 28–32, 67–71 beside 39–43). Today
the Red-2 program reverses switches 27, 32, 38 and 43 only for a train
already standing in a siding, or when the main leg is closed. The CTC
Office now outputs `route_requests`: the position each switch should
take for the train routed over it. The Track Controller HW should let a
request choose the leg, without weakening any protection.

## Goals

- The HW wayside reads the CTC's route requests and gives each switch
  two PLC inputs, `REQSW_s` and `REQREV_s`, alongside `CTCSW_s` and
  `CTCREV_s`.
- The Red-2 program follows a request at switches 27, 32, 38 and 43,
  and keeps today's rule when there is none.
- The test UI can drive route requests, as it drives switch commands.

## Non-goals

- The harness mapping from the CTC to the HW Track Controller
  (`common/harness/hw_wayside_edges.py`): Kevin's (Landis's open
  question 1). Not on this branch unless Kevin agrees.
- Turning on `PASSING_SIDINGS` in the CTC: Landis's.
- The Track Controller SW: Harry's call (Green has no sidings).
- Red-1 and Red-3 programs: no sidings there; they ignore the inputs.

## Anti-goals

- A request must never move a switch the program would refuse: not into
  a closed leg, not under a train, not against a maintenance command.
- The vital block must not change. It only restricts.

## Approaches

| | Approach | Verdict |
|---|---|---|
| **A** | New PLC inputs `REQSW_s` / `REQREV_s`; the program decides | **Chosen** (Braden, 2026-11-03) |
| B | Merge requests into `CTCSW_s` / `CTCREV_s` on the host | Rejected: a request becomes a command; the vital block forces commands, so it would move a switch into a closed or occupied leg; signals would show caution; maintenance precedence is lost |
| C | Vital block or Python host picks the leg | Rejected: routing outside the PLC; the vital block only restricts, the OS only houses the PLC |

## Design

### Signal (CTC Office → Track Controller HW)

`route_requests`: entries `{line, switch_id, position}`, `position`
`normal` or `reverse`, the same shape as `switch_commands`. A switch is
listed only while a train is routed over it. Proposed signal name
(Landis): `switch-route-request`.

### HW Track Controller plumbing

- `interface.py`: `CtcInputs.route_requests: Mapping[BlockRef,
  SwitchPosition]`, default empty, like `switch_commands`.
- `controller.py`: validated like `switch_commands` (known switch,
  `normal` / `reverse` only).
- `wire.py`: `ctc.route_requests` both ways, entry shape as
  `switch_commands`. Missing field = no requests (older senders still
  work).
- `wayside.py`: for every switch, `REQSW_s` (a request exists) and
  `REQREV_s` (it is reverse; 0 with no request) join `input_names` and
  the input image. The PLC-names table in the module docstring gains
  both rows.
- Test UI (`harness.py`, `TestView.qml`): a per-switch route request
  selector (none / normal / reverse) beside the switch command, sent
  over the test link. Test UI, link and wire change in the same commit.
- `vital.py`: unchanged. It already passes the program's `SW_s` when
  there is no CTC command, locks a switch under a train on its point or
  listed block, and forces maintenance commands.

### Red-2 program (`red_wayside_2_integration_test.plc`)

Declare `REQSW_s REQREV_s` for 27, 32, 38, 43. Replace each `AUTO_s`:

| Switch | Normal leg | Reverse leg |
|---|---|---|
| 27 | 28 | 76 |
| 32 | 32 | 72 |
| 38 | 39 | 71 |
| 43 | 43 | 67 |

```
REQ_R_s := REQSW_s AND REQREV_s AND NOT CLOSED_<reverse>
REQ_N_s := REQSW_s AND NOT REQREV_s AND NOT CLOSED_<normal>
AUTO_s  := REQ_R_s OR (NOT REQ_N_s AND NOT REQ_R_s
           AND <today's AUTO_s>)
```

`WANT_s`, `LOCK_s`, `BAD_s`, `BLOCKED_s`, `CAUTION_s` and the signals
stay as they are.

### Precedence (highest first)

1. A train on the points or listed block: the switch stays where it
   reports (`LOCK_s`, and the vital block).
2. The dispatcher's maintenance command (`CTCSW_s`): wins over a
   request (`WANT_s`, and the vital block).
3. A route request whose leg is open.
4. Today's rule.

## Tests

Unit, all on the PLC through the controller (no hardware):

1. Request reverse on 27 with no train: `SW_27` reverse; request
   removed: normal again. Same for 32, 38, 43.
2. Request reverse with 76 closed: no move. With a train on 27: no move.
3. Maintenance command normal while reverse is requested: normal.
4. No request: today's behaviour unchanged (existing Red tests pass).
5. The vital block with a permissive program still locks and still
   obeys maintenance commands with requests present.
6. Wire round trip of `route_requests`; missing field = empty.

Bench: the same through the test UI against the real Pi (bundle
reinstalled; `track_ctrl_hw` runs on the Pi).

End to end (after the harness carries the field): CTC in Manual,
dispatch a Red train to 74; switch 27 reverses ahead of it; it stops at
74.

## Calls made (Braden to check)

- `CAUTION_s` does not count requests. A reverse request shows caution
  through `SWREV_s` once the switch moves, and `BAD_s` holds red before
  that; a normal request on the main line should not show yellow.
- Every switch on every HW wayside gets the two inputs, so a program
  can opt in; only Red-2 reads them.

## Open, for others

- Kevin: the harness edge (`ctc_edges.py` → `hw_wayside_edges.py`),
  as `switch_commands` does. Until then only the bench test runs.
- Landis: with a request into a closed leg, the program falls back to
  today's rule and may take the *other* leg. Safe only if the CTC never
  routes a train into a closed block — please confirm.
- Harry: whether the SW programs read the same inputs, for parity.
- Truth: Landis owns the `switch-route-request` signal entry (CTC
  Office is the producer).
