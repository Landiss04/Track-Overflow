**Target:** truth/signals/signal-aspect-ahead.md
**Action:** create
**Proposed by:** Claude on claude/quirky-fermi-sickg4
**Provenance:** asserted by Kevin Schillinger 2026-10-16 in the team's review of `documents/system-integration-design.md` (G-SIG-10): the driver can see the light through the windshield, so "make sure that the driver is able to see next light state"; and 2026-10-17: "It is sent from the track model to the train controller directly. and it is spelled SUPER_GREEN". The pending `feature/TrackCtrl-Module-Implementation/20261007-0110-signal-light-command.md` mentions a pending `signal-aspect` that was never filed; that name is listed as an alias here so the two cannot diverge unnoticed.

---

# signal-aspect-ahead

**Status:** current
**Owner:** Track Model
**Provenance:** asserted by Kevin Schillinger 2026-10-16 (the driver sees the next light) and 2026-10-17 (sent from the Track Model to the Train Controller directly; spelled `SUPER_GREEN`)
**Aliases:** next light state, next light, light ahead, signal light ahead, `signal_light_ahead`, signal-aspect, next signal aspect
**Last updated:** 2026-10-17

## Definition

The state of the next signal light ahead of a train, sent from the Track Model to that
train's Train Controller. It goes to the Train Controller directly, not through the
Train Model. It stands for what the driver sees through the windshield.

## Notes

- The values are all caps. The fourth aspect is spelled `SUPER_GREEN`.
- Open: the full set of aspect names. The pending `signal-light-command` proposal
  records a conflict over the second aspect, YELLOW or ORANGE, with Braden as its
  resolution owner.
