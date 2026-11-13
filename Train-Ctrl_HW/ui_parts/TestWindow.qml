// The test bench, in its own window, standing in for the central
// harness (main.py --test). Spawning a train opens its line's console:
// HW for the Red Line, SW for the Green (OPEN_ISSUES.md #45). The
// self-check runs it beside one console on one backend.
import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "../../ui"
import "components"
import "views"

ScaledWindow {
    id: window

    readonly property var s: controller.snapshot

    title: qsTr("Train Controller test bench")

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        // The E-brake badge is the emergency brake and nothing else;
        // failures get their own pills, as on the console.
        ConsoleHeader {
            Layout.fillWidth: true
            moduleName: qsTr("Train Controller test bench")
            instance: window.s.has_train ? window.s.train_id : ""
            mode: window.s.has_train ? window.s.mode_label : ""
            clock: window.s.clock
            underground: window.s.beacon_underground
            paused: window.s.paused
            faulted: window.s.emergency_brake
            dwellLeft: window.s.dwell_left
            alerts: [
                window.s.fault_engine ? qsTr("Engine fault") : "",
                window.s.fault_pickup ? qsTr("Signal pickup fault") : "",
                window.s.fault_brake ? qsTr("Brake fault") : "",
                window.s.vital_breach ? qsTr("Vitality breach") : ""
            ].filter(function (label) { return label !== ""; })

            // Set the bench clock, to test the 18:00 and 06:00 lights:
            // typed as HH:MM or HH:MM:SS, set with Return or the button.
            // Greyed under a harness, whose clock is the time.
            clockTools: [
                TextField {
                    id: timeField
                    objectName: "benchTimeField"
                    implicitWidth: 92
                    implicitHeight: theme.control_h_sm
                    enabled: window.s.bench_clock
                    opacity: enabled ? 1.0 : 0.42
                    text: "18:00:00"
                    placeholderText: "HH:MM:SS"
                    color: theme.text_primary
                    font.family: theme.mono_family
                    font.pixelSize: theme.size_small
                    horizontalAlignment: TextInput.AlignHCenter
                    selectByMouse: true
                    Accessible.name: qsTr("Bench time")
                    onAccepted: controller.set_bench_time(text)
                    background: Rectangle {
                        radius: theme.radius_md
                        color: theme.bg_sunken
                        border.color: timeField.activeFocus
                            ? theme.accent : theme.border_strong
                    }
                },
                AppButton {
                    objectName: "benchTimeButton"
                    size: "small"
                    variant: "secondary"
                    text: qsTr("Set time")
                    enabled: window.s.bench_clock
                    tooltip: window.s.bench_clock
                        ? qsTr("Set the bench clock to the time typed")
                        : qsTr("The harness's clock sets the time")
                    onClicked: controller.set_bench_time(timeField.text)
                }
            ]
        }

        TestView {
            Layout.fillWidth: true
            Layout.fillHeight: true
        }
    }
}
