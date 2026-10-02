// HW Train Controller window.
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
            faulted: window.s.emergency_brake
        }

        OperatorBar {
            Layout.fillWidth: true
        }

        // The console does not exist until an operator signs in.
        StackLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            currentIndex: window.s.signed_in ? 1 : 0

            SignInView {}
            ConsoleView {}
        }
    }

    // Drawn inside the canvas so it scales with the console behind it.
    GainsDialog {
        anchors.fill: parent
    }
}
