// Track Model window. The test UI is a separate process
// (TrackModel/test_ui) and never shares this window.
// Sizing comes from ui/ScaledWindow.qml; main.py installs the aspect
// lock. Never set window geometry here — see documents/SCALING_GUIDE.md.
import QtQuick

import "../../ui"

ScaledWindow {
    id: window

    title: qsTr("Track Model")

    MainView {
        anchors.fill: parent
    }
}
