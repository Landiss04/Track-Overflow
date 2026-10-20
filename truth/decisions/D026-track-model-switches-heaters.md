# D026-track-model-switches-heaters

**Status:** current
**Owner:** Kevin
**Provenance:** relayed by Kevin Schillinger 2026-10-20 from the Track Controller answers
**Aliases:** track heaters, heaters, heater commands, heater control
**Last updated:** 2026-10-20

## Context

The system simulates track heaters that affect the track environment (SRS REQ-FUNC-022).
The Track Model ran its heaters only when commanded, while the Track Controller software
variant expected the Track Model to switch them itself, so nothing switched them.

## Decision

The Track Model switches the track heaters automatically. The Track Controller does not
command them.

## Consequences

- No heater command passes from the Track Controller to the Track Model.
- Open: the rule by which the Track Model switches the heaters is not stated here.
