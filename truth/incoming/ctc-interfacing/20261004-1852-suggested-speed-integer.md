**Target:** truth/signals/suggested-speed.md
**Action:** replace
**Proposed by:** Claude on ctc-interfacing
**Provenance:** asserted by Landis 2026-10-02 (CTC architecture diagram, `ctc-architecture.html`); integer type asserted by Landis 2026-10-04

---

# suggested-speed

**Status:** current
**Owner:** CTC Office
**Provenance:** asserted by Landis 2026-10-02 (CTC architecture diagram, `ctc-architecture.html`); integer type asserted by Landis 2026-10-04
**Aliases:** Suggested Speed, CTC suggested speed
**Last updated:** 2026-10-04

## Definition

The speed the CTC Office suggests for one train, sent to the Track Controller as an
integer in m/s. One value per train, keyed by train ID.

It is not the train's actual speed: it is the speed the CTC Office suggests the train
run at to keep a safe operating distance from other trains.

## Notes

- Distinct from the commanded speed in [track-signal](track-signal.md), which the Track Model sends to the Train Model.
- The unit is m/s per `conventions/units.md`; UIs show it in mph.
- The Track Controller owner has not confirmed it.

## Supersedes

- Type: previously a float in m/s (chosen over the diagram's int on 2026-10-02); now an integer, asserted by Landis 2026-10-04.
