**Target:** truth/decisions/harness-stubs-only-auto-run.md
**Action:** create
**Proposed by:** Codex on claude/quirky-fermi-sickg4
**Provenance:** Kevin Schillinger's direct statement of 2026-10-21, "Keep automatic Run for --stubs-only", answering whether a stubs-only window run should press Run automatically because the stub CTC Office has no window, or require `--auto-run`. The ordinary-window and headless policy is Kevin's R83 decision of 2026-10-21 in `documents/system-integration-design.md` §1.4; clock ownership follows D017. No matching decision key or alias exists in the session's fetched `origin/truth`.

---

# harness-stubs-only-auto-run

**Status:** current
**Owner:** Kevin Schillinger
**Provenance:** asserted by Kevin Schillinger 2026-10-21: R83 for ordinary window and headless runs; "Keep automatic Run for --stubs-only" for the stubs-only window exception.
**Aliases:** stubs-only automatic Run, stub CTC Run exception, harness Run policy, run-on-ready, auto-run
**Last updated:** 2026-10-21

## Context

The CTC Office owns Run through the harness (D017). Its stub has no window in
which a dispatcher can press Run.

## Decision

- An ordinary window run waits for the dispatcher to press Run in the CTC Office's
  window.
- A headless run has the CTC Office press Run automatically once ready.
- A `--stubs-only` run also presses Run automatically once ready, including when
  the harness has a window. It does not require `--auto-run`.
- `--auto-run` explicitly requests automatic Run for a real-module window run,
  for tests and demonstrations.

## Consequences

The stubs-only window exception preserves automatic startup without requiring a
CTC Office window. These launch options request Run through the CTC Office; they
do not change harness clock ownership or module-readiness requirements.
