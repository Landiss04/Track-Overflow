// Track Model test window. Spawned as its own process, so it never
// overlays the Track Model window. Sizing comes from ui/ScaledWindow.qml;
// main.py installs the matching aspect lock. Never set window geometry
// here — see documents/SCALING_GUIDE.md.
import QtQuick

import "../../ui"

ScaledWindow {
    id: window

    title: qsTr("Track Model — Test UI")

    TestView {
        anchors.fill: parent
    }
}
