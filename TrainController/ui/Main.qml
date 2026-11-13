// Train Controller application window.
import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import QtQuick.Window
import "components"

ApplicationWindow {
    id: window

    readonly property var snapshot: controller.snapshot
    readonly property int referenceWidth: 1440
    readonly property int referenceHeight: 900
    readonly property real canvasScale: Math.min(
        width / referenceWidth, height / referenceHeight)

    visible: true
    width: referenceWidth
    height: referenceHeight
    minimumWidth: 720
    minimumHeight: 450
    title: qsTr("Train Controller")
    color: theme.bg_app

    // The design is laid out once at the reference size and scaled as a
    // whole. On Windows, main.py keeps the window at 16:10 while it is
    // resized; any other shape is letterboxed around the centered canvas.
    Item {
        id: designCanvas

        width: window.referenceWidth
        height: window.referenceHeight
        x: (window.width - width * window.canvasScale) / 2
        y: (window.height - height * window.canvasScale) / 2
        transform: Scale {
            origin.x: 0
            origin.y: 0
            xScale: window.canvasScale
            yScale: window.canvasScale
        }

        ColumnLayout {
            anchors.fill: parent
            spacing: 0

            CabHeader {
                Layout.fillWidth: true
                snapshot: window.snapshot
                onUserSelected: function (role) { controller.setUser(role); }
                onModeSelected: function (mode) { controller.setMode(mode); }
            }

            CabView {
                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.margins: theme.space_3
            }
        }

        EngineerGainsPopup {
            anchors.fill: parent
            visible: window.snapshot.user_role === "Engineer"
            snapshot: window.snapshot
            onCloseRequested: controller.setUser("Driver")
        }
    }
}
