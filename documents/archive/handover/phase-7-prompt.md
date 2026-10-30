# Prompt: Phase 7

Written 2026-10-24 from Kevin's post-Phase-6 answers. Paste everything below the line
into Codex. Preparing this prompt did not implement or test the build work.

---

Continue Track Overflow integration on `claude/quirky-fermi-sickg4`. Never change branches,
create worktrees, discard work or open a PR unless Kevin asks. Read `AGENTS.md`, complete
its session-start checks, including the truth fetch and INDEX read. Also run
`git fetch origin claude/quirky-fermi-sickg4` and verify HEAD is `f6ed1a1` or a descendant
without switching branches. Report unexpected state; do not merge, reset or rebase
concurrent changes without authorization.

Read `documents/session-handover-2026-10-22.md`, then `documents/module-owner-review.md`
(the single current owner-review queue), `documents/integration-handover-phase-6.md`,
`documents/review-runbook.md` and `documents/review-scenario-evidence-2026-10-22.md`.
Historical results belong to their recorded revisions and hosts, not this phase.

## How you work

You are the orchestrator. Delegate legwork to **sol 6.1 medium effort** subagents; plan,
review and validate. Assign disjoint files in the shared working tree. Stage explicit
paths only, inspect `git diff --cached --stat`, never touch another agent's uncommitted
work, and wait/retry on `.git/index.lock`. Inspect each commit's `git show --stat` and
rerun key checks yourself; distinguish direct verification from agent reports.

Use the project venv and offscreen Qt for tests. Preserve all user work, including:
`TrainModel/docs/architecture-drawio-prompt.md`, `class-diagram-supplemen-prompt.md` and
`uml-sequence-prompt.md` in that directory; `common/harness/tests/adversarial_probe.py`;
and `documents/central-harness-adversarial-2026-10-20.md`.
Never edit `TrackModel/*_line.json`. Any UI change (including Python behind a window)
needs Kevin's prior approval for that exact change. Reuse existing harness options and
shared `common/hw_link`; real and simulated Pis differ only in transport. No 10x
optimization before real-Pi measurements. Windows packaging remains deferred.
Read facts from fetched `origin/truth` only; proposals are not facts. Only humans promote
or delete inbox proposals. Do not edit/rename/renumber/withdraw existing proposals.
New normative decisions require full-entry proposals with checked aliases and provenance,
committed and pushed that session. Keep plans, status and results out of truth.

## Kevin's decisions, 2026-10-24

- Prior neighbor `CLOSED_n` approval: **"yes"**. Braden acceptance: **"he didnt i did.
  ensure it is documented"**. Attribute approval to Kevin; Braden remains required reviewer.
- Functional review 1x, `TIME_SLIPPED` retained as fault, 10x measured separately:
  **"yes option a is better"**. Review host: **"for now the review will happen on this
  machine"**, identified that session as `kevin-framework`.
- Human collision recommendation: **"ues"** — consolidate D033; withdraw D034's Phase6
  scope plan, retain authoritative Green; retain both D035 policies and renumber one.
  Record this recommendation; agents do not perform deletion, renumbering or promotion.
- CTC findings: **"give a wriet up of the exact issues found"**; carryovers: **"write them
  up for module owner review"**; **"put the ctc and other module owner review things in
  the same place"**. Keep the shared review file current; do not message owners.
- Shared HELLO helper, explicit Braden required reviewer and portable runbook path:
  **"approved"**.

## Build scope

1. Run manual and scheduled process review tests at **1x**, with sufficient bounded
   wall time. Retain every safety/protocol fault assertion including `TIME_SLIPPED`,
   station stops, platform-side doors, continuous 45-s dwell and seven clean exits.
   Reuse the process runner. Do not weaken unresolved multi-train probes.
2. Make the runbook's functional recipe explicitly 1x. Replace fixed `/home/kevin/...`
   Python with portable project-venv selection or caller-supplied interpreter. Identify
   provisional host `kevin-framework`; document optional 10x measurement separately.
3. Consolidate HELLO identity/protocol/session/version/hash validation in one helper.
   Preserve relay boot/reboot checks and caller-specific diagnostics. Test valid replies
   and each rejected identity field, including relay's boot requirement. Reuse protocol
   facilities; do not add another transport, host, agent or provisioning path.
4. Name Braden explicitly as required reviewer in `TrackCtrlHw/CHANGELOG.md`; document
   Kevin's approval before neighbor-input implementation without claiming Braden accepted.
   Keep CTC and other owner findings in `module-owner-review.md`, linked elsewhere.
   CTC/Track Controller owner issues are diagnostics and decision requests only: do not
   change scheduler, vital-layer, starter, PLC or interpretation policies to pass probes.

## Validate and deliver

Run focused 1x process review and shared-Pi HELLO tests, then relevant complete suites:
harness/utils, common.hw_link, Track Controller HW/SW, CTC, Track Model, Train Controller
HW/SW (including `main.py --check`), Train Model and existing opt-in scenarios. Preserve
and report owner-question failures. Report the known Train Model UI flake; do not skip it.
Run scoped lint/type checks and state existing exceptions accurately, including N815.
Record revision, host, commands and bounds with fresh results. Bounded stalls do not prove
permanent deadlock; in-process probes do not verify process protocol faults; simulated
Pis do not establish physical USB readiness. Separate 10x measurements into completed/due
ticks, dropped backlog and late replies. Physical-Pi checks wait for working boards.
Write a Phase7 handover and link the shared owner review. Commit explicit paths with
required attribution and push this feature branch normally. Stop/report non-fast-forward
rejection rather than overwrite history. Preserved user files may leave the tree unclean.
Report changes, commits, direct/agent verification, limitations and remaining decisions.
