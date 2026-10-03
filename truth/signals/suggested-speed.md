# suggested-speed

**Status:** current
**Owner:** CTC Office
**Provenance:** asserted by Landis 2026-10-02 (CTC architecture diagram, `ctc-architecture.html`); types per `conventions/identifiers.md` and `conventions/units.md`, chosen by Landis 2026-10-02 over the diagram's int types
**Aliases:** Suggested Speed, CTC suggested speed
**Last updated:** 2026-10-02

## Definition

The speed in m/s the CTC Office suggests for one train, sent to the Track Controller. One value per train, keyed by train ID.

## Notes

- Distinct from the commanded speed in [track-signal](track-signal.md), which the Track Model sends to the Train Model.
- The diagram typed it as an int; it is a float in m/s per `conventions/units.md`.
- The Track Controller owner has not confirmed it.
