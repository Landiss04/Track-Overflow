# Prompt: Phase 6

Written 2026-10-22, after the Phase 5 fixes were verified (`36911aa..b81e213`). Kevin's scope
answers of 2026-10-22 are built in. Paste everything below the line into a new Codex session.

---

You are continuing the Track Overflow system integration on branch
`claude/quirky-fermi-sickg4`. Never change branches, and open no pull request unless Kevin
Schillinger (the user) asks for one.

Phases 0–5 and the Phase 5 fixes are done. See:
- `documents/phase-5-fixes-prompt.md`;
- the updated `documents/integration-handover-phase-5.md`;
- design §5.6.

The whole system runs as seven processes:
- Green runs on the Track Controller SW and the Train Controller SW.
- Red runs on the Track Controller HW and the Train Controller HW, against simulated Raspberry
  Pis (`--test-pi process|pty`), because no real Pi works yet.

**Phase 6 goal (Kevin, 2026-10-22):** "be prepared for iteration 3 full system integration".
The Iteration 3 System Group Review is on **2026-11-12**. Its rubric gives 35 points to "Do the
Sub-systems Communicate" and 35 to "Does the Train Move from Yard to Destination Block".

The Pis are not done yet. Kevin: "include them as much as possible so that it is turnkey for
when they are done. do not repeat code for this reuse as much as possible so that changes can be
applied in one place."

## Kevin's answers of 2026-10-22

| Topic | Kevin's answer | What it means here |
| --- | --- | --- |
| Goal | "be prepared for iteration 3 full system integration" | Part A. |
| Pis | "include them as much as possible so that it is turnkey" | Part B: everything ready except the hardware itself. |
| Reuse | "do not repeat code … so that changes can be applied in one place" | Applies to all work. See below. |
| Trains | "2+ trains must be able to run on each line" | Nothing hard-codes a train count. Test 2 and 3 trains per line. |
| 10x speed | "wait for pi measurements" | No speed work this phase. Measure and record only. |
| Red return | Reuse Braden's switch logic | The Red test programs route switches in the pattern of Braden's Green programs. This supersedes the earlier "wait for real" for Red switching. |
| Braden's real programs | "Our branch's (PR #43)" | `TrackCtrlHw/data/plc/green_wayside_1..3.plc` on this branch are the real ones; the older copies on `development` are not. `TrackCtrlHw/data/plc/examples/` only demonstrates warnings and errors. |
| Fix-check findings | "yes" | Part A item 7. |
| Windows packaging | "deffered" | Out of scope (K10). |

## How you work

- **You are the orchestrator.** Delegate all legwork to subagents running **sol 6.1 at medium
  effort**. Plan, review and validate their work: read each commit's `git show --stat`, and
  re-run the key tests yourself. Report to Kevin what you verified yourself, and what you only
  have from an agent's report.
- **Agents share one working tree.** `AGENTS.md` forbids worktrees for agents. Give each agent
  a separate set of files, and tell every agent:
  - stage explicit paths only, never `git add -A`, and check `git diff --cached --stat`;
  - never touch another agent's uncommitted changes;
  - if `.git/index.lock` exists, wait and retry.
- **Commits and pushes:**
  - End commit messages with the attribution lines your environment requires.
  - Put no model identifier in any repository file.
  - Push with `git push -u origin claude/quirky-fermi-sickg4`, retrying only on network errors.
- **Reuse, one place for each change (Kevin).** Before writing anything new, look for what
  already exists and extend it. In particular:
  - The real-Pi and simulated-Pi paths share one implementation. Only the transport differs:
    one agent, one relay, one host and one protocol, in `common/hw_link`.
  - The Track Controller HW and Train Controller HW share every piece of Pi plumbing.
  - Bring-up and measurement tools reuse `common/hw_link` and `common/harness/measure.py`;
    they don't copy them.
  - Scenario scripts reuse the harness's existing options (`--dispatch`, `--schedule`,
    `--load-starters`, `--test-pi`, `--speedup`).
  - If you find existing duplication on the Pi path, fold it into one place.
  - Report every place you removed or avoided duplication.
