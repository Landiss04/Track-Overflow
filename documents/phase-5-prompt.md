# Prompt: Phase 5, steps 1–9 and 13 (no hardware)

Paste everything below the line into a new Codex session.

---

You are continuing the Track Overflow system integration on branch
`claude/quirky-fermi-sickg4`. Never change branches, and open no pull request unless Kevin
Schillinger (the user) asks for one. This session builds **Phase 5, steps 1–9 and 13** of the
plan below. No Raspberry Pi is working yet, so nothing in this session may depend on real
hardware: steps 10 (USB measurement), 11 (Pi provisioning) and 12 (packaging) are out of
scope.

## How you work

- **You are the orchestrator.** Delegate every piece of legwork (reading code, editing,
  testing, writing documents) to subagents running **sol 6.1 at medium effort**. You plan,
  write their prompts, review and validate their work (read each commit's
  `git show --stat`, re-run the key tests yourself), and report to Kevin. Say what you
  verified yourself and what you only have from an agent's report.
- **Agents share one working tree.** `AGENTS.md` forbids git worktrees for agents. Give each
  agent a separate set of files, and tell every agent:
  - stage explicit paths only, never `git add -A`, and check `git diff --cached --stat`
    before committing;
  - never touch another agent's uncommitted changes;
  - if `.git/index.lock` exists, wait and retry.
- **Commits and pushes.** End commit messages with the attribution lines your environment
  requires. Put no model identifier in any repository file. Push with
  `git push -u origin claude/quirky-fermi-sickg4`, retrying only on network errors.
- **UI changes need Kevin's permission, every time.** That includes QML and the Python
  behind a window (for example `TrackCtrlHw/ui/state.py` and
  `Train-Ctrl_HW/train_ctrl/backend.py`). Design so that none is needed. If one turns out to
  be unavoidable, stop and ask Kevin, showing the exact change.
- **`AGENTS.md` is binding.** At session start:
  - `git fetch origin truth`, then read `truth/INDEX.md` with `git show`;
  - check the toolchain against `truth/conventions/toolchain.md`;
  - report the date, time, machine and OS;
  - present this branch's inbox (`truth/_inbox/claude/quirky-fermi-sickg4/`), which holds 20
    proposals awaiting promotion.

  Truth is read with `git show` only; never write it into the repository. Write a proposal
  only for a normative fact decided by Kevin or a document, as a full entry in one new file
  per fact. Promotion is human-only.
- **Python:** use a project virtual environment (Python ≥ 3.10, `PySide6>=6.11`, pytest,
  mypy, flake8). Run Qt tests with `QT_QPA_PLATFORM=offscreen`.
- **Write documentation as you go**, matching each file's existing style.

## Read first

- `AGENTS.md`.
- `documents/integration-summary.md`: everything since Phase 3, the open questions and the
  20 proposals.
- `documents/system-integration-design.md` (v0.14): §1.4 rulings, §4.5 (the process model,
  including the Pis), §5.4–5.5, the §6 gaps and Appendix A.
- `documents/integration-handover-phase-4.md` and `common/harness/README.md`.
- In truth: D005, D017, D021, D022, D024 and D027.
- `TrackCtrlHw/README.md` and its `docs/`.
- In `Train-Ctrl_HW/`: `REQUIREMENTS.md` and `HARNESS_INTEGRATION.md`.

## State at the start (verified 2026-10-21 at `aa7776c`)

- **Track Controller HW** (`TrackCtrlHw/`, owner Braden; contract shard owner Harry Tye):
  - The core is pure Python with no Qt, and there is no serial, USB or Pi code.
  - The version on this branch is old. Its boundary keys blocks by `(line, section,
    block_id)`, still has `time_s`, `ctc.maintenance_mode` and `track_model.failures`, and its
    reports have no `line`, `ready` or `reason`.
  - It has three Green sample waysides, without `next_blocks`, so
    `tests/test_territory.py::SampleWaysides::test_samples_match_the_course_layout_file`
    fails. There is no Red data.
- **PR #43** (`origin/feature/TrackCtrl-Showcase-Feedback`, open, blocked) is not merged
  here.
- **Train Controller HW:** the same `Train-Ctrl_HW/train_ctrl` code runs Green today as
  `train-controller-sw`. Its fleet core has no Qt. The console (`backend.py`) reads and
  writes the train state directly, in the same process.
- **Harness:** already in place are `merge_ctc_inputs`, the per-line routing tables
  (`TRACK_CONTROLLER_FOR_LINE`, `CONTROLLER_FOR_LINE`), the Red yard exit at 9 and the
  Red switch mapping. Both HW modules still run as stubs. `utils/module_link.py` answers each
  `STEP` synchronously and cannot defer a reply.
- **Red data** (`TrackModel/red_line.json`): 76 blocks, all two-way. The yard is listed as a
  neighbour of block 75 (`75: [74, 76, "yard"]`). The switch text `75-yard` is on block 9's
  row. The readers disagree on what NORMAL means for it. **No Red train has ever run in the
  integrated system.**

## Kevin's decisions of 2026-10-21

