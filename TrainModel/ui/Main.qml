// Train Model application window.
import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import QtQuick.Window
import "components"

ApplicationWindow {
    id: window

    readonly property var snapshot: trainModel.snapshot
    readonly property int referenceWidth: 1440
    readonly property int referenceHeight: 900
    readonly property real canvasScale: Math.min(
        width / referenceWidth, height / referenceHeight)

    visible: true
    width: referenceWidth
    height: referenceHeight
    minimumWidth: 720
    minimumHeight: 450
    title: qsTr("Train Model")
    color: theme.bg_app

    // The design is laid out once at the reference size and scaled as a
    // whole. On Windows, main.py keeps the window at 16:10 while it is
    // resized; any other shape (maximized, snapped, fullscreen, Linux) is
    // letterboxed around the centered canvas.
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

            ModuleHeader {
                Layout.fillWidth: true
                moduleName: qsTr("Train Model")
                instance: window.snapshot.train_id
                mode: window.snapshot.mode
                line: window.snapshot.line
                clock: window.snapshot.clock
                faulted: window.snapshot.emergency_brake
                navigationEntries: [qsTr("Overview"), qsTr("Test harness")]
                currentNavigationIndex: views.currentIndex
                onNavigationActivated: function (index) { views.currentIndex = index; }
            }

            // This fills the fixed reference canvas; the canvas transform
            // scales the complete design uniformly with the window.
            RowLayout {
                Layout.fillWidth: true
                Layout.fillHeight: true
                spacing: 0

                StackLayout {
                    id: views
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    currentIndex: 0

                    MainView {}
                    TestView {}
                }
            }
        }
    }
}
