# Session handover, 2026-10-22 (after Phase 6)

For a fresh session that continues the orchestration of the Track Overflow integration on
`claude/quirky-fermi-sickg4`. It holds only what the repository doesn't already say. For
everything else, read:
- `documents/integration-handover-phase-6.md`, `review-runbook.md` and
  `review-scenario-evidence-2026-10-22.md`;
- `documents/phase-6-prompt.md`, for the standing rules under "How you work".

## How this work runs

- **Kevin (the user) runs the build phases in Codex.** This session's role is orchestrator
  only (Kevin: "moving forward you are only the orchestrator all legwork is to be done by
  subagents and you review and validate"):
  - Write the next phase's prompt as `documents/phase-N-prompt.md`, with everything below a
    `---` line pasted into Codex.
  - When Kevin says a phase is done, verify it with one check-only subagent (no edits), then
    spot-check the key claims yourself.
  - Report to Kevin: a verdict per item, rule violations, suite numbers and his open
    questions.
  - Then draft the next prompt from his answers.
- **Prompts for Codex** name the subagent model as **"sol 6.1 medium effort"**, never this
  session's model.
- **Kevin answers questions tersely.** Ask with numbered options and mark the recommended one.
  Put his exact words in prompts and proposals as provenance.
- **Before writing a decision into a prompt, check it against the code.** Example: on
  2026-10-22, "wait for Braden's programs" turned out to mean his three Green programs in
  `TrackCtrlHw/data/plc/`, which led to a follow-up question.
- **Kevin's other wishes:**
  - When he asks for a prompt, print it in a code block for copy and paste, as well as
    committing it.
  - Wrap it in "how to find and start" instructions when he asks.
  - Make sure everything is committed and pushed before stopping.
- **The verification environment is per-container and is lost between sessions.** Recreate a
  venv (`python -m venv`, then `pip install "PySide6>=6.11" pytest mypy flake8 pyinstaller`),
  and run Qt with `QT_QPA_PLATFORM=offscreen`. Cloud hosts are 4-core: 10x runs reach about
  4x there, against about 9x on Kevin's machine (kevin-framework).

## Kevin's answers this session that the repo doesn't record

- **`TrackCtrlHw/ui/app.py` `state_factory` parameter (Phase 5 fixes):** "I approved the
  app.py change".
- **10x speed:** "wait for pi measurements". No optimization until real Pi numbers exist.
- **Red return:** reuse Braden's switch logic. This superseded his earlier "wait for real".
  Phase 6 did this.

## Phase 6 verification (2026-10-22, at `a23bc22`)

It was checked on a 4-core cloud host; I spot-checked the proposal collisions and the
`wayside.py` change myself.

**Rules held:**
- no UI file changed;
- `TrackModel/*_line.json` untouched;
- nothing promoted or pushed to `truth`;
- the D028 edit matches what Kevin asked for.

| Item | Verdict | Evidence or gap |
| --- | --- | --- |
| 1. Review scenario | Partly | One command from existing options, with tests and a run book. **Both review tests fail on a 4-core host**: they run at 10x and count `TIME_SLIPPED` as a fault. They pass at 1x. No CSV event records a station stop. |
| 2. Red switching | Met, with one exception | All seven Red switches (9, 15, 27, 32, 38, 43, 52) follow Braden's pattern; R1 returns and retires; the split is kept. **Exception:** `TrackCtrlHw/track_ctrl_hw/wayside.py` (Braden's core) gained neighbour `CLOSED_n` program inputs in the same commit, `16a64b8`. The prompt said to stop and ask first. The handover quotes Kevin approving "Approve shared read-only neighbor closure inputs", but nothing shows he was asked before the code was written. |
| 3. Two or more trains | Not met, reported honestly | Green with 2 trains passes. Green with 3 stalls with G2 at 65 and G3 at 64. Red stays at one train because of the CTC zone rule (9…66). The tests run in process, so protocol faults aren't exercised. The follower case is a seeded snapshot: at 76 the follower gets 0 authority, and occupancy of 76 holds switch 76 REVERSE. |
| 4. Speed, measured only | Partly | Recorded: 9.16x headless and 8.36x Wayland on kevin-framework; 4.26x on the cloud host. The "zero slipped" claim is corrected, and `measure` now prints a hint when `--test-pi` is missing. The difference between machines is described but not explained. |
| 5. Linux build | Met | Built and smoke-tested from outside the checkout. When frozen, the host and the simulated agent read the same `pi-bundle.json`, so the hash check can't fail in that smoke test. |
| 6. Event log | Met | No new events were needed. |
| 7. Fix-check findings | Met | CTC Office change log, D028, the Track Model guard limited to Red block 9 (a Green test fails on the old code), and the flake8 wording. |
| 8. Run book and design §5.7 | Met | `review-runbook.md` hard-codes `/home/kevin/...` as the Python path. |
| 9. Pis turnkey | Mostly | One provisioning recipe; identity and port matching only in `transport.py`; echo and fault checks run against simulated Pis. **HELLO validation is written twice**: `common/hw_link/relay.py:135-140` and `bringup.py:220-227`. The real-board fault checks are a checklist without scripts. |
| 10. Proposals | Partly | See the proposal problems below. |

