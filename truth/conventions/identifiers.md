# identifiers

**Status:** current
**Owner:** Kevin
**Provenance:** `documents/PYTHON_STYLE_GUIDE.md` §8; `documents/Coding Standards (Group).docx` §1.1, §2.2; `documents/srs-filled.md` §1.3, §5 Appendix A; `truth/ui/style-guide.md` §3, §6.7; authority as a block ID and the design token mapping asserted by Kevin 2026-09-30
**Aliases:** IDs, ID formats, key formats
**Last updated:** 2026-09-30

## ID values

- **All IDs are strings**, never integers, even when they look numeric. This applies
  to train IDs, block IDs, and station codes. The rule exists to make arithmetic on
  an identifier a type error rather than a silent bug.
- Track layout files carry a Block Number column. The value is read as a string.
- **Authority is a block ID.** It names the destination block up to which the train may
  travel, so it is a string like every other block ID and is never converted for
  display. See [units.md](units.md) `## Resolved`.
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

- Authority: previously a distance transported as `authority_m: float`; now a block ID
  (Kevin 2026-09-30).
