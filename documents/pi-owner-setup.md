# Raspberry Pi owners: USB serial and agent setup

**Status:** Phase 6 software preparation, 2026-10-22. Installer generation,
Qt-free bundle smoke checks and simulated links are testable here. No Pi has
been provisioned or measured. Boot-to-HELLO under 20 seconds remains a real
hardware acceptance target. Windows packaging remains deferred.

Both module owners use this same recipe, parameterized by module. Each Pi 5
runs `common.hw_link.agent` and its Qt-free core. The two windows stay on the
host; the central harness remains the only clock. The same agent, protocol,
relay and transports serve real and explicitly selected simulated links.

## Assigned identity

| Field | Track Controller HW | Train Controller HW |
| --- | --- | --- |
| Module | `track-controller-hw` | `train-controller-hw` |
| Manufacturer | Track Overflow | Track Overflow |
| Product | Track Overflow Track Controller HW | Track Overflow Train Controller HW |
| Serial | TO-TRACK-CTRL-HW-01 | TO-TRAIN-CTRL-HW-01 |
| VID:PID | `1d6b:0104` | `1d6b:0104` |

The VID/PID is the selected Linux composite gadget default, not a newly
allocated vendor ID. Discovery matches VID, PID and the module's serial;
manufacturer/product are also displayed for inspection. COM numbers and
`ttyACM` suffixes can change. HELLO checks module, protocol, agent version
and the full shared runtime bundle hash before the host becomes ready.

## Generate and transfer the bundle

On the host, from the repository root and project virtual environment:

```sh
python -m common.hw_link.provision --module track-controller-hw --output /tmp/track-pi.tar.gz
python -m common.hw_link.provision --module train-controller-hw --output /tmp/train-pi.tar.gz
```

Transfer the appropriate archive to its board by removable media or the
owner's existing administration connection. This is an offline bundle:
installation downloads nothing. It includes the existing agent, strict
protocol/framing, core adapters and both Qt-free core packages, one configfs
script, two systemd units, a tty permission rule and `install.sh`.
`manifest.json` records module, identity, source revision and content hash;
`SHA256SUMS` records every bundled file. Generate from the same source as the
host executable. The content hash covers source bytes, so an uncommitted
source change also requires regenerating the matching host and Pi bundles.
It is a consistency check, not a cryptographic authenticity signature.

## Prepare the Pi 5 and install

Use Raspberry Pi OS with `/usr/bin/python3` version 3.10 or later. No Qt,
PySide6, pip install or window assets are needed on the board. Connect the
board's USB-C port using a data cable. Confirm the chosen host port/power
arrangement reliably powers the board under load. Raspberry Pi explicitly
lists Pi 5 USB-C for gadget mode and describes power-related reboots/drops;
its default USB network gadget must be disabled before this serial-only
gadget binds the same controller.
[Official Raspberry Pi USB gadget guidance](https://www.raspberrypi.com/news/usb-gadget-mode-in-raspberry-pi-os-ssh-over-usb/).

Enable this line under `[all]` in the active boot configuration, normally
`/boot/firmware/config.txt`, using the owner's editor:

```ini
[all]
dtoverlay=dwc2,dr_mode=peripheral
```

Extract into an empty directory on the board, then install:

```sh
mkdir -p ~/track-overflow-install
cd ~/track-overflow-install
tar -xzf /path/to/track-pi.tar.gz
sudo ./install.sh
sudo reboot
```

Use `train-pi.tar.gz` on the Train Controller board. The script verifies
checksums and Python, creates an unprivileged `trackoverflow` service user,
copies source into `/opt/track-overflow`, installs the gadget/agent units and
tty permission rule, masks the conflicting ttyGS0 getty and enables startup
at boot. It preserves the journal in `/var/lib/track-overflow/session.json`.
It does not modify boot config or reboot for you. Existing competing gadgets
must be stopped by their owner. Identity changes require a fresh boot: the
gadget script refuses to silently reconfigure an existing configfs gadget.

The generated script configures `acm.usb0` through configfs, assigns the
strings above and binds the one controller under `/sys/class/udc`.
[Linux configfs gadget procedure](https://docs.kernel.org/usb/gadget_configfs.html),
[Linux ACM gadget function](https://docs.kernel.org/usb/gadget-testing.html#acm-function).
If no controller appears after reboot, stop and diagnose the boot overlay,
kernel and board configuration; a simulated Pi must never hide that fault.

```sh
ls /sys/class/udc
systemctl status track-overflow-gadget.service track-overflow-agent.service
journalctl -b -u track-overflow-gadget.service -u track-overflow-agent.service
ls -l /dev/ttyGS0
cat /opt/track-overflow/common/hw_link/manifest.py
```

## Host verification and acceptance

Run `python -m common.hw_link.bringup --list` to inspect both identities at
once. The report names each module as found, missing or ambiguous, with all
matching paths and expected strings. Linux should show `/dev/ttyACM*`;
Windows should show a COM port using its standard CDC-ACM driver. Resolve
permissions or duplicate serials before proceeding. Close any application
already holding the port, then:

```sh
python -m common.hw_link.bringup --module track-controller-hw --timeout 20
python -m common.hw_link.bringup --module train-controller-hw --timeout 20
```

These commands check identity/version/hash and report `hello_s`; they do not
step the core. Measure cold boot separately: start the host probe before
powering the board and record power-on plus HELLO timestamps. A successful
probe against an already booted board establishes connection latency only.
The 20 second timeout applies to each pending HELLO/reply, not to the entire
length of a workload benchmark.

Use [the bring-up measurement and fault runbook](pi-bringup-checks.md) for
echo sizes, recorded Red workloads, full-system timing and recovery evidence.
Record the actual Pi model, OS/kernel, revision/hash, cable and power supply,
host OS and identities beside the measurements. Real USB/power, cold boot,
Windows enumeration and real unplug/reboot tests are still pending.