**Proposal problems.** The inbox now holds 34 on this branch, plus 4 from PR #43.
- **Decision-number collisions between Codex's and this session's proposals:**
  - D033: `red-integration-plc-routing` and `red-test-plc-switch-routing`, which say the same
    thing;
  - D034: `phase6-integration-scope` and `authoritative-green-plc-programs`;
  - D035: `shared-neighbor-closures` and `pi-paths-share-one-implementation`.
- **`20261022-1135-phase6-integration-scope`** records a plan, which `AGENTS.md` forbids in
  truth. It also overlaps D032 and D035.
- **`shared-neighbor-closures`** gives only the option text "Approve…" as provenance.
- Proposals may be edited only where Kevin asks; leave renumbering and withdrawal to him.

**Suites on the cloud host.** Baseline at `b81e213` in brackets.

| Suite | Result |
| --- | --- |
| Harness + utils | 261 passed, 4 failed (260) |
| `common/hw_link` | 44 (33) |
| Track Controller HW | 89 (80) |
| CTC Office | 261 |
| Track Controller SW | 213 |
| Track Model | 312 (310) |
| Train Controller HW | 23, with `main.py --check` clean |
| Train Controller SW | 24 |
| Train Model | 878, plus the known flaky UI test |
| Opt-in | 44 passed, 5 failed |

What failed:
- **Harness + utils (4):**
  - the two review scenarios, on `TIME_SLIPPED`;
  - `test_run_is_clean`, which failed in 4 of 11 runs at HEAD against 0 of 10 at `b81e213`.
    This hints at a small 10x slowdown on weak hosts, not proven;
  - a `test_clock_driver` rapid-speed-change test, which passes alone.
- **Opt-in (5):** the 3 expected multi-train failures and the 2 review scenarios.
- **flake8:** passes only with N815 ignored, as before. `common/hw_link/tests/test_bringup.py:124-139`
  adds new N802 warnings.
- **mypy:** `common/hw_link` is clean.

## Open questions for Kevin (next step: ask, then write the next prompt)

1. Did you approve the neighbour `CLOSED_n` core input before it was written? Does Braden
   accept the change to his `wayside.py`?
2. Should the review run at 1x? Or should `TIME_SLIPPED` stop counting as a fault in the review
   tests? Which machine will the review use?
3. How should the proposal collisions be settled: D033 (keep one), D034 (withdraw the scope
   proposal as a plan?), D035 (renumber)?
4. The CTC Office questions for its owner:
   - Red allows only one train because of its zone rule;
   - Green with 3 trains stalls at 65/64;
   - the follower at 76.

   The "2+ trains" requirement (D032) depends on these.
5. Should the duplicate HELLO validation be folded into one helper? Should
   `TrackCtrlHw/CHANGELOG.md` name Braden explicitly as reviewer? Should the run book drop
   the hard-coded `/home/kevin` path?
6. Still open from earlier:
   - removing the SW vital layer (Harry);
   - Braden's real Red programs;
   - the Red block-9 reading;
   - the cross-wayside "missing counts as clear" rule;
   - the 38 pending proposals awaiting human promotion.
