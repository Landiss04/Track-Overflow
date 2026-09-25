// Safety-critical control, style guide 7. Minimum 44 px by 200 px, --danger
// fill, uppercase label with 0.05em tracking, and an explicit confirmation
// step. Only the Train Controller emergency brake is unconfirmed, so the
// Train Model's passenger brake confirms.
import QtQuick
import QtQuick.Layouts

Item {
    id: root

    property string label: ""
    property string releaseLabel: "Release emergency brake"
    property bool applied: false         // engaged state: shows the darker
                                         // release control instead of apply
    property string confirmLabel: "Confirm"
    property string cancelLabel: "Cancel"
    property string tooltip: ""          // optional hover text (native ToolTip)
    signal confirmed()

    property bool armed: false

    implicitHeight: theme.safety_min_height
    implicitWidth: Math.max(theme.safety_min_width, row.implicitWidth)

    AppButton {
        anchors.fill: parent
        visible: !root.armed
        variant: "danger"
        active: root.applied
        size: "large"
        text: (root.applied ? root.releaseLabel : root.label).toUpperCase()
        tooltip: root.tooltip
        font.letterSpacing: theme.safety_letter_spacing
        onClicked: root.armed = true
    }

    RowLayout {
        id: row
        anchors.fill: parent
        visible: root.armed
        spacing: theme.space_3

        AppButton {
            Layout.fillWidth: true
            Layout.fillHeight: true
            variant: "danger"
            size: "large"
            text: root.confirmLabel.toUpperCase()
            font.letterSpacing: theme.safety_letter_spacing
            onClicked: {
                root.armed = false;
                root.confirmed();
            }
        }

        AppButton {
            Layout.fillHeight: true
            variant: "ghost"
            size: "large"
            text: root.cancelLabel
            onClicked: root.armed = false
        }
    }
}
