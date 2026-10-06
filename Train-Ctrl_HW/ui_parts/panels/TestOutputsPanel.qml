// What this controller sends to the Train Model. Read-only: these are
// produced by the control law and the driver's controls, so the way to
// change one is to drive the console, not to type here.
//
// Shown in the display units (documents/units.md): power in
// kilowatts, temperature in Fahrenheit. The payload itself leaves in
// watts and Celsius; this column is the readable side of it, which is
// why it differs from the SI inputs beside it.
//
// The unit sits against its value rather than in a column of its own
// (style guide 6.5), so the pair reads as one figure and lines up
// under the Value heading.
import QtQuick
import QtQuick.Layouts
import "../../../ui"
import "../components"

Panel {
    id: root

    readonly property var s: controller.snapshot

    title: qsTr("Outputs to Train Model")
    headerItems: [
        StatusBadge {
            label: root.s.armed ? qsTr("Sending") : qsTr("Inert")
            variant: root.s.armed ? "ok" : "idle"
        }
    ]

    ColumnLayout {
        Layout.fillWidth: true
        spacing: 0
        // Nothing to read or write until a train exists.
        enabled: controller.snapshot.has_train

        // 260 name + 52 type + 190 value + 56 unit + three gaps, so
        // the header rules sit over the columns below it.
        TableHeader {
            Layout.fillWidth: true
            Layout.bottomMargin: theme.space_1
            nameColumn: qsTr("Signal")
            kindColumn: ""
            valueColumn: qsTr("Value")
            kindWidth: 0
            valueWidth: 150
            unitWidth: 0
        }

        SignalEditRow {
            Layout.fillWidth: true
            rowHeight: 44
            showKind: false
            valueWidth: 150
            inlineUnit: true
            valueSize: theme.size_h3
            name: "power_commanded"
            kind: "float"
            unit: "kW"
            value: Number(root.s.power_kw).toFixed(1)
        }
        SignalEditRow {
            Layout.fillWidth: true
            rowHeight: 44
            showKind: false
            valueWidth: 150
            inlineUnit: true
            valueSize: theme.size_h3
            name: "service_brake_command"
            kind: "bool"
            value: root.s.service_brake
        }
        SignalEditRow {
            Layout.fillWidth: true
            rowHeight: 44
            showKind: false
            valueWidth: 150
            inlineUnit: true
            valueSize: theme.size_h3
            name: "emergency_brake_command"
            kind: "bool"
            value: root.s.emergency_brake
        }
        SignalEditRow {
            Layout.fillWidth: true
            rowHeight: 44
            showKind: false
            valueWidth: 150
            inlineUnit: true
            valueSize: theme.size_h3
            name: "door_command_left"
            kind: "bool"
            value: root.s.doors_left
        }
        SignalEditRow {
            Layout.fillWidth: true
            rowHeight: 44
            showKind: false
            valueWidth: 150
            inlineUnit: true
            valueSize: theme.size_h3
            name: "door_command_right"
            kind: "bool"
            value: root.s.doors_right
        }
        SignalEditRow {
            Layout.fillWidth: true
            rowHeight: 44
            showKind: false
            valueWidth: 150
            inlineUnit: true
            valueSize: theme.size_h3
            name: "cabin_lights_command"
            kind: "bool"
            value: root.s.lights
        }
        SignalEditRow {
            Layout.fillWidth: true
            rowHeight: 44
            showKind: false
            valueWidth: 150
            inlineUnit: true
            valueSize: theme.size_h3
            name: "headlights_command"
            kind: "bool"
            value: root.s.headlights
        }
        SignalEditRow {
            Layout.fillWidth: true
            rowHeight: 44
            showKind: false
            valueWidth: 150
            inlineUnit: true
            valueSize: theme.size_h3
            rule: false
            name: "temperature_setpoint"
            kind: "int"
            unit: "\u00b0F"
            value: Math.round(root.s.target_temp_f)
        }
    }

    Item { Layout.fillHeight: true }
}
