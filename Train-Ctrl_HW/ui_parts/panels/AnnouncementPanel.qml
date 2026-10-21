// Station announcement. The controller only sends the command and the
// Train Model makes the announcement (REQUIREMENTS.md M7). The station
// announcements go out automatically, so in Automatic the control says
// so instead of inviting a press.
import QtQuick
import QtQuick.Layouts
import "../../../ui"

Panel {
    id: root

    readonly property var s: controller.snapshot

    title: qsTr("Announcements")
    headerItems: [
        StatusBadge {
            label: qsTr("Sent")
            variant: "info"
            visible: root.s.announcing
        }
    ]

    AppButton {
        id: button
        Layout.fillWidth: true
        // Room for two lines whatever the label says, so the panel
        // never changes height when the label does.
        Layout.preferredHeight: 2 * fit.height + 2 * theme.space_3
        size: "large"
        variant: "secondary"
        text: root.s.announce_label
        enabled: root.s.can_drive && !root.s.announcing
        onClicked: controller.announce()

        // The shared button's label, wrapping onto a second line
        // instead of eliding when the panel is narrow.
        contentItem: Text {
            text: button.text
            color: button.labelColor
            font.family: theme.ui_family
            font.pixelSize: button.labelSize
            font.weight: theme.weight_bold
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
            wrapMode: Text.WordWrap
            maximumLineCount: 2
            elide: Text.ElideRight
        }

        FontMetrics {
            id: fit
            font.family: theme.ui_family
            font.pixelSize: button.labelSize
            font.weight: theme.weight_bold
        }
    }
}
