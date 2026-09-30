// Set a switch position and send it to the track controller.
import QtQuick
import QtQuick.Layouts
import "../../../../ui"

Panel {
    id: root

    property var lineOptions: []
    property var switchOptions: []
    // Last acknowledgement from the track controller; empty until one
    // arrives.
    property string lastConfirmation: ""

    // position: 0 = normal, 1 = reverse.
    signal sendRequested(string line, string switchId, int position)

    title: qsTr("Set switch position")

    RowLayout {
        Layout.fillWidth: true
        spacing: theme.space_3

        SelectField {
            id: lineSelect
            Layout.preferredWidth: 120
            label: qsTr("Line")
            model: root.lineOptions
            currentIndex: -1
        }

        SelectField {
            id: switchSelect
            Layout.fillWidth: true
            label: qsTr("Switch")
            model: root.switchOptions
            currentIndex: -1
        }
    }

    FormField {
        Layout.fillWidth: true
        label: qsTr("Position")

        SegmentedToggle {
            id: positionToggle
            Layout.fillWidth: true
            options: [qsTr("Normal"), qsTr("Reverse")]
            currentIndex: -1
            onActivated: function (index) { currentIndex = index; }
        }
    }

    AppButton {
        Layout.fillWidth: true
        variant: "primary"
        text: qsTr("Send to track controller")
        enabled: switchSelect.currentIndex >= 0
            && positionToggle.currentIndex >= 0
        onClicked: root.sendRequested(lineSelect.currentValue,
            switchSelect.currentValue, positionToggle.currentIndex)
    }

    HelperText {
        Layout.fillWidth: true
        text: root.lastConfirmation === ""
            ? qsTr("No command sent.") : root.lastConfirmation
    }

    Item { Layout.fillHeight: true }
}
