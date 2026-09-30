import QtQuick
import QtQuick.Controls.Basic

ApplicationWindow {
    id: window

    // The page is designed at 1680 x 1040, but must not open larger than the
    // screen it lands on.
    width: Math.min(1680, Screen.desktopAvailableWidth - 80)
    height: Math.min(1040, Screen.desktopAvailableHeight - 80)
    minimumWidth: 1280
    minimumHeight: 760
    visible: true
    title: qsTr("CTC / Train System \u2014 Track Controller")
    color: theme.bg_app

    TrackController {
        anchors.fill: parent
    }
}
