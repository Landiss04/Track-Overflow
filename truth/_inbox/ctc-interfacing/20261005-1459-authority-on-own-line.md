**Target:** truth/arbitration/authority-on-own-line.md
**Action:** create
**Proposed by:** Claude on ctc-interfacing
**Provenance:** asserted by Landis 2026-10-05 (safety rules for the CTC Office, answered during the CTC bug review)

---

# authority-on-own-line

**Status:** current
**Owner:** Landis
**Provenance:** asserted by Landis 2026-10-05 (safety rules for the CTC Office, answered during the CTC bug review)
**Aliases:** cross-line dispatch, wrong-line authority
**Last updated:** 2026-10-05

## Definition

The CTC Office never dispatches a train to a block on a different line than the line the
train is reported on: a train on the Green line can be sent only to Green line blocks.
Such a dispatch is refused.

## Notes

- A train not reported on any line yet (for example a new train) may be dispatched to
  either line.