- **Any UI change needs Kevin's permission first.** That covers QML and the Python behind a
  window. Ask and show the exact change.
- **The track data is given and can't be modified** (Kevin, 2026-10-22). Interpret it in the
  readers; never edit `TrackModel/*_line.json`.
- **`AGENTS.md` is binding:**
  - follow its session-start steps;
  - read truth with `git show` only;
  - write proposals only from Kevin's decisions or documents;
  - promotion is human-only;
  - edit existing proposals only where Kevin asks (item 7 below is such a request).
- **Python:**
  - Use the project virtual environment, and set `QT_QPA_PLATFORM=offscreen` for Qt tests.
  - Leave untracked files from earlier work untouched.
  - One Train Model UI test is known to be flaky:
    `test_ui_sync.py::test_input_list_scrolls_in_place_and_outputs_are_trimmed`. It fails
    sometimes on both the old and new code and passes alone. Report it if it fails; never
    skip it.
- **Write documentation as you go**, matching each file's style.

## Read first

- `AGENTS.md`.
- `documents/integration-summary.md` and its post-summary decisions.
- `documents/integration-handover-phase-4.md` and `integration-handover-phase-5.md`.
- `documents/system-integration-design.md`:
  - §1.4 rulings and §1.5 open questions;
  - §5.5–5.6;
  - the §6 gaps (G-CLK-6, G-HW-*, G-RUN-*, G-LIFE-*).
- `common/harness/README.md`.
- `documents/phase-5-prompt.md` and `phase-5-fixes-prompt.md`, for decisions K1–K12 and the
  answers of 2026-10-22.
- `common/hw_link/`, and the `TrackCtrlHw/` and `Train-Ctrl_HW/` READMEs.
- Braden's design: `documents/sdd/track_ctrl_hw.md` and `documents/uml/track_ctrl_hw/`.

## Part A: Iteration 3 full-system readiness

1. **The review scenario, scripted and repeatable.** One command runs the graded run:
   - the Green waysides become ready (starters loaded) and their gains are set (test options);
   - G1 is dispatched from the yard to a Green station;
   - R1 is dispatched from block 9 to a Red station, on the HW variants with simulated Pis.

   Both trains must stop at their stations with doors open. There must be no fault events,
   and the run must end with seven clean exits. Both manual and scheduled dispatch must work
   (R84). Build the scenario from the existing options; don't write a second launcher. Add an
   end-to-end test, and a checklist for a person to run it with windows on a display.
2. **Red return and Red switching.** Kevin chose to reuse Braden's switch logic.

   Today R1, sent back to the yard, stops for good at 66. The reason:
   - The test programs only hold switch 52 where it is.
   - The way back 16→17…66→52…9 needs 52 REVERSE.
   - The direct way back (16→15) would be an automatic reversal, which
     `arbitration/no-automatic-reversal` forbids.

   Give the three Red test programs
   (`TrackCtrlHw/data/plc/red_wayside_{1,2,3}_integration_test.plc`) switch routing in the
   same pattern as Braden's Green programs (`green_wayside_1..3.plc` on this branch):
   - obey the CTC Office while it commands a switch (`CTCSW_n`, `CTCREV_n`);
   - otherwise route automatically from the wayside's own inputs (occupancy, closures), as his
     programs do (`AUTO_12`, `WANT_28`). Route so that a train the CTC Office sends back
     through 52 toward the yard gets the route;
   - lock a switch where it reports while a train is on its points;
   - keep the signals following the route.

   Do this for every Red switch, not only 52. Constraints:
   - Keep his structure and naming. Don't invent a second style.
   - The programs stay test copies for Braden to replace or approve.
   - Keep the wayside split (Red-1: 1–24 and 73–76; Red-2: 25–45 and 67–72; Red-3: 46–66).
   - Keep the no-automatic-reversal rule and the block-9 reading (point 9, NORMAL 8, REVERSE
     yard, light on 10).
   - If routing a switch needs an input the HW core does not give a program today, stop and
     ask Kevin.

   Then:
   - R1 returns to the yard and retires;
   - the Red outbound runs still work;
   - add tests for both;
   - record the change in `TrackCtrlHw/CHANGELOG.md` with Braden as reviewer.
