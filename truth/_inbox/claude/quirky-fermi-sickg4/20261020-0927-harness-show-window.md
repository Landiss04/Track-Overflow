**Target:** truth/decisions/harness-show-window.md
**Action:** create
**Proposed by:** Codex on claude/quirky-fermi-sickg4
**Provenance:** asserted by Kevin Schillinger 2026-10-20 in the
harness window implementation questions.

---

# harness-show-window

**Status:** current
**Owner:** Kevin Schillinger
**Provenance:** asserted by Kevin Schillinger 2026-10-20
**Aliases:** SHOW, showRequested, reopen module window
**Last updated:** 2026-10-20

## Decision

The harness provides a Show window action per module. It sends a SHOW
message to that module over the existing local protocol. SHOW is
additive and does not bump the protocol version. It carries the usual
integer id and tick, requires no reply, and does not step the module.
ModuleLink emits showRequested on receipt. Stubs ignore SHOW.
A module with a window connects showRequested to reopening its window.

