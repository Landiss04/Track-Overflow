// The dial sets the target. Commanded speed reads in the hero row.
import QtQuick
import QtQuick.Layouts
import "../../../ui"
import "../components"

Panel {
    id: root

    readonly property var s: controller.snapshot

    title: qsTr("Speed")
    headerItems: [
        StatusBadge {
            label: root.s.speed_source
            variant: root.s.manual ? "info" : "idle"
        }
    ]

    SpeedDial {
        Layout.fillWidth: true
        Layout.fillHeight: true
        target: root.s.target_mph
        actual: root.s.actual_mph
        limit: root.s.limit_mph
        interactive: root.s.can_drive && root.s.armed
        onTargetRequested: function (mph) { controller.set_target_mph(mph); }
    }

    // Two lines of room, always: the panel never resizes under the hand
    // that is using it.
    HelperText {
        Layout.fillWidth: true
        Layout.preferredHeight: 34
        horizontalAlignment: Text.AlignHCenter
        text: root.s.dial_hint
    }
}
