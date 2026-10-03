// Everything that goes into the controller, in two columns of one
// table: the signals the Train Model sends on the left, and the
// controls a driver or an engineer would press at the console on the
// right. The bench runs in its own window, so if a value is not here
// there is no way to feed it in.
//
// The two columns behave differently on purpose. Train Model signals
// are staged: typing fills a draft, edited rows are marked, and Send
// publishes the set in one call, so the controller never sees a
// half-typed set of signals. Cab controls act at once, because they
// are buttons a hand presses, not a message being assembled.
//
// Units differ for the same reason. The left column is the module
// interface, so it is backend SI: m/s, Celsius, a count of blocks.
// The right column is the cab, so it is what the driver reads: mph
// and Fahrenheit (documents/units.md).
import QtQuick
import QtQuick.Layouts
import "../../../ui"
import "../components"

Panel {
    id: root

    readonly property var s: controller.snapshot
    readonly property var aspects: ["RED", "YELLOW", "GREEN", "SUPER GREEN"]
    readonly property var roles: ["Signed out", "Driver", "Engineer"]

    // What the controller is holding right now.
    readonly property var live: ({
        "commanded_speed": Math.round(s.commanded_mps * 100) / 100,
        "authority_blocks": s.authority_blocks,
        "kp": Math.round(s.kp),
        "ki": Math.round(s.ki),
        "beacon": s.beacon,
        "failure_engine": s.fault_engine,
        "failure_brake": s.fault_brake,
        "failure_signal_pickup": s.fault_pickup,
        "cabin_temperature": Math.round(s.cabin_temp_c * 10) / 10,
        "signal_light_ahead": s.next_signal,
        "brake_state": s.fb_brake,
        "door_state_left": s.fb_doors_left,
        "door_state_right": s.fb_doors_right,
        "light_state_cabin": s.fb_lights,
        "light_state_headlights": s.fb_headlights,
        "actual_speed": Math.round(s.actual_mps * 100) / 100
    })

    // What is typed but not sent, and which rows were typed in. The
    // plant keeps running, so rows nobody has touched follow it
    // instead of standing out as edits the moment the train moves.
    property var draft: live
    property var touched: ({})
    readonly property bool dirty: {
        for (var key in touched)
            if (pending(key))
                return true;
        return false;
    }

    onLiveChanged: {
        var next = {};
        for (var key in live)
            next[key] = touched[key] ? draft[key] : live[key];
        draft = next;
    }

    function stage(key, value) {
        var next = {};
        for (var k in draft)
            next[k] = draft[k];
        next[key] = value;
        draft = next;
        var marks = {};
        for (var j in touched)
            marks[j] = touched[j];
        marks[key] = true;
        touched = marks;
    }

    function pending(key) {
        return String(draft[key]) !== String(live[key]);
    }

    function release() {
        draft = live;
        touched = ({});
    }

    title: qsTr("Inputs")
    headerItems: [
        StatusBadge {
            label: root.dirty ? qsTr("Unsent edits") : qsTr("Sent")
            variant: root.dirty ? "warning" : "ok"
        },
        AppButton {
            size: "small"
            variant: "ghost"
            enabled: root.dirty
            text: qsTr("Discard")
            onClicked: root.release()
        },
        AppButton {
            size: "small"
            variant: "primary"
            enabled: root.dirty
            text: qsTr("Send to controller")
            onClicked: {
                controller.applyInputs(root.draft);
                root.release();
            }
        }
    ]

    RowLayout {
        Layout.fillWidth: true
        Layout.fillHeight: true
        spacing: theme.space_5
        // Nothing to read or write until a train exists.
        enabled: controller.snapshot.has_train

        // ------------------------------------------- Train Model
        ColumnLayout {
            Layout.fillWidth: true
            Layout.preferredWidth: 1
            Layout.alignment: Qt.AlignTop
            spacing: 0

            LabeledDivider {
                Layout.fillWidth: true
                Layout.bottomMargin: theme.space_1
                text: qsTr("From the Train Model")
            }

            SignalEditRow {
                Layout.fillWidth: true
                editable: true
                showKind: false
                rowHeight: 42
                valueWidth: 160
                unitWidth: 52
                name: "commanded_speed"
                kind: "float"
                unit: "m/s"
                value: root.draft.commanded_speed
                pending: root.touched["commanded_speed"] === true
                    && root.pending("commanded_speed")
                onEdited: function (v) { root.stage("commanded_speed", v); }
            }
            SignalEditRow {
                Layout.fillWidth: true
                editable: true
                showKind: false
                rowHeight: 42
                valueWidth: 160
                unitWidth: 52
                name: "authority_blocks"
                kind: "int"
                unit: "blocks"
                value: root.draft.authority_blocks
                pending: root.touched["authority_blocks"] === true
                    && root.pending("authority_blocks")
                onEdited: function (v) { root.stage("authority_blocks", v); }
            }
            SignalEditRow {
                Layout.fillWidth: true
                editable: true
                showKind: false
                rowHeight: 42
                valueWidth: 160
                unitWidth: 52
                name: "beacon"
                kind: "string"
                value: root.draft.beacon
                pending: root.touched["beacon"] === true
                    && root.pending("beacon")
                onEdited: function (v) { root.stage("beacon", v); }
            }
            SignalEditRow {
                Layout.fillWidth: true
                editable: true
                showKind: false
                rowHeight: 42
                valueWidth: 160
                unitWidth: 52
                name: "failure_engine"
                kind: "bool"
                value: root.draft.failure_engine
                pending: root.touched["failure_engine"] === true
                    && root.pending("failure_engine")
                onEdited: function (v) { root.stage("failure_engine", v); }
            }
            SignalEditRow {
                Layout.fillWidth: true
                editable: true
                showKind: false
                rowHeight: 42
                valueWidth: 160
                unitWidth: 52
                name: "failure_brake"
                kind: "bool"
                value: root.draft.failure_brake
                pending: root.touched["failure_brake"] === true
                    && root.pending("failure_brake")
                onEdited: function (v) { root.stage("failure_brake", v); }
            }
            SignalEditRow {
                Layout.fillWidth: true
                editable: true
                showKind: false
                rowHeight: 42
                valueWidth: 160
                unitWidth: 52
                name: "failure_signal_pickup"
                kind: "bool"
                value: root.draft.failure_signal_pickup
                pending: root.touched["failure_signal_pickup"] === true
                    && root.pending("failure_signal_pickup")
                onEdited: function (v) {
                    root.stage("failure_signal_pickup", v);
                }
            }
            SignalEditRow {
                Layout.fillWidth: true
                editable: true
                showKind: false
                rowHeight: 42
                valueWidth: 160
                unitWidth: 52
                name: "cabin_temperature"
                kind: "float"
                unit: "\u00b0C"
                value: root.draft.cabin_temperature
                pending: root.touched["cabin_temperature"] === true
                    && root.pending("cabin_temperature")
                onEdited: function (v) { root.stage("cabin_temperature", v); }
            }
            SignalEditRow {
                Layout.fillWidth: true
                editable: true
                showKind: false
                rowHeight: 42
                valueWidth: 160
                unitWidth: 52
                name: "signal_light_ahead"
                kind: "enum"
                options: root.aspects
                value: root.draft.signal_light_ahead
                pending: root.touched["signal_light_ahead"] === true
                    && root.pending("signal_light_ahead")
                onEdited: function (v) { root.stage("signal_light_ahead", v); }
            }
            SignalEditRow {
                Layout.fillWidth: true
                editable: true
                showKind: false
                rowHeight: 42
                valueWidth: 160
                unitWidth: 52
                name: "brake_state"
                kind: "bool"
                value: root.draft.brake_state
                pending: root.touched["brake_state"] === true
                    && root.pending("brake_state")
                onEdited: function (v) { root.stage("brake_state", v); }
            }
            SignalEditRow {
                Layout.fillWidth: true
                editable: true
                showKind: false
                rowHeight: 42
                valueWidth: 160
                unitWidth: 52
                name: "door_state_left"
                kind: "bool"
                value: root.draft.door_state_left
                pending: root.touched["door_state_left"] === true
                    && root.pending("door_state_left")
                onEdited: function (v) { root.stage("door_state_left", v); }
            }
            SignalEditRow {
                Layout.fillWidth: true
                editable: true
                showKind: false
                rowHeight: 42
                valueWidth: 160
                unitWidth: 52
                name: "door_state_right"
                kind: "bool"
                value: root.draft.door_state_right
                pending: root.touched["door_state_right"] === true
                    && root.pending("door_state_right")
                onEdited: function (v) { root.stage("door_state_right", v); }
            }
            SignalEditRow {
                Layout.fillWidth: true
                editable: true
                showKind: false
                rowHeight: 42
                valueWidth: 160
                unitWidth: 52
                name: "light_state_cabin"
                kind: "bool"
                value: root.draft.light_state_cabin
                pending: root.touched["light_state_cabin"] === true
                    && root.pending("light_state_cabin")
                onEdited: function (v) { root.stage("light_state_cabin", v); }
            }
            SignalEditRow {
                Layout.fillWidth: true
                editable: true
                showKind: false
                rowHeight: 42
                valueWidth: 160
                unitWidth: 52
                name: "light_state_headlights"
                kind: "bool"
                value: root.draft.light_state_headlights
                pending: root.touched["light_state_headlights"] === true
                    && root.pending("light_state_headlights")
                onEdited: function (v) {
                    root.stage("light_state_headlights", v);
                }
            }
            SignalEditRow {
                Layout.fillWidth: true
                rule: false
                editable: true
                showKind: false
                rowHeight: 42
                valueWidth: 160
                unitWidth: 52
                name: "actual_speed"
                kind: "float"
                unit: "m/s"
                value: root.draft.actual_speed
                pending: root.touched["actual_speed"] === true
                    && root.pending("actual_speed")
                onEdited: function (v) { root.stage("actual_speed", v); }
            }
        }

        // ------------------------------------------------ the cab
        ColumnLayout {
            Layout.fillWidth: true
            Layout.preferredWidth: 1
            Layout.alignment: Qt.AlignTop
            spacing: 0

            LabeledDivider {
                Layout.fillWidth: true
                Layout.bottomMargin: theme.space_1
                text: qsTr("From the cab")
            }

            SignalEditRow {
                Layout.fillWidth: true
                editable: true
                showKind: false
                rowHeight: 42
                valueWidth: 160
                unitWidth: 52
                name: "operator"
                kind: "enum"
                options: root.roles
                value: root.roles[root.s.operator_index + 1]
                onEdited: function (v) {
                    controller.selectOperator(root.roles.indexOf(v) - 1);
                }
            }
            SignalEditRow {
                Layout.fillWidth: true
                editable: true
                showKind: false
                rowHeight: 42
                valueWidth: 160
                unitWidth: 52
                enabled: root.s.signed_in
                name: "operating_mode"
                kind: "enum"
                options: ["Automatic", "Manual"]
                value: root.s.manual ? "Manual" : "Automatic"
                onEdited: function (v) {
                    controller.setManual(v === "Manual");
                }
            }
            SignalEditRow {
                Layout.fillWidth: true
                editable: true
                showKind: false
                rowHeight: 42
                valueWidth: 160
                unitWidth: 52
                enabled: !root.s.gains_locked
                name: "kp"
                kind: "float"
                unit: "W per m/s"
                value: root.draft.kp
                pending: root.touched["kp"] === true && root.pending("kp")
                onEdited: function (v) { root.stage("kp", v); }
            }
            SignalEditRow {
                Layout.fillWidth: true
                editable: true
                showKind: false
                rowHeight: 42
                valueWidth: 160
                unitWidth: 52
                enabled: !root.s.gains_locked
                name: "ki"
                kind: "float"
                unit: "W per m"
                value: root.draft.ki
                pending: root.touched["ki"] === true && root.pending("ki")
                onEdited: function (v) { root.stage("ki", v); }
            }
            SignalEditRow {
                Layout.fillWidth: true
                editable: true
                showKind: false
                rowHeight: 42
                valueWidth: 160
                unitWidth: 52
                enabled: root.s.can_drive
                name: "target_speed"
                kind: "float"
                unit: "mph"
                value: Math.round(root.s.target_mph)
                onEdited: function (v) { controller.setTargetMph(v); }
            }
            SignalEditRow {
                Layout.fillWidth: true
                editable: true
                showKind: false
                rowHeight: 42
                valueWidth: 160
                unitWidth: 52
                enabled: root.s.can_drive
                name: "cabin_setpoint"
                kind: "int"
                unit: "\u00b0F"
                value: Math.round(root.s.target_temp_f)
                onEdited: function (v) { controller.setTargetTemp(v); }
            }
            SignalEditRow {
                Layout.fillWidth: true
                editable: true
                showKind: false
                rowHeight: 42
                valueWidth: 160
                unitWidth: 52
                enabled: root.s.can_drive
                name: "door_command_left"
                kind: "bool"
                value: root.s.doors_left
                onEdited: function (v) { controller.setDoor("left", v); }
            }
            SignalEditRow {
                Layout.fillWidth: true
                editable: true
                showKind: false
                rowHeight: 42
                valueWidth: 160
                unitWidth: 52
                enabled: root.s.can_drive
                name: "door_command_right"
                kind: "bool"
                value: root.s.doors_right
                onEdited: function (v) { controller.setDoor("right", v); }
            }
            SignalEditRow {
                Layout.fillWidth: true
                editable: true
                showKind: false
                rowHeight: 42
                valueWidth: 160
                unitWidth: 52
                enabled: root.s.can_drive
                name: "cabin_lights_command"
                kind: "bool"
                value: root.s.lights
                onEdited: function (v) { controller.setLights(v); }
            }
            SignalEditRow {
                Layout.fillWidth: true
                editable: true
                showKind: false
                rowHeight: 42
                valueWidth: 160
                unitWidth: 52
                enabled: root.s.can_drive
                name: "headlights_command"
                kind: "bool"
                value: root.s.headlights
                onEdited: function (v) { controller.setHeadlights(v); }
            }
            SignalEditRow {
                Layout.fillWidth: true
                editable: true
                showKind: false
                rowHeight: 42
                valueWidth: 160
                unitWidth: 52
                enabled: root.s.signed_in
                name: "emergency_brake"
                kind: "bool"
                value: root.s.emergency_brake
                onEdited: function (v) {
                    if (v !== root.s.emergency_brake)
                        controller.toggleEmergencyBrake();
                }
            }
            SignalEditRow {
                Layout.fillWidth: true
                rule: false
                editable: true
                showKind: false
                rowHeight: 42
                valueWidth: 160
                unitWidth: 52
                enabled: root.s.can_drive
                name: "service_brake"
                kind: "bool"
                value: root.s.service_request
                onEdited: function (v) {
                    if (v !== root.s.service_request)
                        controller.toggleServiceBrake();
                }
            }

            AppButton {
                Layout.fillWidth: true
                Layout.topMargin: theme.space_3
                variant: "secondary"
                enabled: root.s.can_drive && !root.s.announcing
                text: root.s.announcing ? qsTr("Announcing\u2026")
                                        : qsTr("Announce station")
                onClicked: controller.announce()
            }

            HelperText {
                Layout.fillWidth: true
                Layout.topMargin: theme.space_2
                text: root.s.gains_locked
                    ? qsTr("Gains are set for this train.")
                    : root.s.operator === "engineer"
                        ? qsTr("Sending the inputs commissions the gains "
                               + "and starts the run.")
                        : qsTr("Sign in as the engineer to set the gains.")
            }
        }
    }

}
