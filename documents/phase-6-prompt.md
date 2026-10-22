# Prompt: Phase 6 (DRAFT)

**Draft, 2026-10-22. Settle the scope questions below before handing this to Codex.** It
assumes the Phase 5 fixes in `documents/phase-5-fixes-prompt.md` are complete and pushed.

Scope questions for Kevin (the recommendation is marked):

1. Phase 6's goal: **(recommended) Iteration 3 readiness on 2026-11-12**, with part B kept ready
   for when the Pis work; or the hardware bring-up first; or both at once.
2. Part B (Phase 5 steps 10–11, the Pis): include it now, or wait until a module owner says a
   Pi 5 works?
3. Multiple trains in Part C: **(recommended) two trains per line on Green and Red**, or more?
4. Windows packaging (Phase 5 step 12, K10 "kick this down the road"): still deferred?

Paste everything below the line into a new Codex session.

---

You are continuing the Track Overflow system integration on branch
`claude/quirky-fermi-sickg4`. Never change branches, and open no pull request unless Kevin
Schillinger (the user) asks for one. Phases 0–5 are built, and the Phase 5 fixes are done (see
`documents/phase-5-fixes-prompt.md` and the updated `documents/integration-handover-phase-5.md`).
The whole system runs as seven processes. Green runs on the Track Controller SW and the Train
Controller SW. Red runs on the Track Controller HW and the Train Controller HW, against
simulated Raspberry Pis (`--test-pi process|pty`), because no real Pi works yet.

**Phase 6 goal:** be ready for the Iteration 3 System Group Review on **2026-11-12**. Its rubric
gives 35 points to "Do the Sub-systems Communicate" and 35 to "Does the Train Move from Yard
to Destination Block". Keep the hardware bring-up (Part B) ready to run the day a Pi works.
Iteration 4, the final, is on 2026-12-10.

## How you work

- **You are the orchestrator.** Delegate all legwork to subagents running **sol 6.1 at medium
  effort**. Plan, review and validate their work (read each commit's `git show --stat`, re-run
  the key tests yourself), and report to Kevin what you verified yourself and what you only
  have from an agent's report.
- **Agents share one working tree** (`AGENTS.md` forbids worktrees for agents). Give each agent
  a separate set of files, and tell every agent:
  - stage explicit paths only, never `git add -A`, and check `git diff --cached --stat`;
  - never touch another agent's uncommitted changes;
  - if `.git/index.lock` exists, wait and retry.
- **Commits and pushes.** End commit messages with the attribution lines your environment
  requires. Put no model identifier in any repository file. Push with
  `git push -u origin claude/quirky-fermi-sickg4`, retrying only on network errors.
- **Any UI change needs Kevin's permission first.** That covers QML and the Python behind a
  window. Ask and show the exact change.
- **The track data is given and can't be modified** (Kevin, 2026-10-22). Interpret it in the
  readers; never edit `TrackModel/*_line.json`.
- **Red switching** waits for Braden's real PLC programs (Kevin, 2026-10-22: "wait for
  real"). Don't make the test programs route Red switches.
- **`AGENTS.md` is binding:** session-start steps, truth read with `git show` only, proposals
  only from Kevin's decisions or documents, promotion human-only, existing proposals edited
  only when Kevin asks.
- **Python:** project virtual environment; `QT_QPA_PLATFORM=offscreen` for Qt tests. Two
  untracked files from earlier work (`common/harness/tests/adversarial_probe.py`,
  `documents/central-harness-adversarial-2026-10-20.md`) stay untouched.
- **Write documentation as you go**, matching each file's style.

## Read first

- `AGENTS.md`.
- `documents/integration-summary.md` and its post-summary decisions.
- `documents/integration-handover-phase-4.md` and `integration-handover-phase-5.md`.
- `documents/system-integration-design.md`: §1.4 rulings, §1.5 open questions, §5.5–5.6, the
  §6 gaps (G-CLK-6, G-HW-*, G-RUN-*, G-LIFE-*).
- `common/harness/README.md`.
- `documents/phase-5-prompt.md` and `phase-5-fixes-prompt.md` for decisions K1–K12 and the
  2026-10-22 answers.

## Part A: Iteration 3 readiness (no hardware needed)

1. **The review scenario, scripted and repeatable.** One command runs the graded run:
   - Green waysides ready (starters loaded) and gains set (test options);
   - G1 dispatched from the yard to a Green station;
   - R1 dispatched from block 9 to a Red station, on the HW variants with simulated Pis.

   Both trains must stop at their stations with doors open, with no fault events and seven
   clean exits. Dispatch may be manual or by schedule; both are supported (R84). Add an
   end-to-end test for it, and a checklist for a person to run it with windows on a display.
   The check: the subsystems communicate, and each train moves from the yard to its
   destination block.
