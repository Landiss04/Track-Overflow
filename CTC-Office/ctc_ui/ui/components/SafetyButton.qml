// Safety-critical control, style guide 7. Minimum 44 px by 200 px,
// --danger fill, uppercase label with 0.05em tracking, and an explicit
// confirmation step before `confirmed` is emitted.
import QtQuick
import QtQuick.Layouts

Item {
    id: root

    property string label: ""
    property string confirmLabel: qsTr("Confirm")
    property string cancelLabel: qsTr("Cancel")
    property bool armed: false
    signal confirmed()

    implicitHeight: theme.safety_min_height
    implicitWidth: Math.max(theme.safety_min_width, row.implicitWidth)

    // Disarm if the control is disabled mid-confirmation, e.g. when the
    // selection that enabled it is cleared.
    onEnabledChanged: if (!enabled) armed = false

    AppButton {
        anchors.fill: parent
        visible: !root.armed
        variant: "danger"
        size: "large"
        text: root.label.toUpperCase()
        font.letterSpacing: theme.safety_letter_spacing
        onClicked: root.armed = true
    }

    RowLayout {
        id: row
        anchors.fill: parent
        visible: root.armed
        spacing: theme.space_3

        AppButton {
            Layout.fillHeight: true
            variant: "ghost"
            size: "large"
            text: root.cancelLabel
            onClicked: root.armed = false
        }

        AppButton {
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.minimumWidth: theme.safety_min_width
            variant: "danger"
            size: "large"
            text: root.confirmLabel.toUpperCase()
            font.letterSpacing: theme.safety_letter_spacing
            onClicked: {
                root.armed = false;
                root.confirmed();
            }
        }
    }
}
