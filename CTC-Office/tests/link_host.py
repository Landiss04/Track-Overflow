"""Headless CTC Office link server for the socket link tests.

Serves a fresh stub module on the socket name given as the first
argument, prints ``ready`` once listening, and exits after a few
seconds or when its stdin closes.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtCore import QCoreApplication, QTimer  # noqa: E402

from ctc.model import StubCtcOffice  # noqa: E402
from ctc.socket_link import CtcLinkServer  # noqa: E402

app = QCoreApplication(sys.argv)
module = StubCtcOffice()
server = CtcLinkServer(module, name=sys.argv[1])
if not server.listen():
    print("listen failed", flush=True)
    sys.exit(1)
print("ready", flush=True)


def push_maintenance() -> None:
    # Stands in for the CTC UI changing the module between requests.
    module.set_maintenance_mode(True)
    server.push()


QTimer.singleShot(int(sys.argv[2]) if len(sys.argv) > 2 else 600,
                  push_maintenance)
# Optional: quit after N ms, then shut down like ctc_ui/__main__.py.
QTimer.singleShot(int(sys.argv[3]) if len(sys.argv) > 3 else 8000,
                  app.quit)
app.exec()
server.close()
