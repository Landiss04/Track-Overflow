# Source of Truth

The `truth` branch is the authoritative record for this repo. It holds normative facts
only: interfaces, signal definitions, arbitration and precedence rules, naming and unit
conventions, and decisions. It does not hold status — what is stubbed, what is
implemented, defect counts, coverage. Status is read from the repo itself and must
never be written into the truth store.

Agents read facts from the `truth` branch and write proposals to `truth/_inbox/` on
their feature branch. Promotion of a proposal onto the `truth` branch is human-only.

## Reading facts

- Facts live only on the `truth` branch. Never assume a local copy exists. Nothing
  under `truth/` in the working tree is a fact.
- Fetch once per session: `git fetch origin truth`
- Enumerate entries: `git ls-tree -r --name-only origin/truth -- truth/`
- Search content: `git grep <pattern> origin/truth -- truth/`
- Read one entry: `git show origin/truth:truth/<path>`
- Read `truth/INDEX.md` first, via `git show`. Read individual shards on demand. Never
  read the whole store.
- Bulk reads may be written to a scratch directory outside the repo, e.g.
  `/tmp/truth-<session>/`. Scratch copies are valid for the current session only,
  require a fresh `git fetch` at session start, and are never reused across sessions.
  Never write truth content anywhere inside the repo.
- Nothing under `truth/incoming/` is a fact. It is promoted content in transit to its
  canonical path.

## At session start

1. `git fetch origin truth`.
2. Read `truth/INDEX.md` with `git show origin/truth:truth/INDEX.md`. Always. It lists
   every shard with a one-line description and a last-changed date.
3. Read only the shards relevant to the work at hand. Do not read the whole store.
4. Environment drift check. Verify the local toolchain meets the minimum versions in
   `truth/conventions/toolchain.md` (read via `git show`). If it does not, report the
   mismatch to the user before starting work.
5. System check. Report the date, time, machine name, and operating system name.
6. Check `truth/_inbox/<current-branch>/`. If it is non-empty, these are proposals from
   a previous session awaiting promotion. Present them to the user before starting new
   work.

## Writing proposals

When you learn a normative fact that is absent from the `truth` branch, contradicts it,
or supersedes it, write a proposal immediately. Do not wait for the end of the session.

- Write to `truth/_inbox/<branch>/<YYYYMMDD-HHMM>-<slug>.md` on the current feature
  branch.
- `<branch>` is the feature branch name from `git rev-parse --abbrev-ref HEAD`, run at
  the repo root. It is never `truth`.
- `truth/_inbox/` does not exist on the `truth` branch. Never attempt to write a
  proposal there.
- Commit and push the proposal in the same session that produced it. Never leave a
  proposal uncommitted, or in an unpushed commit.
- One proposal per file. One new file each time. Never edit an existing proposal
  except when the user asks for a modification.
- A proposal is the **full proposed entry**, in final form, ready to be copied to its
  canonical path. Not a diff, not a description of an edit.
- Every proposal states its target canonical path and its provenance.
- When `truth/_inbox/<branch>/` holds five proposals, present them to the user for
  review before continuing work. This does not replace the session-start check.

Do not infer facts from code and record them as normative. Code is evidence of what
is, not of what was decided. A normative fact comes from a decision, a document, a PR
discussion, or a direct statement by the user.

## Promotion — human only

- Agents never promote proposals, never open a PR against `truth`, and never push to
  `truth` or any `promote-*` branch.
- If a proposal is ready to promote, say so and stop. Do not act on it.
- A human promotes by merging approved proposals, wrapper included, into
  `truth/incoming/` on `truth`. The `truth-incoming` workflow then moves each entry to
  its `**Target:**` path and deletes the incoming file. That workflow is the only
  non-human writer to `truth`.
- The procedure is `RUNBOOK.md` on the `truth` branch. It is for humans only.

## Git invariants

These are invariants, not a list of banned commands. Any command not listed below is
to be evaluated against the invariant, not assumed permitted.

1. **The primary worktree's checked-out branch never changes.** Violated by
   `git checkout <branch>`, `git switch <branch>`, `git checkout -b`, `git switch -c`,
   `git checkout <commit>`, and any `git worktree` operation against the primary path.
2. **Truth content is never written to disk inside the repo.** Violated by
   `git checkout origin/truth -- <path>` and `git restore --source=origin/truth <path>`
   — both look like reads and in fact materialise and stage content. Also violated by
   redirecting `git show` output to a file inside the repo. Never check out, merge, or
   rebase `truth` into a code branch, and never run
   `git merge --allow-unrelated-histories` against it.
