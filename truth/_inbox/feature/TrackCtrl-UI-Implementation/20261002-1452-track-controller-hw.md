**Target:** truth/modules/track-controller/track-controller-hw.md
**Action:** replace
**Proposed by:** GitHub Copilot on feature/TrackCtrl-UI-Implementation
**Provenance:** asserted by Braden 2026-10-02 (separate window and separate
process for the test UI); wayside interface diagram supplied by Braden
2026-10-02 (the signal set the test UI drives and reads back)

Note for the promoter: the shard this replaces is a placeholder that asserts
nothing. This proposal fills only the sections that now have a source and
leaves the rest unpopulated. **Owner is still unassigned**, so by the entry
rules this is not yet promotable as written — a named owner has to be filled
in first.

---

# track-controller-hw

*Any difference observable to a consumer belongs in the contract shard or in the
relevant signal entry, not here.*

**Status:** current
**Owner:** unassigned — must be named before promotion
**Provenance:** asserted by Braden 2026-10-02; wayside interface diagram
supplied by Braden 2026-10-02
**Aliases:** HW Track Controller
**Contract:** `truth/modules/track-controller/track-controller.md`
**Last updated:** 2026-10-02

## Import path and entry point

| Surface | Entry point |
| --- | --- |
| Module UI | `TrackCtrlHw/ui/main.py` |
| Test UI | `TrackCtrlHw/test_ui/main.py` |
| Module package | `TrackCtrlHw/track_ctrl/` |

## Platform and dependencies

PySide6 with QML, per `truth/ui/style-guide.md` §9. Both windows read their
design tokens from the shared `ui/theme.py` and build from the shared QML
components in `ui/`.

## Build and run

Run from the repository root:

```
python TrackCtrlHw/ui/main.py        # module UI
python TrackCtrlHw/test_ui/main.py   # test UI
```

## Implementation-specific constraints

- **The test UI is a separate window in a separate process.** It is not a page,
  tab, panel or overlay inside the module window, and the two never share a
  process. Each is launched by its own entry point above.
- The test UI presents exactly the signals on the wayside interface diagram —
  the inputs from the CTC Office, from the Track Model and from the programmer,
  and the outputs to the CTC Office and to the Track Model. It does not expose
  any other control the module UI happens to carry.
- Signal values on the test UI are shown in backend units (m/s, m), not the
  display units of `truth/conventions/units.md`, because the page probes the
  module interface rather than presenting it to an operator.
