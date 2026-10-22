# Raspberry Pi owners: USB serial and agent setup

**Status:** Instructions only, 2026-10-21. Untested on hardware. No Pi was
provisioned in Phase 5 steps 1–9/13. Module owners perform step 11 when working
Raspberry Pi 5 boards are available; USB timing is step 10 and packaging is
step 12. Those three steps have not started.

Kevin's K5 assigns one Pi per HW module. Both windows stay on the host. The Pi
runs the Qt-free Python core and `common.hw_link.agent`, without its own clock.

## Identity

| Field | Track Controller HW | Train Controller HW |
| --- | --- | --- |
| Module argument | `track-controller-hw` | `train-controller-hw` |
| Manufacturer | Track Overflow | Track Overflow |
| Product | Track Overflow Track Controller HW | Track Overflow Train Controller HW |
| Serial | TO-TRACK-CTRL-HW-01 | TO-TRAIN-CTRL-HW-01 |
| VID:PID | `1d6b:0104` | `1d6b:0104` |

`1d6b:0104` is the selected Linux composite-gadget default, not a newly
allocated vendor ID. The host matches VID, PID and the distinct serial, then
checks the module in HELLO. A COM number is never configured. Product and
manufacturer strings describe each device for its owner.

## Prepare the board

Use a current Raspberry Pi OS installation and Python 3.10 or newer. Copy the
same source revision as the host to `/opt/track-overflow`; that path is an
example installation location chosen for the service below. The Pi needs
`common/`, `utils/`, `TrackCtrlHw/track_ctrl_hw/` and
`Train-Ctrl_HW/train_ctrl/`, preserving their relative paths. It needs no
PySide6, Qt or host UI assets. The owner chooses a suitable power arrangement
and a data-capable cable before connecting the USB-C port to the host.

Raspberry Pi documents the board's USB-C port for gadget mode and notes that
some host ports cannot power a Pi 5 reliably. The default Raspberry Pi USB
network gadget is a different function; do not have it bind the same USB
controller while configuring this serial-only gadget.
[Official Raspberry Pi gadget guidance](https://www.raspberrypi.com/news/usb-gadget-mode-in-raspberry-pi-os-ssh-over-usb/).

Enable the DWC2 peripheral overlay in the active boot configuration
(normally `/boot/firmware/config.txt`, under `[all]`):

```ini
[all]
dtoverlay=dwc2,dr_mode=peripheral
```

After the owner reboots, verify `/sys/class/udc` has a controller. Stop here
if none appears: no software fallback should hide an unavailable Pi (K8).

## Serial gadget template

The following configfs script is an owner-run example for a clean boot with
no gadget already bound. Save as `/usr/local/sbin/track-overflow-gadget`,
make executable, and choose the two strings for the correct module. It uses
Linux's ACM function and binds one USB controller.
[Linux configfs gadget procedure](https://www.kernel.org/doc/html/latest/usb/gadget_configfs.html).

```sh
#!/bin/sh
set -eu
# Train Controller owners substitute their product and serial from the table.
TO_PRODUCT='Track Overflow Track Controller HW'
TO_SERIAL='TO-TRACK-CTRL-HW-01'
modprobe libcomposite
mountpoint -q /sys/kernel/config || mount -t configfs none /sys/kernel/config
TO_GADGET=/sys/kernel/config/usb_gadget/track-overflow
mkdir "$TO_GADGET"
cd "$TO_GADGET"
printf '0x1d6b' > idVendor
printf '0x0104' > idProduct
mkdir strings/0x409
printf '%s' 'Track Overflow' > strings/0x409/manufacturer
printf '%s' "$TO_PRODUCT" > strings/0x409/product
printf '%s' "$TO_SERIAL" > strings/0x409/serialnumber
mkdir configs/c.1
mkdir configs/c.1/strings/0x409
printf 'Track Overflow CDC-ACM' > configs/c.1/strings/0x409/configuration
mkdir functions/acm.usb0
ln -s functions/acm.usb0 configs/c.1/acm.usb0
set -- /sys/class/udc/*
[ "$#" -eq 1 ] && [ -e "$1" ]
printf '%s' "${1##*/}" > UDC
```

Do not run this twice against an existing configfs instance. An owner who
changes the identity must unbind the gadget before reconfiguring it. Ensure
no serial console/getty or modem manager drives `/dev/ttyGS0`. The agent puts
that device in raw mode with echo off when it opens it.

## Example systemd units

Save `/etc/systemd/system/track-overflow-gadget.service`:

```ini
[Unit]
Description=Track Overflow CDC-ACM gadget
After=systemd-modules-load.service sys-kernel-config.mount

[Service]
Type=oneshot
ExecStart=/usr/local/sbin/track-overflow-gadget
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
```

Create an unprivileged `trackoverflow` user with access to `/dev/ttyGS0`
(for example through the device's `dialout` group on the installed OS).
Save `/etc/systemd/system/track-overflow-agent.service`. Replace the module
argument for the Train Controller board:

```ini
[Unit]
Description=Track Overflow Pi core
Requires=track-overflow-gadget.service
After=track-overflow-gadget.service

[Service]
Type=simple
User=trackoverflow
SupplementaryGroups=dialout
WorkingDirectory=/opt/track-overflow
StateDirectory=track-overflow
ExecStart=/usr/bin/python3 -m common.hw_link.agent --module track-controller-hw --device /dev/ttyGS0 --journal /var/lib/track-overflow/session.json --log /var/lib/track-overflow/agent.log
Restart=always
RestartSec=1

[Install]
WantedBy=multi-user.target
```

Owners then reload systemd and enable the two services. They must verify
actual device permissions, service ordering, source revision and journal
persistence on their OS. The example units have not been installed or run.

## Owner acceptance after hardware works

Confirm both identities enumerate on Windows with its built-in CDC-ACM
serial driver, correct HELLO module/version, manual database/program loads,
engineer gains, a Green+Red run, and unplug/reboot recovery. Verify no step
runs twice. Measure 1x/10x round trips, per-tick traffic, Pi scan duration and
power stability. The simulated-process and Linux pty tests do not establish
these hardware results. Windows packaging and separate installs remain
deferred under K10.
