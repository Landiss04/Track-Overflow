// Train Model test UI window. Runs in its own process (test_ui.py) and
// stands in for the Track Model, the Train Controller and the clock,
// driving the Train Model's process through its interface.
import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import QtQuick.Window
import "../../ui"

ScaledWindow {
    id: window

    title: qsTr("Train Model Test UI")

    // Laid out once at the reference size and scaled as a whole, the
    // same way as the Train Model window (Main.qml).
    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        ModuleHeader {
            Layout.fillWidth: true
            moduleName: qsTr("Train Model Test UI")
            mode: !harness.connected ? harness.disconnectedReason
                : harness.running ? qsTr("Running") : qsTr("Paused")
            clock: harness.elapsed
            faulted: !harness.connected || harness.emergencyBrakeActive

            // Which train the page shows and edits, right after the
            // badges, as in the Train Model window. Every train is
            // stepped each tick, whichever is shown.
            statusExtras: [
                SelectField {
                    objectName: "trainSelector"
                    Layout.preferredWidth: 140
                    Layout.fillWidth: false
                    label: qsTr("Train")
                    labelVisible: false
                    model: harness.trainIds
                    currentIndex: harness.selectedIndex
                    onCommitted: function (value) {
                        harness.selectTrain(value);
                    }
                },
                AppButton {
                    objectName: "addTrain"
                    size: "small"
                    text: qsTr("Add train")
                    enabled: harness.connected
                    onClicked: harness.addTrain()
                },
                AppButton {
                    objectName: "removeTrain"
                    size: "small"
                    variant: "ghost"
                    text: qsTr("Remove train")
                    enabled: harness.connected && harness.canRemoveTrain
                    onClicked: harness.removeTrain()
                }
            ]
        }

        TestView {
            Layout.fillWidth: true
            Layout.fillHeight: true
        }
    }
}
