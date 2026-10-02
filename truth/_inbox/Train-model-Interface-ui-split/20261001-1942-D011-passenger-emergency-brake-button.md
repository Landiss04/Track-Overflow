**Target:** truth/decisions/D011-passenger-emergency-brake-button.md
**Action:** create
**Proposed by:** Claude Code on Train-model-Interface-ui-split
**Provenance:** asserted by Kevin Schillinger 2026-10-01 in a Claude Code session: "when the emergency break is activated the emergency break button should be disabled. and the text should no longer change to release emergency break just keep it as apply emergency break"; and the button must update when the Train Controller commands the emergency brake (from the test UI)

---

# D011-passenger-emergency-brake-button

**Status:** current
**Owner:** Kevin Schillinger
**Provenance:** asserted by Kevin Schillinger 2026-10-01
**Aliases:** apply emergency brake button, overview emergency brake button, passenger brake button
**Last updated:** 2026-10-01

## Context

The Train Model UI's passenger emergency brake button turned into a release control
once pulled, although who releases a pull is open
(`arbitration/passenger-emergency-brake.md`), and it did not react when the Train
Controller commanded the emergency brake.

## Decision

- The button always reads "Apply emergency brake". It never offers a release.
- It is disabled while the emergency brake is activated, whatever activated it: a
  passenger pull or the Train Controller's emergency brake command.
- The Train Controllere releases the emegency break 
