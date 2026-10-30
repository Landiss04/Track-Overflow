"""Owner tooling stays on the same agent, codecs and transport paths."""

import json
import os
import subprocess
import sys
import tarfile

import pytest
from common.hw_link import protocol as p
from common.hw_link.agent import PiLinkServer
from common.hw_link.bringup import recording
from common.hw_link.provision import build
from common.hw_link.tests.test_protocol_agent import hello, step


def test_echo_is_explicit_and_preserves_core_state():
    request = dict(hello(), echo="x" * 20480)
    normal = PiLinkServer("train-controller-hw")
    assert "echo" not in normal.handle(request)[0]
    echo = PiLinkServer("train-controller-hw", echo_test=True)
    assert echo.handle(request)[0]["echo"] == request["echo"]
    assert not echo.cache


@pytest.mark.parametrize("module", p.MODULES)
def test_bundle_is_offline_stdlib_and_shell_parses(tmp_path, module):
    archive = tmp_path / "pi.tar.gz"
    result = build(module, archive)
    assert len(result["sha256"]) == 64
    folder = tmp_path / "bundle"
    with tarfile.open(archive) as stream:
        stream.extractall(folder, filter="data")
    subprocess.run(
        ["sha256sum", "-c", "SHA256SUMS"],
        cwd=folder,
        check=True,
        capture_output=True,
    )
    for script in ("install.sh", "track-overflow-gadget"):
        subprocess.run(["sh", "-n", str(folder / script)], check=True)
    # -S proves that neither Qt nor any site-installed dependency is needed.
    env = dict(os.environ, PYTHONPATH=str(folder / "source"))
    request = dict(hello(), module=module)
    child = subprocess.run(
        [
            sys.executable,
            "-S",
            "-m",
            "common.hw_link.agent",
            "--module",
            module,
            "--journal",
            str(tmp_path / "journal"),
        ],
        cwd=folder,
        input=p.encode(request),
        capture_output=True,
        env=env,
        check=True,
    )
    response = p.decode(child.stdout)
    assert response["module"] == module
    manifest = json.loads((folder / "manifest.json").read_text())
    assert response["agent_hash"] == manifest["agent_hash"]
    assert not any(
        b"from PySide" in path.read_bytes()
        for path in (folder / "source").rglob("*.py")
    )
    assert not child.stderr


@pytest.mark.parametrize("transport", ("process", "pty"))
def test_cli_echo_and_recording(tmp_path, transport):
    if transport == "pty" and sys.platform != "linux":
        pytest.skip("Linux raw tty")
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen")
    base = [
        sys.executable,
        "-m",
        "common.hw_link.bringup",
        "--module",
        "train-controller-hw",
        "--transport",
        transport,
    ]
    for args in (
        ["--echo-bytes", "20480", "--count", "5"],
        ["--recording", str(tmp_path / "recording")],
    ):
        (tmp_path / "recording").write_text(
            json.dumps({"request": step()}) + "\n"
        )
        child = subprocess.run(
            base + args, capture_output=True, env=env, timeout=30, check=True
        )
        output = json.loads(child.stdout)
        assert output["error"] is None
        assert output["samples"] > 0
        assert output["hello_s"] < 20
        assert not output["hardware_test"]
        assert not child.stderr


def test_recording_preserves_actions_and_steps(tmp_path):
    path = tmp_path / "recording"
    action = p.message(
        p.ACTION, 5, action="test_engineer_gains", args={"kp": 1, "ki": 2}
    )
    frames = [action, step()]
    path.write_text("\n".join(json.dumps({"request": f}) for f in frames))
    assert recording(path) == frames


def test_inventory_names_missing_and_ambiguous():
    from common.hw_link.bringup import inventory

    assert all(
        entry["status"] == "missing"
        for entry in inventory([])["modules"].values()
    )

    class Port:
        def hasVendorIdentifier(self):
            return True

        def hasProductIdentifier(self):
            return True

        def vendorIdentifier(self):
            return 0x1D6B

        def productIdentifier(self):
            return 0x0104

        def serialNumber(self):
            return "TO-TRACK-CTRL-HW-01"

        def systemLocation(self):
            return "/dev/ttyACM0"

        def manufacturer(self):
            return "Track Overflow"

        def description(self):
            return "Track Overflow Track Controller HW"

    result = inventory([Port(), Port()])
    assert result["modules"]["track-controller-hw"]["status"] == "ambiguous"
    assert result["modules"]["train-controller-hw"]["status"] == "missing"


def test_bundle_hash_covers_core_and_protocol_bytes():
    from common.hw_link.manifest import content_hash, sources

    original = sources()
    for name in (
        "common/hw_link/protocol.py",
        "Train-Ctrl_HW/train_ctrl/control.py",
        "TrackCtrlHw/track_ctrl_hw/controller.py",
    ):
        changed = dict(original)
        changed[name] += b"\n# changed core\n"
        assert content_hash(changed) != content_hash(original)


def test_relay_refuses_wrong_bundle_and_version():
    from common.hw_link.relay import HardwareRelay
    from common.hw_link.transport import ByteTransport

    class Idle(ByteTransport):
        def start(self):
            pass

        def write(self, data):
            pass

        def close(self):
            pass

    relay = HardwareRelay("train-controller-hw", Idle())
    ready, events = [], []
    relay.ready.connect(lambda: ready.append(True))
    relay.diagnosticEvent.connect(events.append)
    frame = dict(
        hello(),
        session=relay.session,
        agent_version="1",
        agent_hash=relay.expected_agent_hash,
        boot="boot",
    )
    relay._handle(dict(frame, agent_hash="wrong"))
    relay._handle(dict(frame, agent_version="wrong"))
    assert not ready and len(events) == 2
    assert all("PI_HELLO_REJECTED" in event for event in events)
    relay._handle(frame)
    assert ready
    relay.close()


@pytest.mark.parametrize("module", p.MODULES)
def test_bundle_identity_comes_only_from_shared_table(
    tmp_path, monkeypatch, module
):
    from common.hw_link.transport import IDENTITIES

    # Changing the shared identity must change all generated USB fields.
    identity = dict(
        manufacturer="Owner Test",
        product="Test Controller",
        serial="TEST-01",
        vid=0x1234,
        pid=0x5678,
    )
    monkeypatch.setitem(IDENTITIES, module, identity)
    archive = tmp_path / "identity.tar.gz"
    build(module, archive)
    with tarfile.open(archive) as bundle:
        gadget = bundle.extractfile("track-overflow-gadget").read().decode()
        manifest = json.load(bundle.extractfile("manifest.json"))
    assert "printf '0x1234' > idVendor" in gadget
    assert "printf '0x5678' > idProduct" in gadget
    for key, target in (
        ("manufacturer", "manufacturer"),
        ("product", "product"),
        ("serial", "serialnumber"),
    ):
        assert f"'{identity[key]}' > strings/0x409/{target}" in gadget
    assert manifest["identity"] == identity
    assert not any(
        marker in gadget
        for marker in (
            "@VID@",
            "@PID@",
            "@MANUFACTURER@",
            "@PRODUCT@",
            "@SERIAL@",
        )
    )
