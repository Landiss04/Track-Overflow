# Index

This file is read at the start of every agent session. Shards are read on demand, only when relevant to the work at hand.

| Shard | Path | Description | Last changed |
| --- | --- | --- | --- |
| UI design | [style-guide.md](ui/style-guide.md) | Visual tokens, component and accessibility rules; [HTML review preview](ui/ui-style-guide-preview.html) | 2026-09-28 |
| Conventions | `truth/conventions.md` | Naming, units, identifiers, and file/path conventions | 2026-09-28 |
| Modules | `truth/modules/` | One owned shard per module; a module with multiple implementations has a contract shard plus one shard per variant — **all are placeholders, none assert facts** | 2026-09-28 |
| Signals | `truth/signals/` | One file per signal | — empty |
| Arbitration | `truth/arbitration/` | One file per precedence rule | — empty |
| Decisions | `truth/decisions/` | One file per decision | 2026-09-28 |

## Decisions on record

| ID | Decision |
| --- | --- |
| D001 | [Moving Block Overlay dropped from scope](decisions/D001-drop-mbo-from-scope.md) |
| D002 | [Two unit systems, split at the display layer](decisions/D002-two-unit-systems.md) |

## Module shards

One row per module. All are **placeholders**: each states the sources that still need
reading and carries no provenance, so nothing in them may be cited as truth.

A module with two implementations lives in a directory holding its contract shard and
one shard per variant. The contract is the definition both variants conform to; the
variant shards hold only what is true of that implementation alone.

| Module | Shard | Variants | Owner |
| --- | --- | --- | --- |
| CTC Office | [ctc-office.md](modules/ctc-office.md) | — | unassigned |
| Track Controller | [track-controller/](modules/track-controller/track-controller.md) | SW, HW | unassigned |
| Train Controller | [train-controller/](modules/train-controller/train-controller.md) | SW, HW | unassigned |
| Track Model | [track-model.md](modules/track-model.md) | — | unassigned |
| Train Model | [train-model.md](modules/train-model.md) | — | unassigned |
