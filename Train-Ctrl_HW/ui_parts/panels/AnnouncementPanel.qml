// Station announcement. In Automatic the train announces itself, so the
// control reports that instead of inviting a press.
import QtQuick
import QtQuick.Layouts
import "../../../ui"

Panel {
    id: root

    readonly property var s: controller.snapshot

    title: qsTr("Announcements")
    headerItems: [
        StatusBadge {
            label: qsTr("Announcing")
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