3. **Two or more trains per line.** Nothing may hard-code a train count. Run 2 and 3 trains
   per line on Green and Red under the CTC Office's schedule in automatic mode, and show that
   exclusive authority, separation and dwell all hold:
   - no emergency brake, no pickup latch, no protocol fault;
   - also exercise the Green follower case: Landis's open question at 75/76, while a train
     stands at 77 bound for 101. Report what happens. Don't change the CTC's or Track
     Controller's rules without the owners;
   - add the scenarios as tests (opt-in if they are slow).
4. **Speed: measure only (Kevin: "wait for pi measurements").** Run `measure --system
   --test-pi process` at 1x and 10x, headless and with every window visible on a real display.
   Use the review machine if Kevin names one. Record the numbers against the Phase 4 and
   Phase 5 tables in the handover. Don't optimize for 10x this phase.

   The Phase 5 fix check measured:
   - about 3.6–4.3x at 10x on a 4-core cloud machine, against the handover's 9.69x on
     kevin-framework;
   - startup of about 2 s, against the handover's 0.5 s.

   Explain the difference. Correct the handover table, which reports 1,455 of 1,502 ticks done
   yet "zero slipped".

   Also:
   - Make `measure --system` without `--test-pi` say what it is waiting for, instead of
     waiting silently. Show the existing `PI_SEARCH` events or a one-line hint, from one place
     in the code.
5. **The full system as one Linux build.** Extend the PyInstaller recipe to every module:
   - `TrackCtrlHw` and its data;
   - `common/hw_link`;
   - the Pi agent bundle, with its hash checked at `HELLO`.

   Smoke-test the build from outside the checkout with simulated Pis: both lines dispatched,
   and seven clean exits. Windows packaging stays deferred (Kevin: "deffered").
6. **Event log and operator readiness.** Confirm a person can follow the run from the harness
   window and the CSV log alone:
   - readiness per line;
   - each train added and retired;
   - missing Pis named;
   - faults.

   Fill any gap with log events only. Make no UI change without permission.
7. **Findings from the Phase 5 fix check (Kevin: "yes").**
   - **CTC Office change log.** Commit `5d51051` hard-codes Red `to_yard` to block 9 in
     `CTC-Office/ctc/track_layout.py:120-121`. Add an entry to the CTC Office change log
     (create `CTC-Office/CHANGELOG.md` in `Train-Ctrl_HW/CHANGELOG.md`'s style if none
     exists), and list the change for the CTC Office owner's review.
   - **D028.** Revert the proposal's wording beyond recording Kevin's words of 2026-10-22.
     Kevin asked for this. That means:
     - restore its "Unconfirmed interpretation" section;
     - stop calling K2 a "source-file edit instruction";
     - keep reader-interpretation wording out of the normative text, and put it in a
       labelled assumption section;
     - keep a heading rename (D028 or D031) only where it makes the entry key match the
       target filename (`AGENTS.md`: "the filename is the entry key"); otherwise restore the
       heading.
   - **Track Model guard.** Limit the `_check_directions` change
     (`TrackModel/track_model/layout.py:331`, which dropped the `from_yard` guard) to the
     Red block-9 reading. Keep the guard for every other switch and line, and add a test that
     it still rejects a bad layout on Green. Record the change in `TrackModel/CHANGELOG.md`.
   - **flake8 wording.** Correct the handover's "Production flake8 passes": it holds only
     with the repo's existing N815 convention for Qt signals ignored. Say so.
8. **Review documents.** Write:
   - a one-page run book for the review: setup, the command, what to show, and how to recover
     if something stalls;
   - an update of the design document.

## Part B: Pis turnkey, without hardware

