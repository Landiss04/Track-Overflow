**Target:** truth/arbitration/train-gains-reconnect.md
**Action:** create
**Proposed by:** Integration on claude/quirky-fermi-sickg4
**Provenance:** Kevin Schillinger's Phase 5 decisions relayed in the session prompt, 2026-10-21. K11: "they should never loose connection mid run but add logic to check if connections are lost while the clock as running and if they are lost while the clock is running then the gains should be resent".

---

# train-gains-reconnect

**Status:** current
**Owner:** Train Controller
**Provenance:** asserted by Kevin Schillinger 2026-10-21; K11: "they should never loose connection mid run but add logic to check if connections are lost while the clock as running and if they are lost while the clock is running then the gains should be resent"
**Aliases:** gains after reboot, lost Pi connection, commissioning replay
**Last updated:** 2026-10-21

## Rule

Detect the loss of a Train Controller Pi connection. If the connection
was lost while the shared simulation clock was running, re-send the
engineer's previously entered gains when it reconnects. If it was lost
while paused, do not automatically apply gains. Log both cases.

This is replay of engineer-entered gains, not automatic commissioning
with defaults. Every new train still waits for an engineer to set gains
(D024). No particular clock-state transport mechanism is decided here.
