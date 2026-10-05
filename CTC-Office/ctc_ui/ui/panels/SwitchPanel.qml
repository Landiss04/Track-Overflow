// Set a switch position and send it to the track controller. Only in
// maintenance mode (REQ-FUNC-012); leaving maintenance mode releases
// every commanded switch. Normal is the first connection the layout file
// lists for the switch, reverse the second.
import QtQuick
import QtQuick.Layouts
import "../../../../ui"

Panel {
    id: root

    // The CtcHost from __main__.py.
    property var host: null
    // Result of the last command: an error, or a confirmation.
    property string lastConfirmation: ""
    property bool lastIsError: false

    readonly property string line: lineSelect.currentIndex >= 0
        ? lineSelect.currentValue : ""
    readonly property string switchId: switchSelect.currentIndex >= 0
        ? switchSelect.currentValue : ""
    // Connections and positions of the selected switch.
    readonly property var detail: {
        if (!root.host || root.switchId === "")
            return ({});
        root.host.revision;
        return root.host.switchDetail(root.line, root.switchId);
    }

    function report(error, done) {
        root.lastIsError = error !== "";
        root.lastConfirmation = error !== "" ? error : done;
    }

    title: qsTr("Set switch position")

    RowLayout {
        Layout.fillWidth: true
        spacing: theme.space_3

        SelectField {
            id: lineSelect
            Layout.preferredWidth: 120
            label: qsTr("Line")
            model: root.host ? root.host.lineNames : []
            currentIndex: -1
        }

        SelectField {
            id: switchSelect
            Layout.fillWidth: true
            label: qsTr("Switch")
            textRole: "text"
            valueRole: "value"
            model: root.host && root.line !== ""
                ? root.host.switchOptions(root.line) : []
            currentIndex: -1
        }
    }

    FormField {
        Layout.fillWidth: true
        label: qsTr("Position")

        SegmentedToggle {
            id: positionToggle
            Layout.fillWidth: true
            options: [
                root.detail.normal
                    ? qsTr("Normal (%1)").arg(root.detail.normal)
                    : qsTr("Normal"),
                root.detail.reverse
                    ? qsTr("Reverse (%1)").arg(root.detail.reverse)
                    : qsTr("Reverse")
            ]
            currentIndex: -1
            onActivated: function (index) { currentIndex = index; }
        }
    }

    KeyValueRow {
        Layout.fillWidth: true
        label: qsTr("Reported by track controller")
        value: root.detail.reported || "—"
    }
    KeyValueRow {
        Layout.fillWidth: true
        label: qsTr("Commanded by CTC")
        value: root.detail.commanded || "—"
    }

    RowLayout {
        Layout.fillWidth: true
        spacing: theme.space_2

        AppButton {
            Layout.fillWidth: true
            variant: "primary"
            text: qsTr("Send to track controller")
            enabled: root.switchId !== "" && positionToggle.currentIndex >= 0
            onClicked: root.report(
                root.host.setSwitch(root.line, root.switchId,
                    positionToggle.currentIndex),
                qsTr("Sent: %1 switch %2 → %3.").arg(root.line)
                    .arg(root.switchId)
                    .arg(positionToggle.currentIndex === 0
                        ? qsTr("normal") : qsTr("reverse")))
        }

        AppButton {
            variant: "secondary"
            text: qsTr("Release")
            enabled: root.detail.commanded !== undefined
                && root.detail.commanded !== "—"
            onClicked: root.report(
                root.host.releaseSwitch(root.line, root.switchId),
                qsTr("Released %1 switch %2 to the track controller.")
                    .arg(root.line).arg(root.switchId))
        }
    }

    HelperText {
        Layout.fillWidth: true
        color: root.lastIsError ? theme.danger : theme.text_secondary
        text: root.lastConfirmation === ""
            ? qsTr("No command sent.") : root.lastConfirmation
    }

    Item { Layout.fillHeight: true }
}
