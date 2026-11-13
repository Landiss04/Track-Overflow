**Target:** truth/arbitration/pi-link-recovery.md
**Action:** create
**Proposed by:** Integration on claude/quirky-fermi-sickg4
**Provenance:** Kevin Schillinger's Phase 5 decisions relayed in the session prompt, 2026-10-21. K7: "approved" to hold/reconnect/HELLO/load replay/pending STEP; K8: "the whole clock should wait this will never happen".

---

# pi-link-recovery

**Status:** current
**Owner:** Kevin
**Provenance:** asserted by Kevin Schillinger 2026-10-21; K7: "approved" to hold/reconnect/HELLO/load replay/pending STEP; K8: "the whole clock should wait this will never happen"
**Aliases:** USB unplug, Pi reboot, repeated STEP, replay
**Last updated:** 2026-10-21

## Rule

On unplug or reboot, the host holds the outstanding STEP reply. The
harness pauses and names the late module after about one second (D017).
There is no automatic fallback to a local core or simulated Pi. A Pi
missing at launch also holds the whole clock. Simulation is selected
explicitly for tests and development only.

The host reconnects by USB identity, repeats HELLO, replays recorded
loads and re-sends the pending STEP, logging each recovery stage. The Pi
answers a repeated STEP from its session's cache keyed by `(id, tick)`;
it never advances the same STEP twice. A restart must preserve or rebuild
that accepted state before answering the pending STEP.
