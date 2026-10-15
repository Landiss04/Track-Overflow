**Target:** truth/arbitration/track-controller-vital-restrictions.md
**Action:** create
**Proposed by:** Claude Code on Track-Ctrl-SW
**Provenance:** asserted by the user in the Track Controller UI chat, 2026-10-14: remove the maintenance hold and the authority truncation from the vital layer. Supersedes the unpromoted proposal `20261008-1740-vital-restrictions.md`, which asserted both.

---

# track-controller-vital-restrictions

**Status:** current
**Owner:** Track Controller
**Provenance:** asserted by the user 2026-10-14 (Track Controller UI chat); implemented in `TrackCtrlSW/track_ctrl/vital.py`
**Aliases:** vital layer, vital supervisor, vital restrictions, fail-safe supervisor
**Last updated:** 2026-10-14

## Rule

Whatever a PLC program asks for, the Track Controller's vital layer can only make an
output more restrictive. It never raises a speed, extends an authority, clears a
crossing or turns a signal more permissive. Speed and authority are per block, and a
train gets the values of the block it is in.

The vital layer applies these restrictions:

- A block whose `AUTH` output is not set sends speed 0 and authority 0.
- A block the CTC Office closed sends speed 0 and authority 0
  ([block-closure](block-closure.md)).
- A block holding a switch that is not at its commanded position, or that reports a
  fault, sends speed 0 (and 0 authority for a fault).
- A speed above the block's posted limit is cut to the limit
  ([suggested-speed-under-block-limit](suggested-speed-under-block-limit.md)).
- A yellow signal halves its block's speed after the limit, rounded down to whole m/s.
- Zero authority means zero speed.
- A signal showing no aspect, or more than one, is red. A signal on an occupied or
  closed block is red.
- A switch on an occupied block does not move
  ([no-switch-under-train](no-switch-under-train.md)).
- A crossing with a train on its approach is active.
- A Track Controller that is not ready, or whose scan fails, drives its fail-safe
  outputs: [track-controller-ready](../signals/track-controller-ready.md).

In maintenance mode a switch follows the CTC Office's command if it has sent one for
that switch, else the programmer's hand-set position, else the program. That is all
maintenance mode changes.

## Does not

- **Count blocks ahead.** The Track Controller does not know the route or the
  direction of travel, so it does not shorten an authority at an occupied or closed
  block. Stopping authority before an obstruction is the CTC Office's
  ([authority-stops-before-obstruction](authority-stops-before-obstruction.md)).
- **Hold authority in maintenance mode.** Speed and authority are unchanged.

## Notes

- The CTC Office owner and the HW Track Controller owner have not confirmed the
  precedence of the CTC's switch command over a hand-set switch.

## Supersedes

- The unpromoted proposal `20261008-1740-vital-restrictions.md` (same author, same
  branch) recorded two restrictions that are withdrawn: counting authority to the
  first occupied or closed block ahead, and holding authority at zero in maintenance
  mode. The user withdrew both on 2026-10-14. Withdrawn by this proposal, not edited:
  only a human edits or deletes an existing proposal.
