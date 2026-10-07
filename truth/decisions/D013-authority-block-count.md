# D013-authority-block-count

**Status:** current
**Owner:** Landis
**Provenance:** team decision including Kevin, asserted by Landis 2026-10-06
**Aliases:** authority as block count, blocks remaining, authority count
**Last updated:** 2026-10-06

## Context

Authority was a block ID (Kevin 2026-09-30): the string ID of the destination block up
to which a train may travel. Every module that handles authority then had to carry and
compare block ID strings, and block numbers repeat across lines. The team judged a count
easier to work with than strings.

## Decision

Authority is the number of blocks a train may still enter before it must stop, as a
non-negative integer, everywhere in the system.

- The count is of the blocks ahead of the train's current block, along its route. The
  current block is not counted.
- 0 means the train must stop before leaving its current block. A train in block 5 that
  may run through block 8 and stop there has an authority of 3.
- It applies to every authority signal: the CTC Office's suggested authority to the
  Track Controller, and the authority the Track Model sends to the train in the track
  signal.

## Consequences

- Authority is a count, not an identifier. `conventions/identifiers.md` no longer
  covers it; `conventions/units.md` records its unit as blocks.
- A count depends on the route, so whoever computes it walks the track in the train's
  direction of travel through the current switch positions.
- `common/interfaces.py` still carries `authority_m: float`. Under D008 the catalog
  must agree with truth, so it changes to an integer block count.
- Which module counts the authority down as the train enters each new block is not
  decided by this entry.
