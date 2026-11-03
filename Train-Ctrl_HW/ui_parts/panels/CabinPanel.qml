// Doors, cabin temperature and lights: everything the driver touches
// at a station stop.
import QtQuick
import QtQuick.Layouts
import "../../../ui"
import "../components"

Panel {
    id: root

    readonly property var s: controller.snapshot

    title: qsTr("Cab controls")
    headerItems: [
        // Whether the driver may work the doors now: a tile is live
        // when it may be pressed, greyed when it may not, and the
        // tiles say which side is open.
        StatusBadge {
            readonly property bool free: root.s.door_left_live
                || root.s.door_right_live
            label: !root.s.can_drive ? qsTr("Locked")
                : free ? qsTr("Doors free") : qsTr("Doors locked")
            variant: root.s.can_drive && free ? "ok" : "idle"
        }
    ]

<<<<<<< HEAD
<<<<<<< HEAD
    // Only the platform side opens, and only at a stand; an open door
    // can always be closed, so a door left open when the platform side
    // changes is not stuck. A moving train says why it will not open.
=======
    // Either side opens at a stand, only the platform side at a
    // station (REQUIREMENTS.md M6); an open door can always be closed.
    // A tile that cannot act now is greyed.
>>>>>>> origin/Train_Ctrl_integration
=======
    // REQUIREMENTS.md M6: either side opens at a stand away from a
    // station; at a station the controller opens the platform side,
    // closes it after the dwell, and closes any door for a new Track
    // Signal. A tile that cannot act now is greyed.
>>>>>>> integrate/quirky-into-development-resolved
    RowLayout {
        Layout.fillWidth: true
        spacing: theme.space_2

        ToggleTile {
            Layout.fillWidth: true
<<<<<<< HEAD
<<<<<<< HEAD
            enabled: root.s.can_drive && (root.s.fb_doors_left
                || (root.s.platform_left && root.s.at_stand))
            on: root.s.fb_doors_left
            tone: "info"
            text: root.s.fb_doors_left ? qsTr("Close left")
                : root.s.at_stand ? qsTr("Open left")
                : qsTr("Left: stop first")
=======
            enabled: root.s.can_drive
                && (root.s.fb_doors_left || root.s.may_open_left)
            on: root.s.fb_doors_left
            tone: "info"
            text: root.s.fb_doors_left ? qsTr("Close left")
                                       : qsTr("Open left")
>>>>>>> origin/Train_Ctrl_integration
=======
            enabled: root.s.door_left_live
            on: root.s.fb_doors_left
            tone: "info"
            text: root.s.fb_doors_left ? qsTr("Close left")
                                       : qsTr("Open left")
>>>>>>> integrate/quirky-into-development-resolved
            onClicked: controller.set_door("left", !root.s.fb_doors_left)
        }

        ToggleTile {
            Layout.fillWidth: true
<<<<<<< HEAD
<<<<<<< HEAD
            enabled: root.s.can_drive && (root.s.fb_doors_right
                || (root.s.platform_right && root.s.at_stand))
            on: root.s.fb_doors_right
            tone: "info"
            text: root.s.fb_doors_right ? qsTr("Close right")
                : root.s.at_stand ? qsTr("Open right")
                : qsTr("Right: stop first")
=======
            enabled: root.s.can_drive
                && (root.s.fb_doors_right || root.s.may_open_right)
            on: root.s.fb_doors_right
            tone: "info"
            text: root.s.fb_doors_right ? qsTr("Close right")
                                        : qsTr("Open right")
>>>>>>> origin/Train_Ctrl_integration
=======
            enabled: root.s.door_right_live
            on: root.s.fb_doors_right
            tone: "info"
            text: root.s.fb_doors_right ? qsTr("Close right")
                                        : qsTr("Open right")
>>>>>>> integrate/quirky-into-development-resolved
            onClicked: controller.set_door("right", !root.s.fb_doors_right)
        }
    }

    TempDial {
        Layout.fillWidth: true
        Layout.fillHeight: true
        target: root.s.target_temp_f
        actual: root.s.cabin_temp_f
        interactive: root.s.can_drive
        onTargetRequested: function (degrees) {
            controller.set_target_temp_f(degrees);
        }
    }

    RowLayout {
        Layout.fillWidth: true
        spacing: theme.space_2

        ToggleTile {
            Layout.fillWidth: true
            enabled: root.s.can_drive
            on: root.s.fb_interior_lights
            text: root.s.fb_interior_lights ? qsTr("Interior on")
                                            : qsTr("Interior off")
            onClicked: controller.set_interior_lights(
                !root.s.fb_interior_lights)
        }

        ToggleTile {
            Layout.fillWidth: true
            enabled: root.s.can_drive
            on: root.s.fb_exterior_lights
            text: root.s.fb_exterior_lights ? qsTr("Exterior on")
                                            : qsTr("Exterior off")
            onClicked: controller.set_exterior_lights(
                !root.s.fb_exterior_lights)
        }
    }
}
