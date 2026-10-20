**Target:** truth/signals/signal-aspect-ahead.md
**Action:** create
**Proposed by:** Claude on claude/quirky-fermi-sickg4
**Provenance:** as `20261017-1433-signal-aspect-ahead.md` on this branch, which this proposal supersedes (deny that one), plus the Track Controller answers relayed by Kevin Schillinger 2026-10-20: "Will change orange to yellow". That settles the second aspect, the YELLOW-or-ORANGE conflict in the pending `feature/TrackCtrl-Module-Implementation/20261007-0110-signal-light-command.md`.

---

# signal-aspect-ahead

**Status:** current
**Owner:** Track Model
**Provenance:** asserted by Kevin Schillinger 2026-10-16 (the driver sees the next light) and 2026-10-17 (sent from the Track Model to the Train Controller directly; spelled `SUPER_GREEN`); YELLOW, not ORANGE, for the second aspect, relayed by Kevin Schillinger 2026-10-20 from the Track Controller answers
**Aliases:** next light state, next light, light ahead, signal light ahead, `signal_light_ahead`, signal-aspect, next signal aspect
**Last updated:** 2026-10-20

## Definition

The state of the next signal light ahead of a train, sent from the Track Model to that
train's Train Controller. It goes to the Train Controller directly, not through the
Train Model. It stands for what the driver sees through the windshield.

## Notes

- One of `RED`, `YELLOW`, `GREEN` and `SUPER_GREEN`, all caps.
