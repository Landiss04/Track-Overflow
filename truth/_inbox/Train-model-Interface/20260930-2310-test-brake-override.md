**Target:** truth/decisions/passenger-emergency-brake-release.md
**Action:** create
**Proposed by:** Codex on Train-model-Interface
**Provenance:** Kevin Schillinger corrected Codex in this chat on 2026-09-30: the test UI must toggle the emergency brake, while the regular UI stays unchanged because release there remains an open question.

---

# passenger-emergency-brake-release

**Status:** current
**Owner:** Kevin Schillinger
**Provenance:** asserted by Kevin Schillinger 2026-09-30 in the correction to the emergency-brake UI fix
**Aliases:** passenger brake release, overview emergency-brake release, test emergency-brake override
**Last updated:** 2026-09-30

## Decision

The test UI must support toggling the emergency brake even when a passenger
request is latched. This is a testing override, not a normal control action.
Keep the regular overview UI unchanged: whether normal users can release
the passenger emergency brake remains an open question.

