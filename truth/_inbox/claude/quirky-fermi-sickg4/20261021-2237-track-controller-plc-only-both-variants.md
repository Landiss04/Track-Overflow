**Target:** truth/decisions/D019-wayside-runs-only-its-program.md
**Action:** create
**Proposed by:** Integration on claude/quirky-fermi-sickg4
**Provenance:** asserted by Kevin Schillinger 2026-10-22: "yes" to confirming that the no-vital-layer policy covers SW too; asserted by Braden 2026-10-16 (showcase changes).

---

# D019-wayside-runs-only-its-program

**Status:** current
**Owner:** Kevin
**Provenance:** asserted by Kevin Schillinger 2026-10-22: "yes" to confirming that the no-vital-layer policy covers SW too; asserted by Braden 2026-10-16 (showcase changes).
**Aliases:** no vital layer, PLC-only safety, SW and HW policy
**Last updated:** 2026-10-22

## Decision

Both Track Controller variants house their PLC programs. Neither variant
has a separate vital layer making safety decisions after the PLC scan.
Every safety rule belongs in the PLC program: separation, closed blocks,
speed caps, switch locking and correspondence, signals and crossings.
CTC switch/closure/speed/authority inputs reach the program, which decides
the outputs, including switch commands in maintenance.

For the HW implementation described by Braden's WP2 design and PR #43,
dual-channel execution/check and fail-safe hold while no trustworthy
program runs are execution integrity mechanisms, not a second layer that
rewrites a running program's safety decisions. This does not prescribe
dual-channel execution for the SW variant. Every program author implements
all applicable safety and precedence rules.

## Supersedes

- The October 14 pending SW vital-restrictions policy is superseded by
  Kevin's explicit October 22 confirmation that the no-vital policy
  covers both variants.

## Conflict

- This proposed D019 entry (`20261021-2237-track-controller-plc-only-both-variants.md`): no separate vital layer in either variant, with dual-channel execution integrity allowed for HW. Provenance: Kevin Schillinger, "yes", 2026-10-22.
- Braden's proposed D019 entry (`truth/_inbox/feature/TrackCtrl-Showcase-Feedback/20261016-1430-D019-wayside-runs-only-its-program.md`): outputs pass through as the program produces them; fail-safe values apply only while no program runs. Provenance: asserted by Braden 2026-10-16 (showcase changes).

Both proposals target `truth/decisions/D019-wayside-runs-only-its-program.md`. Their treatment of execution integrity and fail-safe holds requires reconciliation before promotion; neither replaces the other here.

**Resolution owner:** Harry Tye (Track Controller contract owner), with Braden responsible for resolving the HW interpretation.
