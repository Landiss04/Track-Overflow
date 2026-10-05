// Maintenance mode: block closures and switch positions set by hand.
import QtQuick
import QtQuick.Layouts
import "../../../../ui"
import "../panels"

ColumnLayout {
    id: root

    // The CtcHost from __main__.py.
    property var host: null

    spacing: theme.space_3

    Callout {
        Layout.fillWidth: true
        variant: "warning"
        heading: qsTr("Maintenance mode")
        body: qsTr("Dispatching is suspended on affected blocks. You set "
            + "switch positions and block closures by hand. Switch "
            + "commands are released when you leave Maintenance.")
    }

    RowLayout {
        Layout.fillWidth: true
        spacing: theme.space_3

        CloseBlockPanel {
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.preferredWidth: 1
            host: root.host
        }

        SwitchPanel {
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.preferredWidth: 1
            host: root.host
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
            host: root.host
        }

        ThroughputPanel {
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.preferredWidth: 405
            host: root.host
        }
    }
}