No Pi works yet. Make the day a Pi works a matter of plugging in and running scripted checks,
with no new code. Everything here reuses `common/hw_link` and `measure.py`. Test everything
that can be tested without hardware against the simulated Pis (`--test-pi pty` exercises the
serial path).

1. **Provisioning, scripted and documented.** One setup recipe for the Pi 5, shared by both
   HW modules and parameterized by module. It covers:
   - USB device mode on the USB-C port;
   - the K5 identity:
     - manufacturer `Track Overflow`;
     - product;
     - serial `TO-TRACK-CTRL-HW-01` or `TO-TRAIN-CTRL-HW-01`;
     - VID:PID `1d6b:0104`;
   - installing the agent bundle;
   - starting the agent at boot so it answers `HELLO` within the 20 s startup timeout.

   Add a host-side check command that reports, from one place, whether each identity shows up:
   `ttyACM*` on Linux, a COM port on Windows (built-in usbser).
2. **USB round-trip checks, ready to run (G-CLK-6, K9 "agreed test when implemented").**
   Provide these as commands, run now against simulated Pis:
   - an echo test at 1, 10 and 20 KB payloads at 100 per second;
   - the agent's step time with recorded Red inputs;
   - `measure --system` against real Pis.

   They must produce a table like §5.5's. The 10x decision waits for these real numbers. Then
   give Kevin the options: accept a slower time, use a faster Pi, or shrink the per-tick data
   on the Pi link.
3. **Fault checks, ready to run (K7, K11).** Write a checklist and a script for each check,
   tested now with simulated Pis where possible (kill and restart the simulated agent; drop
   the pty). The checks: unplug and replug while the clock runs, and reboot a Pi. Expected:
   - `REPLY_LATE`, then recovery and `LATE_REPLY_RECEIVED`;
   - no double step;
   - gains re-sent only if the connection was lost while the clock was running;
   - the missing-Pi event naming the module.
4. **A bring-up run book** for the module owners (K5: "Pi 5 set up by module owners"). It
   gives the order of the checks above, the expected output of each, and what to send back.
   It ends with the full system on real Pis on Linux. Windows comes later, with packaging.

## Questions to put to Kevin and owners as they come up (don't decide)

- Removing the SW vital layer in code, now that K3b covers both variants (Harry Tye; Kevin
  kept this open).
- Braden's review of the Red test programs' switch routing (item 2), and his real Red programs
  and wayside split if he writes them.
- The Red block-9 reading (point 9, NORMAL 8, REVERSE yard, light on 10), for the Track Model
  owner and Braden.
- The cross-wayside occupancy rule, where "an occupied block missing from the inputs counts as
  clear" (Braden, Harry).
- The CTC Office's Red `to_yard` change (item 7), for the CTC Office owner.
- Earlier open owner questions:
  - the ticket rate (Q-P4-7);
  - the Track Model light-ahead issue B1;
  - heaters (D026);
  - the Green starter and follower decisions (Harry, Landis).
- The pending truth proposals, on this branch and the 4 from PR #43, for Kevin to review and
  promote.

## Before you finish

Run every suite:
- harness and utils;
- `common/hw_link`;
- Track Controller HW and SW;
- CTC Office;
- Track Model;
- Train Controller, with `main.py --check`;
- Train Model;
- the opt-in Green round trip;
- the new review-scenario, Red-return, multi-train and Pi-readiness tests.

Phase 5 fix-check baseline at `b81e213`:

| Suite | Passed |
| --- | --- |
| Harness + utils | 260 |
| `common/hw_link` | 33 |
| Track Controller HW | 80 |
| CTC Office | 261 |
| Track Controller SW | 213 |
| Track Model | 310 |
| Train Controller HW | 23 |
| Train Controller SW | 24 |
| Train Model | 878, plus the flaky one |
| Green round trip | 5 |

Then:
- write a Phase 6 handover and update the design (§5.7);
- leave the tree clean and pushed;
- give Kevin a summary of every change, by area: commits, tests, measurements, duplication
  removed, proposals, and open questions.
