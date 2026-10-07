// Every number behind the four readouts, one press away. Closed by
// default: the driving view shows what is needed to drive, and this is
// what is needed to debug.
import QtQuick
import QtQuick.Layouts
import "../../../ui"

ColumnLayout {
    id: root

    property bool expanded: false
    readonly property var s: controller.snapshot

    // Display units only (truth conventions/units.md): the backend converted
    // these on the way out, so nothing here does arithmetic beyond
    // rounding.
    function mph(value) { return Math.round(value) + " mph"; }
    function kilowatts(value) { return Number(value).toFixed(1) + " kW"; }

    spacing: 0

    AppButton {
        id: disclosure
        Layout.fillWidth: true
        variant: "ghost"
        size: "small"
        implicitHeight: theme.control_h_md
        text: root.expanded ? qsTr("Hide all numbers")
                            : qsTr("Show all numbers")
        onClicked: root.expanded = !root.expanded

        background: Rectangle {
            color: disclosure.hovered ? theme.accent_subtle : theme.bg_raised

            Rectangle {
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.bottom: parent.bottom
                implicitHeight: 1
                color: theme.border
            }

            Rectangle {
                anchors.fill: parent
                anchors.margins: -4
                visible: disclosure.visualFocus
                color: "transparent"
                border.width: 2
                border.color: theme.focus_ring
            }
        }
    }

    RowLayout {
        Layout.fillWidth: true
        Layout.topMargin: theme.space_2
        Layout.leftMargin: theme.space_4
        Layout.rightMargin: theme.space_4
        Layout.bottomMargin: 0
        spacing: theme.space_4
        visible: root.expanded

        Card {
            Layout.fillWidth: true
            Layout.preferredWidth: 1
            Layout.alignment: Qt.AlignTop
            title: qsTr("Motion")

            ColumnLayout {
                Layout.fillWidth: true
                spacing: 2

            KeyValueRow {
                Layout.fillWidth: true
                label: qsTr("Current speed")
                value: root.mph(root.s.actual_mph)
            }
            KeyValueRow {
                Layout.fillWidth: true
                label: qsTr("Target speed")
                value: root.mph(root.s.target_mph)
            }
            KeyValueRow {
                Layout.fillWidth: true
                label: qsTr("Commanded speed")
                value: root.mph(root.s.commanded_mph)
            }
            KeyValueRow {
                Layout.fillWidth: true
                label: qsTr("Speed limit")
                value: root.mph(root.s.limit_mph)
            }
            KeyValueRow {
                Layout.fillWidth: true
                rule: false
                label: qsTr("Acceleration")
                value: Number(root.s.accel_ftps2).toFixed(2) + " ft/s^2"
            }
            }
        }

        Card {
            Layout.fillWidth: true
            Layout.preferredWidth: 1
            Layout.alignment: Qt.AlignTop
            title: qsTr("Engine & brakes")

            ColumnLayout {
                Layout.fillWidth: true
                spacing: 2

            KeyValueRow {
                Layout.fillWidth: true
                label: qsTr("Power command")
                value: root.kilowatts(root.s.power_kw)
            }
            KeyValueRow {
                Layout.fillWidth: true
                label: qsTr("Max engine power")
                value: root.kilowatts(root.s.max_power_kw)
            }
            KeyValueRow {
                Layout.fillWidth: true
                label: qsTr("Service brake")
                value: root.s.service_brake ? qsTr("Engaged")
                                            : qsTr("Released")
            }
            KeyValueRow {
                Layout.fillWidth: true
                label: qsTr("Emergency brake")
                value: root.s.emergency_brake ? qsTr("Engaged")
                                              : qsTr("Released")
            }
            KeyValueRow {
                Layout.fillWidth: true
                rule: false
                label: qsTr("Gains, Kp / Ki")
                value: Math.round(root.s.kp) + " / " + Math.round(root.s.ki)
            }
            }
        }

        Card {
            Layout.fillWidth: true
            Layout.preferredWidth: 1
            Layout.alignment: Qt.AlignTop
            title: qsTr("Equipment status")

            ColumnLayout {
                Layout.fillWidth: true
                spacing: 2

            KeyValueRow {
                Layout.fillWidth: true
                label: qsTr("Engine")
                value: root.s.fault_engine ? qsTr("Fault") : qsTr("Normal")
            }
            KeyValueRow {
                Layout.fillWidth: true
                label: qsTr("Brake")
                value: root.s.fault_brake ? qsTr("Fault") : qsTr("Normal")
            }
            KeyValueRow {
                Layout.fillWidth: true
                label: qsTr("Signal pickup")
                value: root.s.fault_pickup ? qsTr("Fault") : qsTr("Normal")
            }
            KeyValueRow {
                Layout.fillWidth: true
                // A count and an ID, not a measurement: neither is
                // converted.
                label: qsTr("Authority")
                value: qsTr("%1 to block %2").arg(root.s.authority_blocks)
                    .arg(root.s.authority_target)
            }
            KeyValueRow {
                Layout.fillWidth: true
                rule: false
                label: qsTr("Cabin setpoint")
                value: Math.round(root.s.target_temp_f) + " \u00b0F"
            }
            }
        }
    }
}
