**Target:** truth/decisions/harness-output-inspector.md
**Action:** create
**Proposed by:** Codex on claude/quirky-fermi-sickg4
**Provenance:** asserted by Kevin Schillinger 2026-10-20 in the
harness window implementation questions.

---

# harness-output-inspector

**Status:** current
**Owner:** Kevin Schillinger
**Provenance:** asserted by Kevin Schillinger 2026-10-20
**Aliases:** last outputs inspector, selected module outputs
**Last updated:** 2026-10-20

## Decision

The harness window shows the selected module's last outputs read-only.
It pretty-prints and truncates the output, inspects only the selected
module, and refreshes at most twice a second. The inspector treats
outputs as opaque data and does not interpret module-specific fields.

