// Track Controller application window. Sizing, the 1440 x 900 reference
// canvas and the letterbox all come from the shared ui/ScaledWindow.qml;
// main.py installs the matching aspect lock. Never set window geometry here
// — see documents/SCALING_GUIDE.md.
import QtQuick

import "../../ui"

ScaledWindow {
    id: window

    title: qsTr("CTC / Train System \u2014 Track Controller")

    TrackController {
        anchors.fill: parent
    }
}
