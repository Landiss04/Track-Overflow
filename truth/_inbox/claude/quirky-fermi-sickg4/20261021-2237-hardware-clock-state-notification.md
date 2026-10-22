**Target:** truth/decisions/D031-hardware-clock-state-notification.md
**Action:** create
**Proposed by:** Integration on claude/quirky-fermi-sickg4
**Provenance:** asserted by Kevin Schillinger 2026-10-22: "yes" to approval of the prepared CLOCK_STATE exception.

---

# D031-hardware-clock-state-notification

**Status:** current
**Owner:** Kevin
**Provenance:** asserted by Kevin Schillinger 2026-10-22: "yes" to approval of the prepared CLOCK_STATE exception.
**Aliases:** CLOCK_STATE, hardware clock metadata, loss while running
**Last updated:** 2026-10-22

## Decision

The central harness sends authoritative clock pause/speed metadata to
the two HW host processes on their existing module channels, initially
and when the state changes. `CLOCK_STATE` is the approved additive
exception to the Phase 5 instruction to leave the harness core and
module protocol unchanged. Other module behavior is unchanged.

The metadata does not advance a core, apply gains or change any window.
A HW host latches the actual clock state when it loses its Pi link,
before the harness's late-reply timeout can pause the clock. The Train
Controller relay uses that loss-time state for K11: resend the engineer's
gains after a running loss, and do not automatically apply them after a
paused loss. A pause between STEP messages must be visible to that host;
last-tick timing is not a substitute for authoritative clock state.

This addition is on the harness-to-HW-host channel. HELLO/ACTION/ACK/VIEW
remain the separate host-to-Pi additions of D030/D027.