3. **Uncommitted work is never discarded.** Violated by `git reset --hard`,
   `git clean -fd`, `git stash` (which reaches invariant 1 by making the tree look
   clean), and `git checkout -- <path>` against a file with uncommitted changes.

`git worktree add` is forbidden to agents entirely, including `--detach`. It is a
promotion-time mechanism and belongs to the human runbook (`RUNBOOK.md` on `truth`).

These invariants apply to all agents in all clones, not only the developer's primary
working clone.

On confusion, stop and report. If you find yourself on an unexpected branch, or the
tree is not in the state you expected, report it and stop. Do not correct it.

## Deletion rule

- Only a human deletes inbox files, as part of promotion.
- Deletion is scoped to `truth/_inbox/**/*.md`.
- `truth/_inbox/.gitkeep` and `truth/README.md` are never deleted or modified. They are
  the scaffold that inherits into new branches.
- On `truth`, the `truth-incoming` workflow deletes files under `truth/incoming/` as it
  moves them to their canonical paths. `truth/incoming/.gitkeep` is never deleted.

## Entry rules

One file per entry. One entry per file. The filename is the entry key.

Required fields, as bold-label lines at the top of the file:

```
**Status:** current | superseded
**Owner:** <module or person>
**Provenance:** <decision ID, PR, document, or "asserted by <name> <date>">
**Aliases:** <comma-separated alternate names, or "none">
**Last updated:** <YYYY-MM-DD>
```

An entry without provenance is unverified and must not be treated as truth.

Prose goes in the body under `##` headings. Keep it short.

### Supersession

Keep only the current value. Git holds the history. When an entry's value changes,
overwrite it and record a `## Supersedes` section naming what the previous value was
and why it changed. One line each. Do not accumulate a running log — the previous
entry is in git.

### Conflicts

When two sources assert incompatible values for the same entry, keep both. Do not
pick one. Add a `## Conflict` section to the entry giving each value, the provenance
of each, and an owner responsible for resolving it. The owner is mandatory. Leave
`**Status:**` as `current` and let the conflict section carry the warning.

### Aliases

Every entry declares its known alternate names so that two branches naming the same
thing differently can be caught. If you are about to create an entry, check the
existing keys and aliases in that shard first.

### Modules with multiple implementations

A module with variants gets **one contract shard plus one shard per variant**, all in
a directory named for the module: `modules/<module>/<module>.md` for the contract and
`modules/<module>/<module>-<variant>.md` for each variant. The contract shard is the
definition every variant conforms to; each variant shard holds only what is true of
that implementation alone. Use `_templates/module-contract.md` and
`_templates/module-variant.md`.

A module with a single implementation stays a flat `modules/<module>.md`. Do not
create a directory for it until a second implementation exists.

The contract shard has a **single named owner**. Variant authors do not edit it
directly — they propose changes through `_inbox/`, and a pull request touching a
contract shard requires **both variant authors as reviewers**.

`signals/` entries name the **module** as producer, never a specific variant. A
signal that only one variant produces is a contract violation, not a signal
attribute.

How the active variant is selected is a `decisions/` entry, not a module fact.
Neither the contract shard nor a variant shard records which implementation is in
use.

## Layout

On the `truth` branch:

```
AGENTS.md               these rules; identical on development
RUNBOOK.md              human promotion procedure; not for agents
.github/                truth-incoming workflow and its move script
truth/
  README.md             what this branch holds; start at INDEX.md
  INDEX.md              always read
  _promotions.md        promotion log: one line per promoted or denied proposal
  incoming/             promoted proposals in transit; never facts
  _templates/           entry.md, decision.md, module-contract.md,
                        module-variant.md, and fragment.md (proposal wrapper)
  conventions/<key>.md  naming, units, identifiers, files-and-paths, toolchain
  ui/style-guide.md     UI style guide: visual tokens and component rules
  modules/<module>.md   one owned shard per module
  modules/<module>/     a module with variants: contract shard plus one per variant
  signals/<signal>.md   one file per signal
  arbitration/<rule>.md one file per precedence rule
  decisions/<id>.md     one file per decision
```

On `development` (the default branch; `main` is release-only, see
`decisions/D003-branch-model.md`) and every feature branch cut from it:

```
AGENTS.md               these rules; identical on truth
truth/
  README.md             scaffold; never modified
  _inbox/.gitkeep       scaffold; never modified
  _inbox/<branch>/      agent write zone
```

`modules/` shards are single-owner and low-contention; tables inside them are fine.
`conventions/`, `signals/`, `arbitration/`, and `decisions/` are directory-as-table: one
file per entry, so that unrelated additions merge cleanly and a real disagreement over the
same fact surfaces as a conflict in one file.
