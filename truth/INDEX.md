# Index

This file is read at the start of every agent session. Shards are read on demand, only when relevant to the work at hand.

| Shard | Path | Description | Last changed |
| --- | --- | --- | --- |
| UI design | [style-guide.md](ui/style-guide.md) | Visual tokens, component and accessibility rules | 2026-09-29 |
| Conventions: naming | [naming.md](conventions/naming.md) | Module names and aliases, Python naming, docstrings | 2026-10-19 |
| Conventions: units | [units.md](conventions/units.md) | Backend and display units, conversion factors | 2026-10-07 |
| Conventions: identifiers | [identifiers.md](conventions/identifiers.md) | ID values, requirement IDs, exceptions, design token names | 2026-10-19 |
| Conventions: files and paths | [files-and-paths.md](conventions/files-and-paths.md) | Paths, file names, delivery, module boundaries, layout, repository, linting | 2026-10-19 |
| Conventions: toolchain | [toolchain.md](conventions/toolchain.md) | Minimum tool versions checked at session start | 2026-10-01 |
| Modules | `truth/modules/` | One owned shard per module; a module with multiple implementations has a contract shard plus one shard per variant — all are placeholders except Train Model | 2026-10-19 |
| Signals | `truth/signals/` | One file per signal | 2026-10-19 |
| Arbitration | `truth/arbitration/` | One file per precedence rule | 2026-10-19 |
| Decisions | `truth/decisions/` | One file per decision | 2026-10-19 |

## Decisions on record

| ID | Decision |
| --- | --- |
| D001 | [Moving Block Overlay dropped from scope](decisions/D001-drop-mbo-from-scope.md) |
| D002 | [Two unit systems, split at the display layer](decisions/D002-two-unit-systems.md) |
| D003 | [`development` is the default branch; `main` is release-only](decisions/D003-branch-model.md) |
| D005 | [A central harness sits between the modules](decisions/D005-central-harness.md) |
| D006 | [Train Model is stepped with a fixed time step](decisions/D006-fixed-time-step.md) |
| D007 | [Station dwell time is 45 s, fixed](decisions/D007-station-dwell.md) |
| D008 | [`common/interfaces.py` is stale and no longer the signal catalog](decisions/D008-interfaces-harness-catalog.md) |
| D009 | [The Train Model is physics only; control belongs to the Train Controller](decisions/D009-train-model-control-boundary.md) |
| D010 | [The Train Model test UI is a separate, removable process](decisions/D010-train-model-test-ui-boundary.md) |
| D011 | [The passenger emergency brake button only applies](decisions/D011-passenger-emergency-brake-button.md) |
| D013 | [Authority is a count of blocks ahead of the train](decisions/D013-authority-block-count.md) |
| D017 | [One shared simulation clock, run by the harness at 1x or 10x](decisions/D017-shared-simulation-clock.md) |
| D020 | [Automatic dispatch from the schedule; trains stop at scheduled stations only](decisions/D020-automatic-dispatch-from-schedule.md) |
| D021 | [Hardware variants run on Raspberry Pis over USB; their UIs run on the host](decisions/D021-hardware-variants-and-selection.md) |
| D022 | [The yard is a black box; the CTC Office releases, creates and returns trains](decisions/D022-yard-black-box.md) |
| D023 | [The Blue Line is out of scope](decisions/D023-blue-line-out-of-scope.md) |
| D024 | [A new train waits for an engineer to set its gains](decisions/D024-train-gains-set-by-engineer.md) |
| D025 | [The CTC Office test UI stands in for the Track Controller only](decisions/D025-ctc-test-ui-boundary.md) |
| D026 | [The Track Model switches the track heaters](decisions/D026-track-model-switches-heaters.md) |
| D027 | [Each Raspberry Pi links to the host as a USB serial (CDC-ACM) device](decisions/D027-usb-link-to-the-pis.md) |

## Module shards

One row per module. All except Train Model are **placeholders**: each states the sources
that still need reading and carries no provenance, so nothing in them may be cited as truth.

A module with two implementations lives in a directory holding its contract shard and
one shard per variant. The contract is the definition both variants conform to; the
variant shards hold only what is true of that implementation alone.

| Module | Shard | Variants | Owner |
| --- | --- | --- | --- |
| CTC Office | [ctc-office.md](modules/ctc-office.md) | — | unassigned |
| Track Controller | [track-controller/](modules/track-controller/track-controller.md) | SW, HW | Harry Tye |
| Train Controller | [train-controller/](modules/train-controller/train-controller.md) | SW, HW | unassigned |
| Track Model | [track-model.md](modules/track-model.md) | — | unassigned |
| Train Model | [train-model.md](modules/train-model.md) | — | Kevin Schillinger |
