// Maintenance mode: block closures and switch positions set by hand.
import QtQuick
import QtQuick.Layouts
import "../components"
import "../panels"

ColumnLayout {
    id: root

    spacing: theme.space_3

    ModeCallout {
        Layout.fillWidth: true
        variant: "warning"
        heading: qsTr("Maintenance mode")
        body: qsTr("Dispatching is suspended on affected blocks. You set "
            + "switch positions and block closures by hand. Every command "
            + "here is confirmed before it is sent to the track controller.")
    }

    RowLayout {
        Layout.fillWidth: true
        spacing: theme.space_3

        CloseBlockPanel {
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.preferredWidth: 1
        }

        SwitchPanel {
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.preferredWidth: 1
        }
    }

    RowLayout {
        Layout.fillWidth: true
        Layout.fillHeight: true
        spacing: theme.space_3

        ClosuresPanel {
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.preferredWidth: 343
        }

        ThroughputPanel {
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.preferredWidth: 405
        }
    }
}
