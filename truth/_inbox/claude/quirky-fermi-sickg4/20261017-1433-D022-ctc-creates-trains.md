**Target:** truth/decisions/D022-yard-black-box.md
**Action:** create
**Proposed by:** Claude on claude/quirky-fermi-sickg4
**Provenance:** as `20261016-2254-D022-yard-black-box.md` on this branch, which this proposal supersedes (deny that one), plus Kevin Schillinger 2026-10-17, answering how a train pulled from the yard comes to exist: "ctc creates the train".

---

# D022-yard-black-box

**Status:** current
**Owner:** Kevin
**Provenance:** asserted by Kevin Schillinger 2026-10-16; the CTC Office creating the trains asserted by Kevin Schillinger 2026-10-17
**Aliases:** yard, train yard, yard black box, dispatch from the yard, train creation, spawn
**Last updated:** 2026-10-17

## Context

Each line's layout joins the yard (`next_blocks` lists `"yard"`, per
`conventions/files-and-paths.md`). No entry said what the yard is or who moves trains
into and out of it.

## Decision

- The yard is a black box with unlimited capacity.
- The CTC Office pulls trains from the yard and sends them back into the yard.
- The CTC Office creates each train it pulls from the yard.

## Consequences

- Open: the signal that carries a new train from the CTC Office to the Train Model
  and the Train Controller, and a train's return to the yard, is not defined.
