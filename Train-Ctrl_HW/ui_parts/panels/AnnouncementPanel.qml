// Station announcement. The controller only sends the command and the
// Train Model makes the announcement (REQUIREMENTS.md M7). In Automatic
// the command goes out on the approach to a station, so the control
// reports that instead of inviting a press.
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
        Layout.fillWidth: true
        size: "large"
        variant: "secondary"
        text: root.s.announce_label
        enabled: root.s.can_drive && !root.s.announcing
        onClicked: controller.announce()
    }
}
