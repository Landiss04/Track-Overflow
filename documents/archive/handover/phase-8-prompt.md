# Prompt: Phase 8 — owner diagnostics

Prepared 2026-10-25. Kevin's direction: "No updates—continue owner diagnostics".
Paste everything below the line into Codex. Reviewed diagnostic observations live
in the shared owner-review queue; this prompt does not authorize policy changes.

---

Continue on `claude/quirky-fermi-sickg4`. Read `AGENTS.md` and complete its
session-start checks, fetching `truth` and this feature branch once. Read fetched
truth INDEX first, then relevant shards only via `git show`. Verify HEAD is
`d606e05` or its expected descendant and report unexpected state without repair.
Never change branches, create worktrees, discard work or open a PR unless asked.

Read `documents/session-handover-2026-10-22.md`,
`documents/integration-handover-phase-7.md`, `documents/module-owner-review.md`,
`documents/review-runbook.md` and this prompt. The shared owner-review file is the
single current queue; link it instead of creating parallel issue writeups.

## How you work

You are the orchestrator. Delegate bounded legwork to **sol 6.1 medium effort**
subagents with disjoint file ownership; review their actual diffs and evidence.
Kevin runs build phases in Codex. His 2026-10-25 answer is
**"No updates—continue owner diagnostics"**: there are no new owner decisions or
working-Pi reports. Preserve existing ownership and approval boundaries.
Kevin's temporary pause expires on 2026-10-25 at **02:20:45 EDT (06:20:45 UTC)**:
make no Qwen delegate calls before that time. Expiry does not require using Qwen.

Preserve these five untracked user files:
`TrainModel/docs/architecture-drawio-prompt.md`,
`TrainModel/docs/class-diagram-supplemen-prompt.md`,
`TrainModel/docs/uml-sequence-prompt.md`,
`common/harness/tests/adversarial_probe.py`, and
`documents/central-harness-adversarial-2026-10-20.md`.
Do not modify `TrackModel/*_line.json`. Any UI change, including Python
behind windows, requires Kevin's prior approval for that exact change.
No scheduler, zone/reservation, vital-layer, PLC/starter, routing or interpretation
policy changes to make owner probes pass. No 10x optimization before real-Pi
measurements, new transport/provisioning paths or claims of physical-Pi readiness.
Truth is read from fetched `origin/truth`; code observations are not decisions.
Do not edit, delete, rename, renumber or promote existing inbox proposals.

## Known diagnostic baseline

- Green's earlier zone hold cleared; at the endpoint CTC grants 35 blocks but the
  SW starter `AUTH_65` gate yields zero, without a reported vital-layer override.
- The Red review plan forms one zone 9…66 through yard index 101; seeded
  snapshots release followers only after the preceding run is DONE.
- Normal occupancy maps are complete; member omission becomes clear membership,
  while missing fields/namespace and retained rejected ticks are distinct cases.

## Diagnostics scope

1. Turn the reviewed Green trace into bounded reusable diagnostic coverage using
   existing real-core harness wiring. Capture the first transition into the 65/64
   hold and the grant boundary, not merely another identical endpoint. Preserve
   schedule/tick semantics and distinguish starter separation from CTC admission.
   Record front position, beacon, station eligibility and door-command state at
   the first hold; preserve existing assertions without assuming an arrival-policy fix.
2. Make the reviewed Red schedule/zone/hold snapshots reproducible with meaningful
   assertions on current behavior. Preserve the distinction between seeded Worlds
   and physics acceptance; do not choose a new zone, route or reservation policy.
3. Make the reviewed input-completeness boundary cases reusable: individual member
   omission versus explicit false, unavailable namespace, missing whole fields and
   repeated snapshots. Fill the static-only rejected-tick retention gap with a
   bounded harness injection that observes retained outputs and rejection events;
   preserve the clock barrier and separate rejected, late and disconnected cases.
4. Reuse existing harness/test facilities and meaningful observations. Preserve the
   three known acceptance failures and all safety/protocol assertions. Avoid
   duplicate runners, permanent debug output and implementation-mirroring tests.
   Do not rerun just-completed traces or full suites merely to reproduce their counts.
5. Update the matching entries in `module-owner-review.md` with reviewed evidence,
   exact revision/host/commands/bounds and concise Landis/Harry/Braden decision
   packets: observation, remaining gap, owner question and required validation.
   Keep historical results scoped to their revisions; a bounded stall is not proof
   of permanent deadlock. No separate issue writeups or policy fixes.

## Validate and deliver

Use the project venv and offscreen Qt. Keep scratch traces and caches outside the
repo where feasible. Run new/changed diagnostic checks and appropriate affected
suites; do not repeat the completed Phase 7 verification without a source change
or a new failure requiring it. Label direct checks versus agent reports.
Report ticks/bounds and expected owner failures explicitly. In-process diagnostics
cannot verify process/Pi protocol correctness; simulated Pis cannot verify USB.
Review explicit staged paths and each commit's stat, preserve all user work, commit
with required attribution and push this feature branch normally. Stop and report
non-fast-forward rejection. Summarize findings and unresolved owner/Pi decisions.
Do not implement a policy fix or advance another phase without Kevin's answers.
