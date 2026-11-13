"""The harness warns about software rendering and tells its modules."""

import os

import pytest
from common.harness import app
from utils import render_check


def run_check(monkeypatch, found):
    monkeypatch.delenv(render_check.LOW_FRAME_RATE_ENV, raising=False)
    monkeypatch.setattr(render_check, "detect", lambda: found)
    app._check_rendering()


def test_software_rendering_warns_and_flags_the_modules(monkeypatch, capsys):
    run_check(monkeypatch, ("the GL renderer is 'llvmpipe'", "OpenGL, llvmpipe"))
    captured = capsys.readouterr()
    assert os.environ[render_check.LOW_FRAME_RATE_ENV] == "1"
    assert "WARNING: software rendering" in captured.err
    assert "llvmpipe" in captured.err
    assert "Rendering: OpenGL, llvmpipe" in captured.out
    monkeypatch.delenv(render_check.LOW_FRAME_RATE_ENV)


def test_gpu_rendering_prints_what_was_seen_and_flags_nothing(
    monkeypatch, capsys
):
    run_check(monkeypatch, (None, "graphics API OpenGL, GL renderer Adreno"))
    captured = capsys.readouterr()
    assert render_check.LOW_FRAME_RATE_ENV not in os.environ
    assert captured.err == ""
    assert "Adreno" in captured.out
