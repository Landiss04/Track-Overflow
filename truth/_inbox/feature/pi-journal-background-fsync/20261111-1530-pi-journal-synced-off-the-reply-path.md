**Target:** truth/decisions/D042-pi-journal-synced-off-the-reply-path.md
**Action:** create
**Proposed by:** GitHub Copilot on feature/pi-journal-background-fsync
**Provenance:** asserted by Braden Bosilovich 2026-11-11 (Kevin Schillinger stated no preference and left the choice to Braden, who delegated it); measurements on the Track Controller Pi 2026-11-08 and 2026-11-11

---

# D042-pi-journal-synced-off-the-reply-path

**Status:** current
**Owner:** Kevin
**Provenance:** asserted by Braden Bosilovich 2026-11-11, with Kevin Schillinger's agreement to leave the choice to him
**Aliases:** Pi journal, agent journal, durable journal, journal fsync, session.json, K7 durability
**Last updated:** 2026-11-11

## Context

Each Pi agent journals every request and reply so that it can rebuild its exact
state after an unplug or reboot (K7). The journal was fsynced before every reply.
On the Track Controller Pi's SD card one fsync takes about 10 ms whatever the
record size, as long as the Pi's whole 10x tick budget, and it held the real Pi
to about 4x. In this setup the USB cable also powers the Pi, so an unplug is a
power cut: dropping the fsync altogether would let a Pi come back behind the host
without either side knowing.

## Decision

- A Pi agent writes each journal record before it replies, and fsyncs the journal
  on a separate thread. The reply does not wait for the disk.
- Every reply names the last request whose record is on disk. On HELLO the agent
  names the last request it has applied.
- The host keeps every answered request until the Pi reports it on disk. After a
  resumed HELLO it resends, in order, exactly those it holds after the request the
  Pi says it applied; a replaced Pi gets its configuration as before.
- At most 50 records may be written but not yet on disk; beyond that a reply waits
  for the disk.
- On restart the agent keeps the journal up to its first torn or malformed record.

## Consequences

- K7 is unchanged: a power cut loses no request the host saw answered, and no
  request is applied twice. The Pi's core must stay deterministic, since a resent
  request is executed again.
- A host-run (simulated) agent still never fsyncs.
- A checkpoint waits for the fsync thread to go idle before it replaces the journal.
