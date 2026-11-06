**Target:** truth/signals/signal-aspect-ahead.md
**Action:** replace
**Proposed by:** Claude on claude/quirky-fermi-sickg4
**Provenance:** Track Model owner (SeeingEyeTree), answers to `documents/module-owner-review.md`, commit `c92f58f`, 2026-10-26, TM-2; signal placement relayed by Braden Bosilovich 2026-10-26 from the professor

---

# signal-aspect-ahead

**Status:** current
**Owner:** Track Model
**Provenance:** asserted by Kevin Schillinger 2026-10-16 (the driver sees the next light) and 2026-10-17 (sent from the Track Model to the Train Controller directly; spelled `SUPER_GREEN`); YELLOW, not ORANGE, for the second aspect, relayed by Kevin Schillinger 2026-10-20 from the Track Controller answers; sent every tick, the light facing the direction of travel, by the Track Model owner (SeeingEyeTree), answers to `documents/module-owner-review.md`, commit `c92f58f`, 2026-10-26 (TM-2)
**Aliases:** next light state, next light, light ahead, signal light ahead, `signal_light_ahead`, signal-aspect, next signal aspect, B1
**Last updated:** 2026-10-27

## Definition

The state of the next signal light ahead of a train, sent from the Track Model to that
train's Train Controller. It goes to the Train Controller directly, not through the
Train Model. It stands for what the driver sees through the windshield.

The Track Model sends it every tick, not only on the tick the train enters a block, and
it is the light that faces the train's direction of travel: a Green train going from 63
to 64 gets the light guarding 63→64, not the one for the opposite direction.

## Notes

- One of `RED`, `YELLOW`, `GREEN` and `SUPER_GREEN`, all caps.
- Signals sit only at switches, one per switch
  ([signals-at-switches](../decisions/signals-at-switches.md), proposed).

## Supersedes

- Timing: previously a train saw the colour once on entering a block; now every tick
  (Track Model owner 2026-10-26, defect B1).
