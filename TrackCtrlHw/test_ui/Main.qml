// Track Controller test window. Spawned as its own process, so it is a
// window in its own right and never overlays the Track Controller UI.
// Sizing and the 1440 x 900 reference canvas come from ui/ScaledWindow.qml;
// main.py installs the matching aspect lock. Never set window geometry here
// — see documents/SCALING_GUIDE.md.
import QtQuick

import "../../ui"

ScaledWindow {
    id: window

    title: qsTr("CTC / Train System \u2014 Track Controller Test UI")

    TestView {
        anchors.fill: parent
    }
}