2. **Real windows under load (G-CLK-6).** Measure `measure --system --test-pi process` at 1x
   and 10x with every window visible on a real display, not offscreen, on the review machine
   if Kevin names one. Report against the Phase 4 and Phase 5 tables. If 10x falls short, find
   the slow window or process, profile it, and propose fixes. Any fix that touches a UI file
   goes to Kevin first.
3. **Several trains** (scope question 3): two trains per line under the CTC Office's schedule
   in automatic mode, with exclusive authority, separation and dwell all holding.
   - No emergency brake, no pickup latch, no protocol fault.
   - Exercise the Green follower case (Landis's open question at 75/76, while a train stands
     at 77 bound for 101). Report what happens; don't change the CTC's or Track Controller's
     rules without the owners.
   - Add the scenarios as tests (opt-in if they are slow).
4. **The full system as one Linux build.** Extend the PyInstaller recipe to every module:
   - `TrackCtrlHw` and its data;
   - `common/hw_link`;
   - the Pi agent bundle, with its hash checked at `HELLO`.

   Smoke-test the build from outside the checkout with simulated Pis: both lines dispatched,
   seven clean exits. Windows packaging stays deferred (K10) unless Kevin says otherwise.
5. **Event log and operator readiness.** Confirm a person can follow the run from the
   harness window and the CSV log alone: readiness per line, each train added, missing Pis
   named (the Phase 5 fix), faults. Fill any gap with log events only; no UI change without
   permission.
6. **Review documents.** A one-page run book for the review (setup, the command, what to
   show, recovery if something stalls), and the design document brought up to date.

## Part B: hardware bring-up (Phase 5 steps 10–11), only when a Pi works

Do Part B only once a module owner reports a Raspberry Pi 5 set up (K5: "Pi 5 set up by module
owners"). Until then, keep its scripts and documents ready and untested on hardware.

1. **Provisioning check.** USB device mode on the Pi 5's USB-C port. Each module's K5 identity
   (manufacturer `Track Overflow`, product, serial `TO-TRACK-CTRL-HW-01` /
   `TO-TRAIN-CTRL-HW-01`, VID:PID `1d6b:0104`) shows as `ttyACM*` on Linux and as a COM port
   on Windows (built-in usbser, no install, no admin). The agent answers `HELLO` within the
   20 s startup timeout after power-on.
2. **USB round trip (G-CLK-6, K9 "agreed test when implemented").**
   - First an echo test at 1, 10 and 20 KB payloads at 100 per second.
   - Then the agent's step time on the Pi with recorded Red inputs.
   - Then `measure --system` with real Pis.

   Report a table like §5.5's. If 10x is not reached, give Kevin the options (accept a slower
   time, use a faster Pi, or shrink the per-tick data on the Pi link) and let him choose.
3. **Real faults (K7, K11).** Unplug and replug under a running clock, and reboot a Pi. Expect:
   - `REPLY_LATE`, then recovery and `LATE_REPLY_RECEIVED`;
   - no double step;
   - gains re-sent only if the connection was lost while the clock was running;
   - the missing-Pi event naming the module.
4. **Full system with real Pis** on Linux, then on Windows if a Windows host is available.

## Questions to put to Kevin and owners as they come up (don't decide)

- Removing the SW vital layer in code, now that K3b covers both variants (Harry Tye).
- Braden's real Red PLC programs and wayside split, replacing the test copies; Red switching,
  return and turnback once they exist.
- The Red block-9 NORMAL-leg assumption (Track Model owner, Braden).
- The cross-wayside occupancy rule, where "an occupied block missing from the inputs counts
  as clear" (Braden, Harry).
- Earlier open owner questions: ticket rate (Q-P4-7), Track Model light-ahead B1, heaters
  (D026), and the Green starter and follower decisions (Harry, Landis).
- The 31 pending truth proposals (27 on this branch, 4 from PR #43), for Kevin to review and
  promote.

## Before you finish

Run every suite (harness and utils, `common/hw_link`, Track Controller HW and SW, CTC Office,
Track Model, Train Controller with `main.py --check`, Train Model), the opt-in Green round trip
and the new multi-train and review-scenario tests. Write a Phase 6 handover and update the
design (§5.7). Leave the tree clean and pushed, and give Kevin a summary of every change by
area: commits, tests, measurements, proposals, open questions.
