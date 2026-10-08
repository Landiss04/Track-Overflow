**Target:** truth/signals/signal-light-command.md
**Action:** create
**Proposed by:** GitHub Copilot on feature/TrackCtrl-Module-Implementation
**Provenance:** asserted by Braden 2026-10-06 (signals stand only where switches are; aspect names as the customer uses them); course `Architecture & Interface Dictionary.xlsx` (Track Controller to Track Model row); conflicting aspect set in `TrackCtrlSW/README.md` on `Track-Ctrl-SW` (`b39fa06`)

Note for the promoter: distinct from Jonathan's pending `signals/signal-aspect.md`
(`Train-Ctrl_SW`, `20261002-2258-signal-aspect.md`), which is the aspect the Track
Model sends on to the Train Controller. The two use the same four aspect names.

---

# signal-light-command

**Status:** current
**Owner:** Track Controller
**Provenance:** asserted by Braden 2026-10-06; course `Architecture & Interface Dictionary.xlsx`, Track Controller to Track Model; conflicting aspect set in `TrackCtrlSW/README.md` on `Track-Ctrl-SW` (`b39fa06`)
**Aliases:** Signal Light Color, signal light commands, signal colors, wayside signal command
**Last updated:** 2026-10-06

## Definition

The aspect the Track Controller commands each wayside signal to show, sent to the
Track Model: RED, YELLOW, GREEN or SUPER GREEN. Set by the PLC program
(REQ-FUNC-053).

## Notes

- Signals stand only where switches are: one signal at each switch, and none
  elsewhere. A signal is identified like its switch, by line and the block the
  switch is listed on in the track layout file, and named after it: `SW-12` and
  `SIG-12`.
- The Track Model reports back the aspect each lamp actually shows.
- The course interface dictionary types it as an enum of Green, Yellow and Red,
  per block. Four aspects, and only at switches, supersede that.

## Conflict

**Resolution owner:** Braden.

**Aspect names. Open.**

| Value | Provenance |
|-------|------------|
| RED, YELLOW, GREEN, SUPER GREEN | Braden 2026-10-06, adopting the customer's terms; Jonathan's pending `signal-aspect` uses the same four |
| RED, ORANGE, GREEN, SUPER GREEN | `TrackCtrlSW/README.md` on `Track-Ctrl-SW` (`b39fa06`), which states "The brief calls for red, orange, green and super green" |

REQ-INTF-009 requires the hardware and software Track Controllers to expose
equivalent interfaces, so the two variants must settle on one set.
