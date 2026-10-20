# identifiers

**Status:** current
**Owner:** Kevin
**Provenance:** `documents/PYTHON_STYLE_GUIDE.md` §8; `documents/Coding Standards (Group).docx` §1.1, §2.2; `documents/srs-filled.md` §1.3, §5 Appendix A; `truth/ui/style-guide.md` §3, §6.7; the design token mapping asserted by Kevin 2026-09-30; block references by line and block number, and switch IDs, asserted by Landis 2026-10-03; authority is not an identifier per D013 (2026-10-06); train IDs from the CTC Office, exact line names, and station names as written in the layout files, agreed in the CTC Office's answers of 2026-10-20, relayed by Kevin Schillinger
**Aliases:** IDs, ID formats, key formats
**Last updated:** 2026-10-20

## ID values

- **All IDs are strings**, never integers, even when they look numeric. This applies
  to train IDs, block IDs, and station codes. The rule exists to make arithmetic on
  an identifier a type error rather than a silent bug.
- Track layout files carry a Block Number column. The value is read as a string.
- **A block is identified by its line and its block number together.** Block numbers
  repeat across lines (Green 12 and Red 12 are different blocks), so a block ID alone
  does not name a block. Every block reference that crosses a module boundary carries
  two strings: `line` (the line name, e.g. `"Green"`) and `block_id` (the block
  number, e.g. `"12"`), as the track layout files and the schedule do.
- **A switch is identified by its line and the block it is listed on** in the track
  layout file. Green block 12 lists the switch `12-13; 1-13`, so its ID is line
  `"Green"`, switch ID `"12"`.
- **Train IDs come from the CTC Office**, which creates every train
  ([D022](../decisions/D022-yard-black-box.md)). A scheduled run's ID is its line's
  initial and its run number: `G1` to `G10` and `R1` to `R10` in the current schedule.
  A manual train's ID is what the dispatcher enters; the CTC window suggests `T1`, `T2`
  and so on. A train ID is a plain string, trimmed and printable, at most 32
  characters. Every module that handles a train uses that ID unchanged.
- **Line names match exactly, case included:** `"Green"` and `"Red"`. A module that
  spells a line otherwise, such as the Track Model's `GREEN`, is mapped at the harness.
- **Station names are written exactly as in the track layout files**, in upper case:
  `GLENBURY`. The line-name mapping does not apply to them.
- **Authority is not an identifier.** It is a count of blocks, an integer; see
  [units.md](units.md) and D013.
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

## Notes

- `truth/ui/style-guide.md` §6.7 shows `TRN-014` as an illustration of a train ID in a
  UI header. It is not the train ID format.

## Supersedes

- Authority: previously listed here as a block ID string (Kevin 2026-09-30); now a
  count of blocks and no longer an identifier, per D013 (2026-10-06).
- Train ID format: previously pending, with only the style guide's `TRN-014` example; now
  set by the CTC Office (2026-10-20).
