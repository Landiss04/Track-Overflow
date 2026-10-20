**Target:** truth/signals/passengers-boarded.md
**Action:** replace
**Proposed by:** Codex on claude/quirky-fermi-sickg4
**Provenance:** Kevin Schillinger’s October 20, 2026 SDD review; documents/Railway_Sim_SDD_Train_Model.md v0.2 §4.9; direct documentation request 2026-10-20

---

# passengers-boarded

**Status:** current
**Owner:** Track Model
**Provenance:** Kevin Schillinger’s October 20, 2026 SDD review; documents/Railway_Sim_SDD_Train_Model.md v0.2 §4.9; direct documentation request 2026-10-20
**Aliases:** Passengers Boarded, boarding count
**Last updated:** 2026-10-20

## Definition

An integer boarding-event count sent by the Track Model to the Train Model.
The Track Model sends boarding events only at stations; zero means no event.

## Responsibilities

- The Track Model owns the station restriction and sends each event once, with a
  count no greater than the last reported [passenger-capacity](passenger-capacity.md).
- The Train Model validates an actual integer (not a boolean) in 0 through 2³¹ − 1,
  checks rest and an open door, and caps accepted boarding at remaining capacity.
  It does not apply a station-presence gate or require station metadata for boarding.
- An event received while moving or with both doors closed boards nobody and is not
  retained by the model. Operating mass follows the accepted passenger count.
- Door interlock ownership is separate: the Train Controller commands the doors;
  the Train Model follows those commands.

## Supersedes

- Previously left the station gate and at-rest enforcement owner unsettled; Kevin’s review assigns station eligibility to Track Model and rest/doors/count/capacity checks to Train Model.
