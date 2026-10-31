**Target:** truth/arbitration/pi-link-recovery.md
**Action:** create
**Proposed by:** Integration on claude/quirky-fermi-sickg4
**Provenance:** Kevin Schillinger's Pi-link performance plan in the session prompt, 2026-10-30, approved for commit 2026-10-31. Item 1: "Every N ticks (proposed: 600 ...) the agent saves its whole core with `pickle`"; "On a mismatch the agent ignores the checkpoint and starts fresh, the same as a wiped Pi." Item 3: "A replaced Pi starts again from those loads. It loses runtime state". Replaces the unpromoted proposal 20261021-1808-pi-link-recovery.md on this branch.

---

# pi-link-recovery

**Status:** current
**Owner:** Kevin
**Provenance:** asserted by Kevin Schillinger 2026-10-21 (K7: "approved" to hold/reconnect/HELLO/load replay/pending STEP; K8: "the whole clock should wait this will never happen"); amended by Kevin Schillinger 2026-10-30 (Pi-link performance plan: agent checkpoint every 600 ticks, bundle-hash mismatch starts fresh, a replaced Pi restarts from its loads only)
**Aliases:** USB unplug, Pi reboot, repeated STEP, replay, checkpoint, replaced Pi, wiped Pi
**Last updated:** 2026-10-31

## Rule

On unplug or reboot, the host holds the outstanding STEP reply. The
harness pauses and names the late module after about one second (D017).
There is no automatic fallback to a local core or simulated Pi. A Pi
missing at launch also holds the whole clock. Simulation is selected
explicitly for tests and development only.

The host reconnects by USB identity, repeats HELLO, replays the recorded
territory and program loads and re-sends the pending STEP, logging each
recovery stage. The Pi answers a repeated STEP from its session's cache
keyed by `(id, tick)`; it never advances the same STEP twice. The cache
keeps every ACTION reply and only the latest STEP reply.

A restarted Pi rebuilds its accepted state before answering the pending
STEP. Every 600 ticks the agent saves its core and cache to its own disk
with `pickle` and starts a new journal headed by that checkpoint, so a
restart re-runs at most 600 ticks. A checkpoint is read only from the
agent's own disk; nothing pickled crosses USB. The journal header records
the agent bundle hash. On a mismatch the agent ignores the checkpoint and
starts fresh, the same as a wiped Pi.

A replaced or wiped Pi starts again from the replayed loads only. It
loses runtime state: locks, channel faults, train integrals and armed
gains. The existing gain-recovery path asks the engineer for gains when
needed.

## Supersedes

- 2026-10-21 value (unpromoted proposal 20261021-1808): the host replayed every recorded STEP and action, so a replaced Pi rebuilt its runtime state; changed because recovery time, memory and disk grew with run length.
