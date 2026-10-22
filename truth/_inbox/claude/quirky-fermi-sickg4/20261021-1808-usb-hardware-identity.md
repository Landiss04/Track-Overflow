**Target:** truth/decisions/D029-usb-hardware-identity.md
**Action:** create
**Proposed by:** Integration on claude/quirky-fermi-sickg4
**Provenance:** Kevin Schillinger's Phase 5 decisions relayed in the session prompt, 2026-10-21. K5: "Pi 5 set up by module owners. assign the both usb ident strigns".

---

# usb-hardware-identity

**Status:** current
**Owner:** Kevin
**Provenance:** asserted by Kevin Schillinger 2026-10-21; K5: "Pi 5 set up by module owners. assign the both usb ident strigns"
**Aliases:** USB identity, Pi 5, CDC-ACM identity
**Last updated:** 2026-10-21

## Decision

One Raspberry Pi 5 per hardware module presents CDC-ACM through its USB-C
device port. Module owners provision their Pis. The host identifies each
module by its USB identity, not a fixed port number (D027).

| Field | Track Controller HW | Train Controller HW |
| --- | --- | --- |
| Manufacturer | Track Overflow | Track Overflow |
| Product | Track Overflow Track Controller HW | Track Overflow Train Controller HW |
| Serial | TO-TRACK-CTRL-HW-01 | TO-TRAIN-CTRL-HW-01 |
| VID:PID | 1d6b:0104 | 1d6b:0104 |

These strings are the integration-assigned identities requested by Kevin.
The VID:PID is the Linux composite-gadget default selected for development,
not an officially allocated Track Overflow vendor ID. Serial and product
distinguish the modules sharing it. Hardware setup and identification must
be verified on working Pis before delivery.
