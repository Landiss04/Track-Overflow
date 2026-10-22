**Target:** truth/decisions/harness-window-close.md
**Action:** create
**Proposed by:** Codex on claude/quirky-fermi-sickg4
**Provenance:** asserted by Kevin Schillinger 2026-10-20 in the
harness window implementation questions.

---

# harness-window-close

**Status:** current
**Owner:** Kevin Schillinger
**Provenance:** asserted by Kevin Schillinger 2026-10-20
**Aliases:** harness shutdown window, end run confirmation
**Last updated:** 2026-10-20

## Decision

Closing the harness window asks for confirmation. Confirming ends the
run using the same shutdown as Ctrl+C: send QUIT to every module,
then kill any that remain. Cancelling keeps the run and window open.
Module windows only hide when closed; the harness window is the
operator's place to end the run.

