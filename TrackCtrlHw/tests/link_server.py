"""Serve wayside 1 over the test link, for test_link. Not a test.

    python tests/link_server.py SERVER_NAME TIMEOUT_S
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtCore import QCoreApplication, QTimer  # noqa: E402

from tests.support import loaded  # noqa: E402
from track_ctrl_hw.link import TestLinkServer  # noqa: E402


def main() -> int:
    """Serve until the timeout, so a crashed test cannot leave it running."""
    app = QCoreApplication(sys.argv[:1])
    controller = loaded(1)
    server = TestLinkServer(controller, sys.argv[1])
    if not server.listen():
        return 2
    print("ready", flush=True)
    QTimer.singleShot(int(float(sys.argv[2]) * 1000), app.quit)
    code = app.exec()
    server.close()
    return code


if __name__ == "__main__":
    sys.exit(main())
