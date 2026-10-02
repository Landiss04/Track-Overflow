# Index

This file is read at the start of every agent session. Shards are read on demand, only when relevant to the work at hand.

| Shard | Path | Description | Last changed |
| --- | --- | --- | --- |
| UI design | [style-guide.md](ui/style-guide.md) | Visual tokens, component and accessibility rules | 2026-09-29 |
| Conventions: naming | [naming.md](conventions/naming.md) | Module names and aliases, Python naming, docstrings | 2026-10-02 |
| Conventions: units | [units.md](conventions/units.md) | Backend and display units, conversion factors | 2026-09-30 |
| Conventions: identifiers | [identifiers.md](conventions/identifiers.md) | ID values, requirement IDs, exceptions, design token names | 2026-09-30 |
| Conventions: files and paths | [files-and-paths.md](conventions/files-and-paths.md) | Paths, file names, delivery, module boundaries, layout, repository, linting | 2026-09-29 |
| Conventions: toolchain | [toolchain.md](conventions/toolchain.md) | Minimum tool versions checked at session start | 2026-10-01 |
| Modules | `truth/modules/` | One owned shard per module; a module with multiple implementations has a contract shard plus one shard per variant — all are placeholders except Train Model | 2026-10-02 |
| Signals | `truth/signals/` | One file per signal | 2026-10-02 |
| Arbitration | `truth/arbitration/` | One file per precedence rule | 2026-10-02 |
| Decisions | `truth/decisions/` | One file per decision | 2026-10-02 |

## Decisions on record

| ID | Decision |
| --- | --- |
| D001 | [Moving Block Overlay dropped from scope](decisions/D001-drop-mbo-from-scope.md) |
| D002 | [Two unit systems, split at the display layer](decisions/D002-two-unit-systems.md) |
| D003 | [`development` is the default branch; `main` is release-only](decisions/D003-branch-model.md) |
| D005 | [A central harness sits between the modules](decisions/D005-central-harness.md) |
| D006 | [Train Model is stepped with a fixed time step](decisions/D006-fixed-time-step.md) |
| D007 | [Station dwell time is 45 s, fixed](decisions/D007-station-dwell.md) |
| D008 | [`common/interfaces.py` is the system-level signal catalog](decisions/D008-interfaces-harness-catalog.md) |
| D009 | [The Train Model is physics only; control belongs to the Train Controller](decisions/D009-train-model-control-boundary.md) |
| D010 | [The Train Model test UI is a separate, removable process](decisions/D010-train-model-test-ui-boundary.md) |
| D011 | [The passenger emergency brake button only applies](decisions/D011-passenger-emergency-brake-button.md) |

## Module shards

One row per module. All except Train Model are **placeholders**: each states the sources
that still need reading and carries no provenance, so nothing in them may be cited as truth.

A module with two implementations lives in a directory holding its contract shard and
one shard per variant. The contract is the definition both variants conform to; the
variant shards hold only what is true of that implementation alone.

| Module | Shard | Variants | Owner |
| --- | --- | --- | --- |
| CTC Office | [ctc-office.md](modules/ctc-office.md) | — | unassigned |
| Track Controller | [track-controller/](modules/track-controller/track-controller.md) | SW, HW | unassigned |
| Train Controller | [train-controller/](modules/train-controller/train-controller.md) | SW, HW | unassigned |
| Track Model | [track-model.md](modules/track-model.md) | — | unassigned |
| Train Model | [train-model.md](modules/train-model.md) | — | Kevin Schillinger |
