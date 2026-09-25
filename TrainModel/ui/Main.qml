// Train Model application window.
import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "components"

ApplicationWindow {
    id: window

    readonly property var snapshot: trainModel.snapshot

    visible: true
    width: 1440
    height: 900
    minimumWidth: 1120
    minimumHeight: 720
    title: qsTr("Train Model")
    color: theme.bg_app

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

        // Keep the content stack inside a row layout. This constrains the
        // ScrollViews to the window width now that the navigation rail has
        // moved into the module header.
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
