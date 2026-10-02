// Window for the CTC Office test UI, a separate process started with
// ctc_ui/test_ui.py. Sizing and scaling come from the shared
// ui/ScaledWindow.qml; test_ui.py installs the matching aspect lock.
import QtQuick
import "../../../../ui"

ScaledWindow {
    title: qsTr("CTC Office — Test harness")

    TestHarnessView {
        anchors.fill: parent
    }
}
