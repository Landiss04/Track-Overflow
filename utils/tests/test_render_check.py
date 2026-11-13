"""Software rendering is recognised from the environment, Qt and the GL renderer."""

import os
import subprocess
import sys

import pytest
from utils.render_check import software_reason


@pytest.mark.parametrize(
    "env, api, renderer, found",
    [
        ({}, "OpenGL", "llvmpipe (LLVM 21.1.8, 256 bits)", "llvmpipe"),
        ({}, "OpenGL", "Microsoft Basic Render Driver", "Basic Render"),
        ({}, "OpenGL", "Mesa Intel(R) UHD Graphics", None),
        ({}, "OpenGL", "NVIDIA GeForce RTX", None),
        ({}, "Direct3D11", None, None),
        ({}, "Software", None, "Software"),
        ({"QT_QUICK_BACKEND": "software"}, "OpenGL", None, "QT_QUICK_BACKEND"),
        ({"LIBGL_ALWAYS_SOFTWARE": "1"}, "OpenGL", "Adreno", "LIBGL"),
        ({"LIBGL_ALWAYS_SOFTWARE": "0"}, "OpenGL", "Adreno", None),
    ],
)
def test_software_reason(env, api, renderer, found):
    reason = software_reason(env, api, renderer)
    assert (reason is None) if found is None else (found in reason)


def test_detect_reports_the_software_backend_in_a_real_qt():
    code = (
        "from PySide6.QtGui import QGuiApplication;"
        "app = QGuiApplication([]);"
        "from utils.render_check import detect;"
        "print(detect()[0])"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True, text=True, check=True,
        env=dict(os.environ, QT_QPA_PLATFORM="offscreen",
                 QT_QUICK_BACKEND="software"),
    )
    assert "QT_QUICK_BACKEND" in result.stdout
