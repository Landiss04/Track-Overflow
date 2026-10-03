// Labeled input with typed commits; validation never sends partial numbers.
import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

ColumnLayout {
    id: root

    property string label: ""
    // Clear where the surrounding row already names the field; the label
    // is still used as the accessible name.
    property bool labelVisible: true
    property string kind: "string" // int | float | string
    property alias text: editor.text
    readonly property bool valid: kind === "string" || editor.acceptableInput
    property string errorMessage: kind === "int"
        ? qsTr("Enter a whole number.") : qsTr("Enter a number.")
    signal committed(var value)

    spacing: theme.space_1
    opacity: enabled ? 1.0 : 0.42

    FieldLabel {
        Layout.fillWidth: true
        text: root.label.toUpperCase()
        visible: root.labelVisible && root.label !== ""
    }

    TextField {
        id: editor
        objectName: "valueEditor"
        Layout.fillWidth: true
        implicitHeight: theme.control_h_md
        leftPadding: theme.space_3
        rightPadding: theme.space_3
        color: theme.text_primary
        font.family: theme.mono_family
        font.pixelSize: theme.size_small
        selectByMouse: true
        Accessible.name: root.label
        validator: root.kind === "int" ? intValidator
            : root.kind === "float" ? doubleValidator : null

        IntValidator { id: intValidator; locale: "C" }
        DoubleValidator {
            id: doubleValidator
            locale: "C"
            notation: DoubleValidator.StandardNotation
        }

        background: Rectangle {
            radius: theme.radius_md
            color: theme.bg_sunken
            border.color: !root.valid ? theme.danger
                : editor.activeFocus ? theme.accent : theme.border_strong
            Rectangle {
                anchors.fill: parent
                anchors.margins: -4
                radius: theme.radius_md + 4
                visible: editor.activeFocus
                color: "transparent"
                border.width: 2
                border.color: theme.focus_ring
            }
        }

        // editingFinished fires on Return and again on focus loss; only
        // commit text that has not already been committed.
        property var lastCommittedText: undefined
        onTextChanged: if (text !== lastCommittedText) lastCommittedText = undefined

        onEditingFinished: {
            if (!root.valid || text === lastCommittedText) return;
            if (root.kind === "string") {
                lastCommittedText = text;
                root.committed(text);
            } else {
                const value = Number.fromLocaleString(Qt.locale("C"), text);
                if (Number.isFinite(value)) {
                    lastCommittedText = text;
                    root.committed(value);
                }
            }
        }
    }

    HelperText {
        Layout.fillWidth: true
        visible: !root.valid
        text: root.errorMessage
        color: theme.danger
    }
}
