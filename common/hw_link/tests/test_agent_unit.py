"""The agent unit sets the governor, prioritises and optimises; install.sh restarts a running agent."""

import subprocess

from common.hw_link import provision


def test_agent_unit_sets_governor_prioritises_and_optimises():
    unit = provision.AGENT_UNIT
    assert "\nCPUAffinity=" not in unit
    assert "\nExecStartPre=-+/bin/sh -c " in unit
    assert "echo performance > " in unit and "scaling_governor" in unit
    assert "\nNice=-10\n" in unit
    assert "\nEnvironment=PYTHONOPTIMIZE=1\n" in unit
    assert unit.index("ExecStartPre") > unit.index("[Service]")
    assert unit.index("ExecStartPre") < unit.index("ExecStart=")


def test_install_script_parses_and_restarts_only_a_running_agent():
    script = provision.INSTALL
    subprocess.run(["sh", "-n"], input=script.encode(), check=True)
    # The state is read before the stop, and the start comes after enable.
    assert (
        script.index("is-active --quiet track-overflow-agent")
        < script.index("systemctl stop track-overflow-agent")
        < script.index("systemctl enable")
        < script.index("systemctl start track-overflow-agent")
        < script.rindex("sync")
    )


def test_install_script_start_is_skipped_when_the_agent_was_stopped(tmp_path):
    # Run the script's own logic with systemctl stubbed.
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    log = tmp_path / "calls"
    for name, status in (("systemctl", 3), ("id", 0), ("sha256sum", 0)):
        (bin_dir / name).write_text(
            f'#!/bin/sh\necho "{name} $*" >> {log}\n'
            + ('[ "$1" = is-active ] && exit %d\n' % status
               if name == "systemctl" else "")
            + "exit 0\n"
        )
        (bin_dir / name).chmod(0o755)
    body = provision.INSTALL.split("/usr/bin/python3 -c", 1)[1]
    tail = "\n".join(
        line
        for line in body.splitlines()[1:]
        if line.startswith(("systemctl", "running", "if systemctl", "[ -z", "fi"))
        or line.startswith("# ")
    )
    for was_active, expect_start in ((0, True), (3, False)):
        log.write_text("")
        (bin_dir / "systemctl").write_text(
            "#!/bin/sh\n"
            f'echo "systemctl $*" >> {log}\n'
            f'[ "$1" = is-active ] && exit {was_active}\n'
            "exit 0\n"
        )
        subprocess.run(
            ["sh", "-c", "set -eu\n" + tail],
            check=True,
            env={"PATH": f"{bin_dir}:/usr/bin:/bin"},
        )
        started = "systemctl start track-overflow-agent.service" in log.read_text()
        assert started is expect_start
