# brake-state

**Status:** current
**Owner:** Train Model
**Provenance:** `Train_Model_Backend_Design.pdf` §5.8 (Locked) and Interfaces table, supplied by Kevin Schillinger 2026-09-30; `bool[2]` shape and state-not-command semantics asserted by Kevin Schillinger 2026-09-30; brake failure disabling both brakes asserted by Kevin Schillinger 2026-09-30
**Aliases:** Brake State, Emergency Brake State, e-brake state, emergency brake active, service brake state
**Last updated:** 2026-09-30

## Definition

Two booleans, `bool[2]`, sent from the Train Model to the Train Controller. Element 0 is
the emergency brake and element 1 is the service brake. Each reports whether that brake
is actually engaged. It does not echo the brake command.

## Notes

- The emergency brake element is true whether the brake was engaged by the Train
  Controller's Emergency Brake Command or by a passenger pull in the Train Model UI. For
  who owns the passenger pull, see `arbitration/passenger-emergency-brake.md`.
- Brake failure disables both brakes, so while the brakes have failed both elements
  are false even when a brake is commanded or a passenger has pulled the emergency
  brake. See `signals/failure-status.md`.
- The source does not say whether the service element is true while the emergency
  brake is also engaged.
