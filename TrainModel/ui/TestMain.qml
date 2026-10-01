// Train Model test UI window. Runs in its own process (test_ui.py) and
// stands in for the Track Model, the Train Controller and the clock,
// driving the Train Model's process through its interface.
import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import QtQuick.Window
import "../../ui"

ApplicationWindow {
    id: window

    readonly property int referenceWidth: 1440
    readonly property int referenceHeight: 900
    readonly property real canvasScale: Math.min(
        width / referenceWidth, height / referenceHeight)

    visible: true
    width: referenceWidth
    height: referenceHeight
    minimumWidth: 720
    minimumHeight: 450
    title: qsTr("Train Model Test UI")
    color: theme.bg_app

    // Laid out once at the reference size and scaled as a whole, the
    // same way as the Train Model window (Main.qml).
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
                moduleName: qsTr("Train Model Test UI")
                mode: !harness.connected ? qsTr("Not connected")
                    : harness.running ? qsTr("Running") : qsTr("Paused")
                clock: harness.elapsed
                faulted: !harness.connected || harness.emergencyBrakeActive
            }

            TestView {
                Layout.fillWidth: true
                Layout.fillHeight: true
            }
        }
    }
}
