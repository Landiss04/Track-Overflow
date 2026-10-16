**Target:** truth/arbitration/no-scheduled-head-on-meets.md
**Action:** create
**Proposed by:** Claude on ctc-deployment
**Provenance:** asserted by Landis 2026-10-15 (the CTC Office must not schedule trains to meet head-on; a head-on meet that happens anyway is the Track Controller's to handle)

---

# no-scheduled-head-on-meets

**Status:** current
**Owner:** Landis
**Provenance:** asserted by Landis 2026-10-15 (the CTC Office must not schedule trains to meet head-on; a head-on meet that happens anyway is the Track Controller's to handle)
**Aliases:** head-on meets, opposing trains, no head-on scheduling, meet avoidance
**Last updated:** 2026-10-15

## Definition

The CTC Office's automatic dispatch never sends trains so that they would meet head-on:
two trains running toward each other over the same track. Where scheduled runs use the
same track in both directions, the CTC Office holds a train back, at its last stop or in
the yard, until no train is coming the other way.

If trains do come to meet head-on anyway, the wayside controllers (the Track
Controller) handle it, not the CTC Office.

## Notes

- This is about how the CTC Office schedules. It does not replace the Track
  Controller's own safety logic, and the CTC Office still gives no two trains
  authority into the same block ([exclusive-authority](exclusive-authority.md)).
- The CTC Office never reverses a train to get it out of a meet
  ([no-automatic-reversal](no-automatic-reversal.md)).
- Applies to the runs the CTC Office dispatches automatically
  (`decisions/D020-automatic-dispatch-from-schedule`, proposed on `ctc-deployment`).
