# Prompt: Phase 5 fixes

Paste everything below the line into a new Codex session.

---

You are continuing the Track Overflow system integration on branch
`claude/quirky-fermi-sickg4`, starting at `1b64bc4`. Never change branches, and open no pull
request unless Kevin Schillinger (the user) asks for one. Phase 5 steps 1–9 and 13 were built
from `documents/phase-5-prompt.md` and are reported in
`documents/integration-handover-phase-5.md`. An independent check on 2026-10-22 found the
problems below. Kevin answered each one; this session fixes them.

## How you work

- **You are the orchestrator.** Delegate every piece of legwork to subagents running
  **sol 6.1 at medium effort**. You plan, review and validate their work (read each commit's
  `git show --stat`, re-run the key tests yourself), and report to Kevin. Say what you verified
  yourself and what you only have from an agent's report.
- **Agents share one working tree.** `AGENTS.md` forbids worktrees for agents. Give each agent a
  separate set of files, and tell every agent:
  - stage explicit paths only, never `git add -A`, and check `git diff --cached --stat`
    before committing;
  - never touch another agent's uncommitted changes;
  - if `.git/index.lock` exists, wait and retry.
- **Commits and pushes.** End commit messages with the attribution lines your environment
  requires. Put no model identifier in any repository file. Push with
  `git push -u origin claude/quirky-fermi-sickg4`, retrying only on network errors.
- **Any UI change needs Kevin's permission first.** That covers QML and the Python behind a
  window. Ask and show the exact change rather than make it.
