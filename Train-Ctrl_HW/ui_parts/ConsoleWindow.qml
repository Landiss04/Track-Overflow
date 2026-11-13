// The driver's console window.
//
// One window, one job: the Test bench is a separate window with its
// own entry point, because the two are launched from the home page
// rather than navigated between. Nothing here can reach it.
//
// The design is laid out once on the shared 1440 x 900 reference canvas
// and scaled as a whole; main.py keeps the window at 16:10 on Windows.
// Never resize the window from here (see documents/SCALING_GUIDE.md).
import QtQuick
import QtQuick.Layouts
import "../../ui"
import "components"
import "panels"
import "views"

ScaledWindow {
    id: window

    readonly property var s: controller.snapshot

    // "SW Train Controller — Green Line" or "HW Train Controller — Red
    // Line" under a harness; standalone, the variant alone (M13).
    title: window.s.window_title

    ColumnLayout {
        anchors.fill: parent
        spacing: 0
        // While the gains dialog is up the console behind it is out of
        // reach, for the keyboard as well as the mouse (guide 8).
        enabled: window.s.operator !== "engineer"

        // Guide 6.7: name and instance, the mode badge, the clock, and
        // the persistent fault badge an active emergency brake requires.
        ConsoleHeader {
            Layout.fillWidth: true
            moduleName: window.s.module_name
            line: window.s.line_name
            instance: window.s.has_train ? window.s.train_id : ""
            mode: window.s.has_train ? window.s.mode_label : ""
            clock: window.s.clock
            underground: window.s.beacon_underground
            paused: window.s.paused
            faulted: window.s.emergency_brake
            // One badge per subsystem the Train Model reports failed,
            // up only while the failure is up, like the e-brake's.
            dwellLeft: window.s.dwell_left
            alerts: [
                window.s.fault_engine ? qsTr("Engine fault") : "",
                window.s.fault_pickup ? qsTr("Signal pickup fault") : "",
                window.s.fault_brake ? qsTr("Brake fault") : "",
                window.s.vital_breach ? qsTr("Vitality breach") : ""
            ].filter(function (label) { return label !== ""; })
        }

        OperatorBar {
            Layout.fillWidth: true
        }

        // The console does not exist until an operator signs in.
        StackLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            currentIndex: !window.s.signed_in ? 0
                : !window.s.has_train ? 2 : 1

            SignInView {}
            ConsoleView {}

            // Nothing runs until a train exists: the test bench spawns
            // it standalone, the CTC Office dispatches it under a
            // harness, onto this window's line.
            Item {
                EmptyState {
                    anchors.centerIn: parent
                    heading: window.s.line_name === ""
                        ? qsTr("No train selected")
                        : qsTr("Waiting for a %1 train")
                            .arg(window.s.line_name)
                    body: window.s.line_name === ""
                        ? qsTr("Spawn one on the test bench, then pick it "
                               + "from Current selected train above.")
                        : qsTr("Dispatch one from the CTC Office, then "
                               + "pick it from Current selected train "
                               + "above.")
                }
            }
        }
    }

    // Drawn inside the canvas so it scales with the console behind it.
    GainsDialog {
        anchors.fill: parent
    }
}
