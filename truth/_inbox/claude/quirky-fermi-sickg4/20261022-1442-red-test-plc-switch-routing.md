**Target:** truth/decisions/D039-red-test-plc-switch-routing.md
**Action:** create
**Proposed by:** Integration on claude/quirky-fermi-sickg4
**Provenance:** asserted by Kevin Schillinger 2026-10-22, choosing to reuse Braden's switch logic for the Red test PLC programs; supersedes Kevin Schillinger's earlier "wait for real" (2026-10-22) for Red switching.

Placed in `decisions/`, not in `modules/track-controller/track-controller-hw.md`.
The entry concerns the PLC programs a wayside runs. The programs are kept
separate from the controller's implementation, so they are not a fact about
the HW implementation alone. The entry also names the Red Line, and the line a
variant serves is variant selection (D021). AGENTS.md puts variant selection
in `decisions/` and keeps it out of contract and variant shards.

No proposal in this inbox, or elsewhere under `truth/_inbox/`, records "wait
for real" or says that the Red test programs do not route switches. The
`## Supersedes` section below names Kevin's earlier instruction directly.

---

# D039-red-test-plc-switch-routing

**Status:** current
**Owner:** Braden (Track Controller HW); contract owner Harry Tye
**Provenance:** asserted by Kevin Schillinger 2026-10-22, choosing to reuse Braden's switch logic for the Red test PLC programs; supersedes Kevin Schillinger's earlier "wait for real" (2026-10-22)
**Aliases:** Red switching, Red test PLC switch routing, red_wayside integration test programs, reuse Braden's switch logic
**Last updated:** 2026-10-22

## Context

The Red Line wayside PLC programs on the integration branch
(`TrackCtrlHw/data/plc/red_wayside_*_integration_test.plc`) are test copies.
They are not Braden's programs. Braden's Green programs
(`TrackCtrlHw/data/plc/green_wayside_1..3.plc`) already route their switches.

## Decision

The Red test programs route switches the same way as Braden's Green programs:

- While the CTC Office commands a switch (maintenance, `CTCSW_n`/`CTCREV_n`),
  the program obeys that command.
- Otherwise the program routes the switch automatically.
- While a train is on a switch's points, the program locks the switch in the
  position it reports.

## Consequences

- The Red test programs stay test copies. Braden, as owner, replaces or
  approves them.
- Every protection stays in the PLC program (proposed D019).

## Supersedes

- Kevin Schillinger's earlier "wait for real" (2026-10-22) for Red switching,
  under which the Red test programs did not route switches. Kevin replaced it
  on 2026-10-22 by choosing to reuse Braden's switch logic.