Record each one, in his words, in design §1.4 (next ruling numbers) and in the Phase 5
handover. File one truth proposal for each fact that is normative and new.

| # | Question | Kevin's answer | What it means for this work |
|---|---|---|---|
| K1 | Go and order | Steps 1–9 and 13 now; "no hardware is functional yet so that cant be tested" | Every Pi path runs against a simulated Pi in tests. |
| K2 | Red yard (Phase 3 Q5) | "block 9 physically connects to the yard via a switch … note that block 9 is in section c" | Fix `red_line.json` so the yard joins block 9, section C, through the switch listed on block 9. Remove `"yard"` from block 75's `next_blocks` and add it to block 9's. Assume point 9, normal along the main line, reverse to the yard; record that as an assumption for the Track Model owner and Braden to confirm. The leftover `75` in the switch text also goes to them. All three readers (Track Model, harness `track_devices`, Track Controller HW `territory`) must agree, enforced by a test. File a proposal. |
| K3 | PR #43 | "merge into this branch not devlopment leave the pr unmerged" | `git merge origin/feature/TrackCtrl-Showcase-Feedback` into this branch: a merge commit, never a rebase. Do not merge, close or comment on PR #43. |
| K3b | Vital layer | "the vital layer has been removed. everything is done by the plc code." | The HW variant has no vital layer (PR #43, its D019 proposal). Every safety rule lives in the PLC programs, so the Red programs must carry the speed caps, separation and crossing rules themselves. The SW variant still has a vital layer: do not change it, and ask Kevin whether this decision covers SW too. |
| K5 | Pis and USB identity | "Pi 5 set up by module owners. assign the both usb ident strigns" | Raspberry Pi 5, USB device mode on its USB-C port. Assign one identity per module (manufacturer, product, serial number, VID:PID), find each Pi by it, document it, and file a proposal. Suggested: manufacturer `Track Overflow`; product `Track Overflow Track Controller HW` / `Track Overflow Train Controller HW`; serial `TO-TRACK-CTRL-HW-01` / `TO-TRAIN-CTRL-HW-01`; VID:PID `1d6b:0104`, the Linux composite-gadget default. Owners set up the Pis; you write and document the gadget and agent setup without running it on hardware. |
| K6 | Pi-link additions | "accept" | `HELLO` (protocol, module, agent version/hash, session), `ACTION`/`ACK` (window actions applied before the next `STEP`) and `VIEW` (a display snapshot, at most every 100–200 ms), on the host-to-Pi link only. File a proposal as an additive extension of D027. |
| K7 | Unplug or reboot recovery | "approved" | Hold the reply (the harness pauses and names the module after 1 s). Reconnect by USB identity, redo `HELLO`, replay the recorded loads, re-send the pending `STEP`, and log every step. The Pi answers a repeated `STEP` from its cache by (id, tick) and never steps twice. File a proposal. |
| K8 | Pi missing at launch | "the whole clock should wait this will never happen" | No fallback. The clock waits for every module, as now. A simulated Pi exists only for tests and development, chosen explicitly, never automatic. Do not add a production `--hw-sim` path that hides a missing Pi. |
| K9 | A Pi that can't hold 10x | "agreed test when implemented" | Measure once hardware works (step 10, not now). Now, record per-tick bytes and core step time from the simulated runs, to size the risk. |
| K10 | Windows builder; separate installs | "kick this down the road" | Out of scope. Record as deferred. |
| K11 | Gains after a Pi reboot | "they should never loose connection mid run but add logic to check if connections are lost while the clock as running and if they are lost while the clock is running then the gains should be resent" | Detect a lost Pi connection. If it was lost while the clock was running, re-send the engineer's gains when it reconnects. If it was lost while paused, do not auto-apply gains (D024). Log both cases. File a proposal. |
| K12 | Python behind the windows | "any ui changes require permission" | See "How you work". Prefer remote adapters passed in through constructor parameters that already exist (`TrackControllerState(controller=…)`, `ConsoleBackend(fleet=…)`), so no window file changes. |

## The work, in order (steps 1–9, then 13)

**Architecture (Option A, decided by K6).**
- **Host process.** Each HW module (`--module track-controller-hw`,
  `--module train-controller-hw`) runs a host process. It is an ordinary harness module: it
  shows the window on the host (D021) and relays the harness's messages to its Pi.
- **Pi agent.** The agent on the Pi runs the module's Qt-free core, using the Python
  standard library plus `utils/harness_protocol.py`. It opens `/dev/ttyGS0` raw, echo off,
  and steps once per `STEP`. It never keeps time; the harness owns the clock (D017).
- **Unchanged:** the harness core, the protocol to modules and the other modules.

1. **Merge PR #43 into this branch (K3).**
   - Re-run the Track Controller HW suite.
   - Acceptance: it passes, apart from the known sample-wayside test; reports carry `line`,
     `ready` and `reason`; there is no vital layer.
2. **Fix the known failing test (R78).** Add `next_blocks` to the Green sample waysides, as
   exact cuts of `green_line.json`.
   - Acceptance: the Track Controller HW suite passes in full.
3. **Red data.**
   - Apply K2 to `red_line.json`, and update anything that read the old yard placement.
   - Add Red wayside databases covering all 76 blocks exactly once, with `next_blocks` (R34,
     R78), and Red PLC programs that carry every safety rule (K3b). Every Red block is
     two-way, so switches stay NORMAL unless a program routes them.
   - The wayside split and the programs are Braden's (K4, not yet decided): mark these as
     integration test copies for him to replace or approve.
   - Acceptance: each file matches `red_line.json` block for block; each loads into the HW
     core; each program compiles with no errors; all three readers agree on every Red
     switch's NORMAL and REVERSE legs.
4. **Harness mappings for the HW Track Controller.** Write pure functions in the harness for
   CTC→HW, Track Model→HW (sections from `BlockNames`), HW→Track Model and HW→CTC. The HW
   module's `time_s` comes from the step's simulation time. Choose the mapping by variant in
   `edges.py`.
   - Acceptance:
     - contract tests feed each mapping into the HW module's own decoder, and from its own
       encoder;
     - `merge_ctc_inputs` joins the Green and Red reports;
     - Red's `WAYSIDES_READY` comes from the HW outputs.
5. **Register the Train Controller HW** (`train-controller-hw` in the module process and in
   `track_overflow.py`). Wire both HW modules behind an option until step 9.
   - Acceptance: Red trains reach only the HW controller, and both controllers' commands are
     merged into the Train Model's inputs.
6. **A Red run in one process, without serial**, following the
   `test_harness_train_loop.py` pattern.
   - Acceptance:
     - the Red waysides become ready;
     - `--dispatch R1:Red:16` releases R1 at 9, and each module takes it a tick apart;
     - R1 runs 9 to 16 with no emergency brake and no pickup-failure latch, and dwells 45 s;
     - G1 on Green alongside is unaffected.
   - Follow-up: Red return to yard and retirement at 9, and whether a train can turn back on
     Red. Report what happens.
   - Record per-tick output bytes and the core step time (K9 groundwork).
7. **The Pi-link protocol and the Pi agent (K6, K7).** Pure functions plus a loop over any
   byte stream.
   - Acceptance: unit tests with chunked and split streams, non-JSON lines (modem `AT`
     probes are skipped and logged), a version mismatch, a repeated `STEP` answered from the
     cache, and `QUIT` resetting the session.
8. **Host relay processes and a simulated Pi.**
   - **Transport:** an abstraction over `QSerialPort`, found by the K5 identity (PySide6
     6.11 ships QtSerialPort, so no pyserial on the host); `QProcess` stdio to a local
     agent; and a Linux pty for the raw-mode path.
   - **Simulated agent:** `--delay-ms`, `--jitter-ms`, `--drop-after N` and
     `--reboot-at-tick N` for fault injection.
   - **`ModuleLink`:** add a deferred-reply mode.
   - **Windows:** remote adapters for both windows, with no UI change (K12).
   - **Recovery:** implement K7, and K11's gain re-send while running.
   - **Tests:** an explicit test-only option selects the simulated Pi (K8).
   - Acceptance:
     - the real-process system test passes with all seven modules real and simulated Pis,
       running G1 and R1;
     - an injected unplug or reboot gives `REPLY_LATE`, then `LATE_REPLY_RECEIVED` after the
       replay, with no double step;
     - gains are re-sent only after a loss while running;
     - window actions behave as they do locally;
     - stderr is empty.
9. **Make both HW variants real modules by default**, finding each Pi by its K5 identity,
   with no fallback (K8).
   - Acceptance: argument tests for every mode; `--stubs-only` unchanged; the default
     harness and module suites green on the simulated Pi in tests.
13. **Documents.**
    - Design §5.6 "Phase 5 as built (steps 1–9)", with K1–K12 as new rulings.
    - A Phase 5 handover in the same form as the Phase 4 one.
    - The harness README.
    - An integration guide for `TrackCtrlHw`.
    - Pi setup instructions for the module owners (USB gadget, systemd unit, the K5
      identity), marked untested on hardware.
    - Truth proposals for K2, K5, K6, K7 and K11, plus K3b if Kevin confirms its scope.
    - Mark steps 10–12 as not started, waiting for working Pis (K9, K10).

## Questions still open (ask Kevin, don't decide)

- Does "the vital layer has been removed" cover the SW variant too?
- The exact NORMAL leg of the block-9 switch, and the stray `75` in its text: confirm with
  the Track Model owner and Braden.
- K4: the Red wayside split and who writes the final Red PLC programs (Braden).

Owner questions that are still open are listed in `documents/integration-summary.md`.

## Before you finish

Run every suite the work touches:
- harness;
- utils;
- CTC Office;
- Track Controller SW;
- Track Controller HW;
- Track Model;
- Train Controller, plus its `main.py --check`;
- Train Model;
- the opt-in Green round trip (`TRACK_OVERFLOW_ROUND_TRIP=1`).

Report the numbers. Leave the tree clean and pushed. Give Kevin a summary of every change,
by area: commits, tests, proposals filed, open questions.
