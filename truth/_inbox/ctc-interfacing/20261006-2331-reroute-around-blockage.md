**Target:** truth/arbitration/reroute-around-blockage.md
**Action:** create
**Proposed by:** Claude on ctc-interfacing
**Provenance:** asserted by Landis 2026-10-06 (a train whose route is blocked should be rerouted); which trains count as not moving, and the twice-as-long limit, proposed by Claude on ctc-interfacing 2026-10-06 for Landis to confirm

---

# reroute-around-blockage

**Status:** current
**Owner:** Landis
**Provenance:** asserted by Landis 2026-10-06 (a train whose route is blocked should be rerouted); which trains count as not moving, and the twice-as-long limit, proposed by Claude on ctc-interfacing 2026-10-06 for Landis to confirm
**Aliases:** rerouting, detour, route around failure, route around stopped train
**Last updated:** 2026-10-06

## Definition

The CTC Office routes a train around what would hold it up for good, when a reasonable
way round exists:

- closed, closing and failed blocks;
- trains that are not going to move: a train with no order, a train that had no
  authority at the last step (at its destination, or held up itself), and an occupied
  block with no train reported in it.

It does not route around a train that is moving; it follows it.

It prefers a route around both, then a route around the unusable blocks only, then the
shortest route, on which the train waits. A way round more than twice as long as the
shortest route is not taken: the train waits instead.

## Notes

- Routes keep the direction of travel and never turn back, so some blockages have no
  way round. See [no-automatic-reversal](no-automatic-reversal.md).
- Exclusive authority still applies on the new route:
  [exclusive-authority](exclusive-authority.md).
