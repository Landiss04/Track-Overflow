# Source of Truth

`truth/` is the authoritative record for this repo. It holds normative facts only:
interfaces, signal definitions, arbitration and precedence rules, naming and unit
conventions, and decisions. It does not hold status — what is stubbed, what is
implemented, defect counts, coverage. Status is read from the repo itself and must
never be written into `truth/`.

Agents read `truth/`. Agents never edit `truth/` directly. Proposed changes go to
`truth/_inbox/<branch>/` and are applied only after the user approves them.

## At session start

1. Read `truth/INDEX.md`. Always. It lists every shard with a one-line description
   and a last-changed date.
2. Read only the shards relevant to the work at hand. Do not read the whole store.
3. Check whether the store is behind main:

   ```
   git fetch origin main && git log --oneline HEAD..origin/main -- truth/
   ```

   If the output is non-empty, tell the user the truth store is behind main and name
   the changed files before relying on them.
4. *Placeholder — environment drift check. Verify the local toolchain matches the
   versions recorded in `truth/conventions.md`. Unpopulated; no action required yet.*
5. Check `truth/_inbox/<current-branch>/`. If it is non-empty, these are undrained
   proposals from a previous session. Present them to the user for review before
   starting new work.

## During the session

When you learn a normative fact that is absent from `truth/`, contradicts it, or
supersedes it, write a fragment immediately. Do not wait for the end of the session.

- Path: `truth/_inbox/<branch>/<YYYYMMDD-HHMM>-<slug>.md`
- One fragment per proposal. One new file each time. Never edit an existing fragment
  except when the user asks for a modification.
- A fragment is the **full proposed entry**, in final form, ready to be copied to its
  canonical path. Not a diff, not a description of an edit.
- Every fragment states its target canonical path and its provenance.

Do not infer facts from code and record them as normative. Code is evidence of what
is, not of what was decided. A normative fact comes from a decision, a document, a PR
discussion, or a direct statement by the user.

## At session end

Walk `truth/_inbox/<branch>/` and present each fragment to the user with a summary of
what it asserts, what it changes, and where it came from. For each one the user
approves, denies, or modifies:

- **Approve** — apply the fragment to its canonical path, then delete the fragment.
- **Deny** — delete the fragment.
- **Modify** — rewrite the fragment as instructed, then apply and delete it.

After draining, the branch's `truth/` is correct and the inbox is empty. The pull
request is the second gate; the user's in-session approval is the first.

Do not drain silently and do not apply a fragment the user has not seen.

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

## Layout

```
truth/
  INDEX.md              always read
  conventions.md        naming, units, ID formats
  modules/<module>.md   one owned shard per module
  signals/<signal>.md   one file per signal
  arbitration/<rule>.md one file per precedence rule
  decisions/<id>.md     one file per decision
  _inbox/<branch>/      agent write zone
  _generated/           renderer output, not committed
```

`modules/` shards are single-owner and low-contention; tables inside them are fine.
`signals/`, `arbitration/`, and `decisions/` are directory-as-table: one file per
entry, so that unrelated additions merge cleanly and a real disagreement over the
same fact surfaces as a conflict in one file.

Never write to `truth/_generated/`. It is produced by the renderer.
