"""Shared content identity for the Pi bundle and its matching host artifact."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AGENT_VERSION = "1"


def sources(root: Path = ROOT) -> dict[str, bytes]:
    """Return the exact Qt-free runtime source set installed on both Pis."""
    names = [
        "common/hw_link/__init__.py",
        "common/hw_link/agent.py",
        "common/hw_link/protocol.py",
        "common/hw_link/codec.py",
        "common/hw_link/cores.py",
        "common/hw_link/manifest.py",
        "utils/__init__.py",
        "utils/harness_protocol.py",
    ]
    for folder in ("TrackCtrlHw/track_ctrl_hw", "Train-Ctrl_HW/train_ctrl"):
        names.extend(
            str(path.relative_to(root))
            for path in sorted((root / folder).glob("*.py"))
            if path.stem
            not in {
                "backend",
                "app",
                "state_bridge",
                "rows_model",
                "module_process",
                "link",
                "harness",
            }
            and not (
                folder.startswith("TrackCtrlHw/") and path.stem == "state"
            )
        )
    return {name: (root / name).read_bytes() for name in sorted(names)}


def content_hash(files: dict[str, bytes]) -> str:
    """Hash canonical paths and bytes, independent of timestamps."""
    digest = hashlib.sha256()
    for name, data in sorted(files.items()):
        digest.update(name.encode() + b"\0")
        digest.update(hashlib.sha256(data).digest())
    return digest.hexdigest()


def expected_hash() -> str:
    """Source/Pi recompute content; frozen host reads its build manifest."""
    if getattr(sys, "frozen", False):
        return str(json.loads((ROOT / "pi-bundle.json").read_text())["hash"])
    return content_hash(sources())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    options = parser.parse_args()
    files = sources()
    options.output.write_text(
        json.dumps(
            dict(
                version=AGENT_VERSION,
                hash=content_hash(files),
                files={
                    name: hashlib.sha256(data).hexdigest()
                    for name, data in files.items()
                },
            ),
            indent=2,
        )
        + "\n"
    )


if __name__ == "__main__":
    main()
