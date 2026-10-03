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

    title: qsTr("HW Train Controller")

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        // Guide 6.7: name and instance, the mode badge, the clock, and
        // the persistent fault badge an active emergency brake requires.
        ModuleHeader {
            Layout.fillWidth: true
            moduleName: qsTr("HW Train Controller")
            // The train and its line are named by the selector below,
            // so the header does not repeat them.
            mode: window.s.signed_in ? window.s.mode_label : qsTr("Signed out")
            clock: window.s.clock
            faulted: window.s.emergency_brake || window.s.faulted
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

            // Nothing runs until a train is spawned, and spawning is
            // the test bench's job, so the console says so and waits.
            Item {
                EmptyState {
                    anchors.centerIn: parent
                    heading: qsTr("No train selected")
                    body: qsTr("Spawn one on the test bench, then pick it "
                               + "from Current selected train above.")
                }
            }
        }
    }

    // Drawn inside the canvas so it scales with the console behind it.
    GainsDialog {
        anchors.fill: parent
    }
}
