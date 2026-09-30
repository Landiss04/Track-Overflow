// Minimized Train Occupancy window, docked over the track view.
import QtQuick
import QtQuick.Layouts
import "../../../../ui"

Rectangle {
    id: root

    property string summary: ""

    signal expandRequested()
    signal closeRequested()

    implicitHeight: theme.control_h_lg
    implicitWidth: row.implicitWidth + theme.space_4 + theme.space_2
    color: theme.bg_surface
    border.color: theme.border_strong
    border.width: 1
    radius: theme.radius_lg

    RowLayout {
        id: row
        anchors.fill: parent
        anchors.leftMargin: theme.space_4
        anchors.rightMargin: theme.space_2
        spacing: theme.space_3

        Text {
            text: qsTr("Train occupancy")
            color: theme.text_primary
            font.family: theme.ui_family
            font.pixelSize: theme.size_small
            font.weight: theme.weight_bold
        }

        HelperText {
            text: root.summary
            color: theme.text_muted
            visible: root.summary !== ""
        }

        Item { Layout.fillWidth: true }

        AppButton {
            variant: "ghost"
            size: "small"
            text: "▴"
            Accessible.name: qsTr("Expand train occupancy")
            onClicked: root.expandRequested()
        }

        AppButton {
            variant: "ghost"
            size: "small"
            text: "×"
            Accessible.name: qsTr("Close train occupancy")
            onClicked: root.closeRequested()
        }
    }
}