- **`AGENTS.md` is binding.** Run its session-start steps (fetch `truth`, read `INDEX.md`, check
  the toolchain, report date/time/machine/OS, present this branch's inbox: 27 proposals).
  Truth is read with `git show` only. Proposals come only from Kevin's decisions or documents,
  and promotion is human-only. **Editing an existing proposal is allowed only where Kevin
  asked**; item 4 below is such a request.
- **Python:** project virtual environment, Python ≥ 3.10, `PySide6>=6.11`, pytest, mypy,
  flake8. Run Qt tests with `QT_QPA_PLATFORM=offscreen`.
- **Write documentation as you go**, matching each file's style.

## Read first

- `AGENTS.md`.
- `documents/phase-5-prompt.md` (decisions K1–K12).
- `documents/integration-handover-phase-5.md` and design §5.6.
- `common/hw_link/` (`protocol.py`, `agent.py`, `relay.py`, `host.py`, `transport.py`).
- `common/harness/{core.py,measure.py,supervisor.py,edges.py}`.
- `TrackCtrlHw/` README and INTEGRATION, and `TrackCtrlHw/ui/` (read only).
- Braden's design on `origin/wp2/TrackCtrl-HW-design`, already merged here as `2335197`:
  `documents/sdd/track_ctrl_hw.md` (§4 architecture, §5.3 host classes) and
  `documents/uml/track_ctrl_hw/class_host.puml` / `class_core.puml`.

## Kevin's answers of 2026-10-22, and the work

| # | Problem found | Kevin's answer | Do this |
|---|---|---|---|
| 1 | The harness core and protocol gained a `CLOCK_STATE` message (D031). The no-vital-layer proposal for both variants claimed his approval without quoting him. | "yes" to both: he approves `CLOCK_STATE`, and confirms the no-vital-layer rule covers the SW variant. | Amend those two proposals (`20261021-…` D031 and `track-controller-plc-only-both-variants`) so their provenance quotes Kevin's "yes" of 2026-10-22. Do **not** remove the SW variant's vital layer in this session: ask Kevin whether he wants that done now, and record it as an open item. |
| 2 | `python -m common.harness.measure --system` waits forever: it never passes `--test-pi`, so it waits for Pis that don't exist. The README budget recipe is broken. | "create a fix" | Give `measure.py` an explicit `--test-pi process\|pty` option. Use it for both HW modules, passing it through the way `app.py` does. Fix the README recipe. Add a test that `measure --system --test-pi process` starts and measures. Never fall back silently (K8). |
| 3 | With simulated Pis, a 10x run reaches only about 5x, with 18 slipped ticks and a mean round trip of 17–23 ms. Phase 4 measured about 5 ms. | "investigate" | Profile one tick end to end: harness → host relay → simulated agent → back. Places to look: the deferred reply, the per-transaction fsync of the journal, the `VIEW` snapshots, JSON encoding of the ~12 KB Track Controller HW output, pipe/pty buffering, and the stdio `QProcess` path. Report where the time goes, with numbers. Fix what is clearly overhead, and keep the K7 durability guarantees unless Kevin agrees to relax them. Re-measure 1x, 10x headless and 10x window with simulated Pis, and compare to Phase 4. If 10x cannot be reached without weakening a guarantee, stop and give Kevin the options. |
| 4 | The no-vital-layer proposal for both variants targets `truth/decisions/D019-wayside-runs-only-its-program.md`, the same path as Braden's own D019 proposal in `truth/_inbox/feature/TrackCtrl-Showcase-Feedback/`. | "add that it has a conflict" | Edit that proposal only (Kevin asked): add a `## Conflict` section per `AGENTS.md`, naming both entries, each one's provenance, and an owner to resolve it (Harry Tye, contract owner, with Braden). Also fix its entry key so it matches its filename. Leave Braden's proposal untouched. |
| 5 | mypy reports 5 errors in `common/hw_link`: `transport.py:71,194,199`, `relay.py:28`, `host.py:104`. The `host.py` one is a real type mismatch (`deferred_handler` dict vs Mapping). | "fix" | Fix them properly, with no blanket ignores. Run mypy (`--explicit-package-bases --disallow-untyped-defs --follow-imports=silent --ignore-missing-imports`) on `common/hw_link` and the changed harness and utils files; correct the handover's mypy claim. Clean flake8 on production code; also clear the 55 E501/E402/N802 warnings in the new test files where that matches existing practice. |
| 6 | Owners' code changed: Red-9 special cases in four layout readers (`TrackCtrlSW/track_ctrl/layout.py:440`, `TrackModel/track_model/layout.py:422`, `TrackCtrlHw/track_ctrl_hw/territory.py:187`, `common/harness/track_devices.py:128`). Braden's HW core gained cross-wayside neighbour `OCC_n` inputs, where an occupied block missing from the inputs counts as clear. | "write this to the change log for the respective modules" | Add an entry to each affected module's change log (`TrackCtrlSW`, `TrackModel`, `TrackCtrlHw`, and the harness README's change notes; create a `CHANGELOG.md` where a module has none, in `Train-Ctrl_HW/CHANGELOG.md`'s style). Give what changed, why (the commit and the decision), and the risk: "an occupied block missing from the inputs counts as clear" is a safety note for Braden and Harry. No code change for this item. |
| 7 | The track data itself. | "the track is a given data point and can not be modified" | **This supersedes part of K2.** Phase 5 commit `f27ba4e` edited `TrackModel/red_line.json` (moved `"yard"` from block 75's `next_blocks` to block 9's). Restore `red_line.json` to its course-given content, exactly as before `f27ba4e`. Keep the yard at block 9 (K2: "block 9 physically connects to the yard via a switch … block 9 is in section c") by interpreting the given file in the readers, which already carry Red-9 handling. Make all four readers agree on the unmodified file, and keep the test that enforces it. Re-check the block-9 switch legs: the readers currently take 9 as the point, 10 as NORMAL and the yard as REVERSE, with the light on 8, yet R1 is released toward 10. Make them consistent with a train leaving the yard onto 9, and record the reading as an assumption for the Track Model owner and Braden. Check every user of the yard placement still works: CTC tracking, `YARD_EXIT_BLOCKS`, the Red run. Update the K2 proposal (D028) only if it states that the file is edited: Kevin asked for this change, so record his words of 2026-10-22. |
| 8 | Red return doesn't work: R1, sent back to the yard, stops for good at 66, behind switch 52 (NORMAL), and never retires. | "fix", and "wait for real" for Red switching in the PLC programs | **These pull against each other. Do not make the test PLC programs route Red switches;** Braden's real programs will. Find out why the CTC Office routes R1 from 16 back to 9 by way of 66 rather than another way, and fix the return without switch routing in the test programs, if a correct fix exists elsewhere. Note truth `arbitration/no-automatic-reversal` and the CTC's two-way zones. If the only fix needs switch routing or a reversal the rules forbid, stop and give Kevin the options; don't pick one. |
| 9 | A missing Pi shows only "5 ready" in the log. | "yes" (the harness should name it) | While a HW host is searching for its Pi, log an event naming the module and the K5 identity it is looking for. Log it at start and then at a sensible interval. Log the matching ports found, including the case where more than one matches, which today waits silently. No UI change: events only; the operator window already lists events. Test it. |
| 10 | The Track Controller HW window's state is swapped after construction (`common/hw_link/host.py:58-68,144-148`). | "no Plug in at the core instead: give the window's existing state a RemoteTrackController in place of the local core, if his state class already accepts one, so the window stays untouched. check the wp2 code on bradens branch for refrencee" | Remove the post-construction swap. Plug a `RemoteTrackController` in at the core: build the window's existing state with it in place of the local `HwTrackController`, through a parameter the state class already has (check `TrackCtrlHw/ui/state.py` and the PR #43 code). Follow Braden's design on `origin/wp2/TrackCtrl-HW-design`: `RemoteTrackController`, `PiSerialLink` and `HarnessEndpoint` in `class_host.puml` and SDD §4/§5.3. If the state class has no such parameter, or the window builds its own state, **stop and ask Kevin**: that would be a UI change. Show him the smallest change that would allow it. |

## Before you finish

Run every suite:
- harness + utils;
- `common/hw_link`;
- Track Controller HW;
- CTC Office;
- Track Controller SW;
- Track Model;
- Train Controller, plus `main.py --check`;
- Train Model;
- the opt-in Green round trip.

Then:
- run a full-system `--test-pi process` run dispatching G1 and R1;
- run the fixed `measure --system --test-pi process` at 1x and 10x, headless and with the window;
- update the Phase 5 handover and design §5.6 (numbers, the item 7 reversal, open items);
- leave the tree clean and pushed;
- give Kevin a summary of every change, by area: commits, tests, proposals touched, and
  what is still open.

**Still open:**
- removing the SW vital layer in code (item 1);
- the Red return if it needs switches (item 8);
- the block-9 legs assumption (item 7);
- Braden's real Red programs.
