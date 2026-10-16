// The Train Model interface bench, in its own window.
//
// Separate from the console on purpose: the two are launched from the
// home page, not navigated between, so neither can reach the other.
// Run both at once from one process (main.py --both) and the bench
// drives the console beside it; run main.py --test alone and it
// drives a controller with no console attached, which is still a
// controller.
import QtQuick
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
            faulted: window.s.emergency_brake
            alerts: [
                window.s.fault_engine ? qsTr("Engine fault") : "",
                window.s.fault_pickup ? qsTr("Signal pickup fault") : "",
                window.s.fault_brake ? qsTr("Brake fault") : ""
            ].filter(function (label) { return label !== ""; })
        }

        TestView {
            Layout.fillWidth: true
            Layout.fillHeight: true
        }
    }
}
