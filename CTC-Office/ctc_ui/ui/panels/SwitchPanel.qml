// Set a switch position and send it to the track controller.
import QtQuick
import QtQuick.Layouts
import "../components"

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

        FormField {
            Layout.preferredWidth: 120
            label: qsTr("Line")

            SelectField {
                id: lineSelect
                Layout.fillWidth: true
                model: root.lineOptions
                currentIndex: -1
            }
        }

        FormField {
            Layout.fillWidth: true
            label: qsTr("Switch")

            SelectField {
                id: switchSelect
                Layout.fillWidth: true
                mono: true
                model: root.switchOptions
                currentIndex: -1
            }
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
        onClicked: root.sendRequested(lineSelect.currentText,
            switchSelect.currentText, positionToggle.currentIndex)
    }

    HelperText {
        Layout.fillWidth: true
        text: root.lastConfirmation === ""
            ? qsTr("No command sent.") : root.lastConfirmation
    }

    Item { Layout.fillHeight: true }
}
