**Target:** truth/conventions/identifiers.md
**Action:** replace
**Proposed by:** Claude (Claude Code) on Train-model-Interface
**Provenance:** authority as a count of blocks asserted by Kevin Schillinger 2026-10-05 in this chat ("Authority has been changed to be the number of blocks the train is able to travel before it must stop … update it to be an integer value"); not in the repository. Companion to the inbox proposal `20261005-0744-units-authority-block-count.md`. Only the authority bullet, the provenance, the date and the supersedes line change.

---

# identifiers

**Status:** current
**Owner:** Kevin
**Provenance:** `documents/PYTHON_STYLE_GUIDE.md` §8; `documents/Coding Standards (Group).docx` §1.1, §2.2; `documents/srs-filled.md` §1.3, §5 Appendix A; `truth/ui/style-guide.md` §3, §6.7; the design token mapping asserted by Kevin 2026-09-30; authority as a count of blocks, not an ID, asserted by Kevin Schillinger 2026-10-05
**Aliases:** IDs, ID formats, key formats
**Last updated:** 2026-10-05

## ID values

- **All IDs are strings**, never integers, even when they look numeric. This applies
  to train IDs, block IDs, and station codes. The rule exists to make arithmetic on
  an identifier a type error rather than a silent bug.
- Track layout files carry a Block Number column. The value is read as a string.
- **Authority is not an ID.** It is the number of blocks the train may travel before it
  must stop, an integer, so the all-IDs-are-strings rule does not apply to it. See
  [units.md](units.md).
- How IDs and timestamps render in a UI is set by `truth/ui/style-guide.md` §3.

## Requirement IDs

`REQ-<AREA>-<NNN>` — uppercase area, three-digit zero-padded number. Example:
`REQ-FUNC-007`.

## Exception identifiers

- Every custom exception derives from `Exception`, never `BaseException`.
- Each module defines one base exception so callers can catch the whole project's
  errors in one clause — e.g. `TrainControllerError`, with `InvalidBlockError`
  deriving from it.
- The hierarchy is designed around what the catching code needs to know: "what went
  wrong", not "a problem occurred".
- Re-raising uses explicit chaining: `raise NewError("...") from original_error`.

## Design token identifiers

UI design tokens use the `--kebab-case` names in `truth/ui/style-guide.md`
Sections 3, 4, and 5. That spelling is canonical. A token that does not exist is added
to the style guide first, then used.

The other spellings are derived mechanically: drop the leading `--`, replace each `-`
with `_`, then

| Context | Rule | Example |
|---------|------|---------|
| Style guide (canonical) | `--kebab-case` | `--bg-app` |
| Python | UPPER_SNAKE_CASE constant, per [naming.md](naming.md) | `BG_APP` |
| QML | `theme.` + lower_snake_case | `theme.bg_app` |

No token takes a spelling that does not follow from its canonical name.

## Pending

The only train ID format appearing in a normative document is `TRN-014`, as an
example in `truth/ui/style-guide.md` §6.7 (`Train Controller — TRN-014`). It is an
illustration, not a stated format. Block and station ID formats are not stated
anywhere. Owner: Kevin — decide and record, or record that IDs are opaque strings
with no enforced shape.

## Supersedes

- Authority: previously a block ID, a string (Kevin 2026-09-30); now a count of blocks,
  an integer, and not an identifier (Kevin Schillinger 2026-10-05).
