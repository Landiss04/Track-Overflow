**Target:** truth/decisions/D027-usb-link-to-the-pis.md
**Action:** create
**Proposed by:** Claude on claude/quirky-fermi-sickg4
**Provenance:** chosen by Claude at Kevin Schillinger's request, 2026-10-20: "choose whatever usb protocol makes the most sense given that this will fucntion on a strangers windows machine as an exe". The link is USB serial in the standard communications class, because Windows 10 and later drive it with their own built-in driver, so a strange machine needs no driver install, no network and no administrator rights; Qt's serial-port module, part of PySide6, reaches it from the built executable. ID D027 because D019 to D026 are taken by pending proposals.

---

# D027-usb-link-to-the-pis

**Status:** current
**Owner:** Kevin
**Provenance:** chosen by Claude at Kevin Schillinger's request, 2026-10-20
**Aliases:** USB link, USB serial, CDC-ACM, Pi link, Raspberry Pi link, COM port, gadget mode
**Last updated:** 2026-10-20

## Context

The hardware variants run on Raspberry Pis that talk to the host PC over USB, and their
windows run on the host ([D021](D021-hardware-variants-and-selection.md)). The system
ships as one executable that must run on any Windows machine it is copied to, with no
driver installation and no network.

## Decision

- Each Raspberry Pi connects to the host PC with one USB cable, in the Pi's USB device
  ("gadget") mode, and presents itself as a USB serial device of the standard
  communications class (CDC-ACM). Windows 10 and later drive such a device with their
  built-in serial driver.
- The host reaches each Pi as a serial (COM) port. It finds the port by the device's USB
  identity, a product name or serial number set on the Pi, never by a fixed COM number.
  On connecting, the Pi states which module it runs.
- The messages are the same newline-delimited JSON that the harness exchanges with every
  module ([D005](D005-central-harness.md)).
- A hardware variant's process on the host owns the serial port. It shows the window and
  relays the harness's messages to the Pi and the replies back, so the harness drives a
  hardware variant exactly as it drives any other module.
- The Raspberry Pis are USB peripherals of the one computer the system runs on.
- There is one Pi per hardware module: one for the Track Controller HW, and one for the
  Train Controller HW, which runs every Red Line train.

## Consequences

- A Pi must support USB device mode, as the Pi Zero family does on its data port and the
  Pi 4 on its USB-C port. A Pi 3 Model B does not.
- A Pi Zero 2 W can run on the power the PC's port gives through the same cable; a Pi 4
  may need more than a PC port supplies.
- The Pi runs Python and the module's core, without the window.
- If a Pi is unplugged, its replies stop, and the harness pauses the clock and names the
  module ([D017](D017-shared-simulation-clock.md)).
