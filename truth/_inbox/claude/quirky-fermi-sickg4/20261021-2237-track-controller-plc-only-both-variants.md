**Target:** truth/decisions/D019-wayside-runs-only-its-program.md
**Action:** create
**Proposed by:** Integration on claude/quirky-fermi-sickg4
**Provenance:** Kevin Schillinger directly confirmed in this integration session on 2026-10-21 that K3b's no-vital policy covers SW too; Braden's 2026-10-16 showcase decision is the earlier HW source.

---

# track-controller-plc-only-both-variants

**Status:** current
**Owner:** Kevin
**Provenance:** Kevin Schillinger directly confirmed in this integration session on 2026-10-21 that K3b's no-vital policy covers SW too; Braden's 2026-10-16 showcase decision is the earlier HW source.
**Aliases:** no vital layer, PLC-only safety, SW and HW policy
**Last updated:** 2026-10-21

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
  Kevin's explicit October 21 clarification that the no-vital policy
  covers both variants.
