# Phase 2 proposal: pipelined STEPs and delta VIEWs (not implemented)

Changes the host-Pi wire protocol (D027) and, for pipelining, the tick rule in D017.
**Decision (the Pi-link owner, 2026-11-13): A3, no pipelining. Delta VIEWs deferred.** Nothing here is built.

## What the measurements say (sandbox, x86; Pi numbers pending)

- A STEP round trip on the link is 0.6 ms (Train) and 3.6-4.0 ms (Track). Track's time is
  the core: 2.6-3.0 ms of it, 90%+ in the PLC interpreter (`plc.py`, three waysides, two
  redundant scans each).
- A Track VIEW is 41 KB every 200 ms; 99.4% of its lines are identical to the previous one.
  Host cost to decode and unpack it: 0.36 + 0.59 ms, once per 20 ticks.

## A. Pipelining 2-4 STEPs per Pi

D017: the harness sends tick N+1 only after every module replied to tick N, and each module's
inputs are the previous tick's outputs of the others. Tick N+1's inputs therefore depend on
tick N's replies, so two STEPs for one Pi can never be in flight at once without changing
that rule. Options:

| Option | What changes | Cost |
| --- | --- | --- |
| A1. Output lag of k-1 ticks for the two HW modules only: STEP N+1 is sent with inputs from tick N-1's outputs | D017 and the edge contract; both Red modules see the world 10 ms (k=2) to 30 ms (k=4) late at 10x, 100 ms to 300 ms at 1x | Control latency becomes simulated physics; every Red scenario test must be re-baselined |
| A2. Keep D017; overlap only host work (parse, GUI) with the Pi's compute | Nothing on the wire | Saves at most the host's 0.4-1 ms per tick; no change to the Pi's 3 ms |
| A3. Do nothing | none | none |

If A1: add `window` to HELLO; the agent keeps the last `window` STEPs in `cache` (today only the
latest, `_remember`), executes in `id` order, and replies in order; the host resends any
unanswered STEP in order after a reconnect (`relay._lost_requests` already resends from
`durable`). Rollback of a refused STEP must also drop later STEPs already sent.

Recommendation: A3 until a Pi run shows the round trip, not the Pi core, is what slips. With
a 3 ms core and 0.6 ms link there is no pipelining gain that A1's latency would not cost back.

## B. Delta VIEWs

VIEW carries the full snapshot every 200 ms. Proposal: `VIEW` gains `base` (the tick of the
snapshot it patches, or null for a full one) and `patch` (changed paths only). The host replies
nothing; it asks for a full VIEW by an ACTION `resync` when `base` does not match what it holds,
and the agent sends a full one on every HELLO and at least once per second.

Saves about 40 KB per VIEW on the wire and under 1 ms of host decode per VIEW. At 5 VIEWs per
second that is about 0.5% of one core on the host and 200 KB/s on the link; it will not move
p99 (1 in 20 ticks carries it, so it shows at p95 at most).

Recommendation: defer. If wanted regardless, B alone needs no D017 change, only D027.

## Decision needed

1. A: A1, A2 or A3? A1 needs Landis (D017 owner) as well as you.
2. B: build now or defer?
