// Train Model application window.
import QtQuick
import QtQuick.Layouts
import QtQuick.Window
import "../../ui"

ScaledWindow {
    id: window

    readonly property var snapshot: trainModel.snapshot

    title: qsTr("Train Model")

    // The design is laid out once at the reference size and scaled as a
    // whole. On Windows, main.py keeps the window at 16:10 while it is
    // resized; any other shape (maximized, snapped, fullscreen, Linux) is
    // letterboxed around the centered canvas.
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
