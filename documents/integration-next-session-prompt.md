# Prompt for the next integration session

Paste everything below the line into a new session on branch `claude/quirky-fermi-sickg4`.

---

You are continuing the Track Overflow system integration on branch
`claude/quirky-fermi-sickg4` (never change branches; no PR unless I ask). Phases 0 to 4 are
built. The Iteration 3 scenario (dispatch a train from the yard to a Green station) runs end
to end, and as of 2026-10-21 a Green train also completes the full round trip and is retired
at 57.

## How you work

- You are the **orchestrator only**. Every piece of legwork (reading code, editing, testing,
  measuring, writing documents) goes to subagents: model `opus`, effort `medium`. You plan,
  write their prompts, review and validate what they report (check their commits'
  `git show --stat`, re-run the key tests yourself), and report to me.
- Several agents may run at once in the one working tree. AGENTS.md forbids git worktrees for
  agents, so give each agent a disjoint set of files, and tell every agent: stage explicit
  paths only (never `git add -A`), check `git diff --cached --stat` before committing, never
  touch another agent's uncommitted changes, wait and retry if `.git/index.lock` exists.
- Every commit message ends with the two attribution lines this session's system reminder
  gives. No model identifiers in repository files. Push with
  `git push -u origin claude/quirky-fermi-sickg4`, retrying only on network errors.
- **No UI changes** unless I ask for one by name (my rule of 2026-10-21).
- Follow AGENTS.md exactly: session-start steps (fetch `truth`, read `truth/INDEX.md`,
  toolchain check, report date/time/machine/OS, check this branch's inbox), truth is read with
  `git show` only, proposals only from my decisions or documents, promotion is human-only.
- Python with the toolchain: create a venv in the scratchpad if none exists
  (`pip install "PySide6>=6.11" "pyinstaller>=6.22.2" pytest mypy flake8 pep8-naming`), and run
  Qt tests with `QT_QPA_PLATFORM=offscreen`.

## Read first

1. `AGENTS.md`.
2. `documents/integration-handover-phase-4.md` and `documents/integration-handover-phase-3.md`
   (as built, open questions, commit tables).
3. `documents/system-integration-design.md` v0.12: §1.4 rulings (R83 to R90 are mine of
   2026-10-21), §1.5 open questions, §5.4 and §5.5, §6 gaps.
4. `common/harness/README.md`.

## First task: a summary of all changes

Before any new work, have a subagent produce a **summary of every change on this branch
since `c311800`** (the last commit before Phase 3), and give it to me. Group it by area:
harness, CTC Office, Track Controller SW, Track Model, Train Model, Train Controller,
utils, documents, truth proposals. For each item give what changed, why (the ruling or
decision), the commit hashes, and the tests that cover it. Then list every module change made
for an owner to review (Track Controller starter rules and PLC inputs `SUG_n`/`REV_s`, the
switch dialog rename, CTC next-block suggestion, train events, return to yard, harness clock,
Train Controller engine-failure rule) and every open question with its owner. Validate the
summary against `git log --stat c311800..HEAD` before you pass it on. Put it in
`documents/integration-summary.md`, commit, push, and show it to me.

## Then, in this order

1. **Small loose ends from 2026-10-21:**
   - The `ReturnToYardTest` docstring in `common/harness/tests/test_harness_train_loop.py`
     still says it fails at block 93. It passes since `460579b` (5/5, about 2 min, only with
     `TRACK_OVERFLOW_ROUND_TRIP=1`). Fix the docstring.
   - Record in the design document and the Phase 4 handover:
     - the round trip is unblocked;
     - Q-P4-8 is resolved by `460579b`;
     - the engine-failure rule as built: never within 0.05 m/s of target; a steady fall of
       more than 0.05 m/s over 6 s, with power commanded and no brake commanded or
       reported.
   - Record its two known limits:
     - a train at a stand with a dead engine is not flagged;
     - a heavily loaded train that cannot hold speed on Green 7's 5 % grade is flagged.
2. **Ask me** (do not decide):
   - The engine detector adds a "steady fall" test on top of my three rules. A straight-line
     check stops the grade sag at Green 7 (about 0.51 m/s, recovered in about 3 s) from
     latching. Do I accept it? See `Train-Ctrl_HW/OPEN_ISSUES.md` #26 and the proposal
     `truth/_inbox/claude/quirky-fermi-sickg4/20261021-1536-engine-failure-detection.md`.
   - Should a `--stubs-only` window run keep pressing Run by itself (the stub CTC has no
     window), or need `--auto-run` too?
   - Present the 18 proposals in `truth/_inbox/claude/quirky-fermi-sickg4/` for review.
     Promotion is mine.
3. **Owner questions to put to me for relay**, still open:
   - **Harry Tye:**
     - keep the new starter switch rule, `SUG_n`/`REV_s`, and switch 28 standing reverse
       at rest?
     - should the vital switch lock cover the points block, or move to it?
     - a cross-wayside occupancy input?
   - **Landis:** does the two-way zone keep a follower off 75/76 while a train stands on 77
     bound for 101?
   - **Track Model owner:**
     - the ticket sales rate (Q-P4-7);
     - switch naming by point versus truth's listed-on block (Phase 3 Q3);
     - bug B1 (light ahead);
     - D026 heaters, with no rule stated (Q6).
   - Phase 3 Q5 (Red `75-yard` normal leg), Q8, Q9, Q10, Q11 and Q12, as listed in the
     Phase 3 handover.
4. **Phase 5**, once I say go. Its scope:
   - the Red Line on the Track Controller HW and the Train Controller HW, on Raspberry Pis
     over USB serial (CDC-ACM, D027), one Pi per hardware module, their UIs on the host
     (D021);
   - the Red wayside data (R34) with `next_blocks` (R78);
   - measuring the USB round trip (G-CLK-6);
   - packaging as one executable, and the build on Windows.

   Known Red issues:
   - every Red block is two-way, so the starter switches stay normal there;
   - the `75-yard` normal leg disagrees between modules (Q5);
   - `merge_ctc_inputs` is already written for a second Track Controller.

   Plan Phase 5 with me before building it.

When agents report, review before relaying: say what you verified yourself and what you only
have from their report.
