"""Generate one offline Pi agent bundle parameterized by hardware module."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import subprocess
import tarfile
from pathlib import Path

from .protocol import MODULES
from .manifest import AGENT_VERSION, content_hash, sources
from .transport import IDENTITIES, ROOT

GADGET = """#!/bin/sh
set -eu
modprobe libcomposite
mountpoint -q /sys/kernel/config || mount -t configfs none /sys/kernel/config
TO_GADGET=/sys/kernel/config/usb_gadget/track-overflow
# A bound instance must never be silently reconfigured.
if [ -d "$TO_GADGET" ]; then
    echo 'Existing gadget; reboot before identity change' >&2
    exit 1
fi
mkdir "$TO_GADGET"
cd "$TO_GADGET"
printf '@VID@' > idVendor
printf '@PID@' > idProduct
mkdir strings/0x409
printf '%s' '@MANUFACTURER@' > strings/0x409/manufacturer
printf '%s' '@PRODUCT@' > strings/0x409/product
printf '%s' '@SERIAL@' > strings/0x409/serialnumber
mkdir -p configs/c.1/strings/0x409
printf '%s' 'Track Overflow CDC-ACM' > configs/c.1/strings/0x409/configuration
mkdir functions/acm.usb0
ln -s functions/acm.usb0 configs/c.1/acm.usb0
set -- /sys/class/udc/*
[ "$#" -eq 1 ] && [ -e "$1" ]
printf '%s' "${1##*/}" > UDC
# Do not depend on the distribution's default tty group.
i=0
while [ ! -e /dev/ttyGS0 ]; do
    i=$((i+1)); [ "$i" -lt 100 ]; sleep 0.05
done
chown trackoverflow:dialout /dev/ttyGS0
chmod 0660 /dev/ttyGS0
"""
GADGET_UNIT = """[Unit]
Description=Track Overflow CDC-ACM gadget
After=systemd-modules-load.service sys-kernel-config.mount
Before=track-overflow-agent.service

[Service]
Type=oneshot
ExecStart=/usr/local/sbin/track-overflow-gadget
RemainAfterExit=yes
TimeoutStartSec=10

[Install]
WantedBy=multi-user.target
"""
AGENT_UNIT = """[Unit]
Description=Track Overflow @MODULE@ core
Requires=track-overflow-gadget.service
After=track-overflow-gadget.service

[Service]
Type=simple
User=trackoverflow
SupplementaryGroups=dialout
WorkingDirectory=/opt/track-overflow
StateDirectory=track-overflow
Environment=PYTHONDONTWRITEBYTECODE=1
ExecStart=/usr/bin/python3 -m common.hw_link.agent \\
 --module @MODULE@ --device /dev/ttyGS0 \\
 --journal /var/lib/track-overflow/session.json \\
 --log /var/lib/track-overflow/agent.log
Restart=always
RestartSec=1

[Install]
WantedBy=multi-user.target
"""
INSTALL = """#!/bin/sh
set -eu
[ "$(id -u)" = 0 ] || { echo 'Run sudo ./install.sh' >&2; exit 1; }
cd "$(dirname "$0")"
sha256sum -c SHA256SUMS
/usr/bin/python3 -c 'import sys; assert sys.version_info >= (3,10)'
id trackoverflow >/dev/null 2>&1 || \\
    useradd --system --create-home --groups dialout trackoverflow
# Stop before replacing source; keep the durable journal.
systemctl stop track-overflow-agent.service 2>/dev/null || true
install -d /opt/track-overflow
cp -R source/. /opt/track-overflow/
install -m 0755 track-overflow-gadget /usr/local/sbin/track-overflow-gadget
install -m 0644 track-overflow-gadget.service \\
    track-overflow-agent.service /etc/systemd/system/
install -m 0644 90-track-overflow.rules /etc/udev/rules.d/
udevadm control --reload-rules
systemctl disable --now serial-getty@ttyGS0.service 2>/dev/null || true
systemctl mask serial-getty@ttyGS0.service
systemctl daemon-reload
systemctl enable track-overflow-gadget.service track-overflow-agent.service
printf '%s\\n' 'Enable dtoverlay=dwc2,dr_mode=peripheral under [all].'
printf '%s\\n' 'Use the active config.txt; reboot.'
printf '%s\\n' 'Inspect both track-overflow services and host HELLO.'
"""


def build(module: str, output: Path) -> dict[str, str]:
    """Bundle core sources and checksums without installing locally."""
    identity = IDENTITIES[module]
    revision = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()
    source_files = sources()
    bundle_hash = content_hash(source_files)
    files = {"source/" + name: data for name, data in source_files.items()}
    files.update(
        {
            "track-overflow-gadget": GADGET.replace(
                "@PRODUCT@", str(identity["product"])
            )
            .replace("@SERIAL@", str(identity["serial"]))
            .replace("@MANUFACTURER@", str(identity["manufacturer"]))
            .replace("@VID@", f"0x{identity['vid']:04x}")
            .replace("@PID@", f"0x{identity['pid']:04x}")
            .encode(),
            "track-overflow-gadget.service": GADGET_UNIT.encode(),
            "track-overflow-agent.service": AGENT_UNIT.replace(
                "@MODULE@", module
            ).encode(),
            "90-track-overflow.rules": (
                b'KERNEL=="ttyGS0", OWNER="trackoverflow", '
                b'GROUP="dialout", MODE="0660"\n'
            ),
            "install.sh": INSTALL.encode(),
            "manifest.json": json.dumps(
                dict(
                    module=module,
                    revision=revision,
                    identity=identity,
                    agent_version=AGENT_VERSION,
                    agent_hash=bundle_hash,
                ),
                indent=2,
            ).encode()
            + b"\n",
        }
    )
    hashes = {
        name: hashlib.sha256(data).hexdigest() for name, data in files.items()
    }
    files["SHA256SUMS"] = "".join(
        f"{digest}  {name}\n" for name, digest in hashes.items()
    ).encode()
    with tarfile.open(output, "w:gz") as archive:
        for name, data in files.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            info.mode = (
                0o755
                if name in {"install.sh", "track-overflow-gadget"}
                else 0o644
            )
            archive.addfile(info, io.BytesIO(data))
    return dict(
        module=module,
        revision=revision,
        output=str(output),
        sha256=hashlib.sha256(output.read_bytes()).hexdigest(),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--module", required=True, choices=MODULES)
    parser.add_argument("--output", required=True, type=Path)
    options = parser.parse_args()
    print(json.dumps(build(options.module, options.output), indent=2))


if __name__ == "__main__":
    main()
