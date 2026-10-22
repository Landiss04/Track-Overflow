// Everything the controller receives, in two columns of one table:
// the signals the Train Model sends on the left, and Murphy's
// injected failures and the Track Model's signal aspect on the right.
// The cab is driven from the console itself, never from here.
//
// Every row is staged: typing fills a draft, edited rows are marked,
// and Send publishes the edited rows in one call, so the controller
// never sees a half-typed set of signals.
//
// Units are the operator's throughout, in both columns: mph and
// Fahrenheit, because a bench you type into all day is easier to
// read in the same units as the console it drives. Only the backend
// is SI, and the conversion happens where every other one does, in
// ConsoleBackend (truth conventions/units.md). Counts and identifiers are
// not measurements, so blocks and block IDs pass through as they
// are.
import QtQuick
import QtQuick.Layouts
import "../../../ui"
import "../components"

Panel {
    id: root
    objectName: "testInputs"

    readonly property var s: controller.snapshot
    readonly property var aspects: ["RED", "YELLOW", "GREEN", "SUPER GREEN"]
    // Shown in words, sent as the beacon encodes them (truth
    // beacon.md), index for index.
    readonly property var sideLabels: ["Left", "Right", "Both"]
    readonly property var sideCodes: ["L", "R", "LR"]

    // What the controller is holding right now.
    readonly property var live: ({
        "commanded_speed": Math.round(s.track_commanded_mph * 10) / 10,
        "actual_speed": Math.round(s.actual_mph * 10) / 10,
        "authority_blocks": s.track_authority_blocks,
        "beacon_station": s.beacon_station,
        "beacon_side": s.beacon_side,
        "beacon_underground": s.beacon_underground,
        "cabin_temperature": Math.round(s.cabin_temp_f),
        "signal_light_ahead": s.next_signal,
<<<<<<< HEAD
        "brake_state_emergency": s.fb_emergency_brake,
=======
        "emergency_brake_state": s.fb_emergency_brake,
>>>>>>> origin/Train_Ctrl_integration
        "door_state_left": s.fb_doors_left,
        "door_state_right": s.fb_doors_right,
        "light_state_interior": s.fb_interior_lights,
        "light_state_exterior": s.fb_exterior_lights,
        // Murphy's injections into the plant, not what the controller
        // has detected (that is in the header pills).
        "failure_engine": s.inject_engine,
        "failure_signal_pickup": s.inject_pickup,
<<<<<<< HEAD
        "failure_brake": s.inject_brake
=======
        "failure_brake": s.inject_brake,
        // The bench's own: whether the beacon is heard every tick.
        "at_station": s.bench_at_station
>>>>>>> origin/Train_Ctrl_integration
    })

    // What is typed but not sent, and which rows were typed in. The
    // plant keeps running, so rows nobody has touched follow it
    // instead of standing out as edits the moment the train moves.
    property var draft: live
    property var touched: ({})
    // Pause holds the whole simulation (REQUIREMENTS.md M11), and the
    // rows stop following it, so a set of values can be typed out
    // without the plant rewriting them underneath. Sending or
    // discarding still works.
    readonly property bool paused: s.paused
    readonly property bool dirty: {
        for (var key in touched)
            if (pending(key))
                return true;
        return false;
    }

    onLiveChanged: {
        if (paused)
            return;
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

    // Only the rows that were edited and still differ from what the
    // controller holds. Sending the whole draft would also write back
    // rounded readings (actual speed to 0.1 mph) and, while paused,
    // stale ones, such as an e-brake report
    // the driver has since released.
    function payload() {
        var edits = {};
        for (var key in touched)
            if (pending(key))
                edits[key] = draft[key];
        return edits;
    }

    function release() {
        draft = live;
        touched = ({});
    }

    // Edits belong to the train they were typed for. Switching
    // trains drops them, rather than carrying one train's staged
    // values across to another and offering to send them.
    readonly property string editing: s.train_id
    onEditingChanged: release()

    title: qsTr("Inputs")
    headerItems: [
        StatusBadge {
            label: root.dirty ? qsTr("Unsent edits") : qsTr("Sent")
            variant: root.dirty ? "warning" : "ok"
        },
<<<<<<< HEAD
=======
        // An event, not a row: the Track Model's next count, sent at
        // once (REQUIREMENTS.md M16).
        AppButton {
            objectName: "blockChangeButton"
            size: "small"
            variant: "ghost"
            enabled: root.s.has_train
            text: qsTr("Block change")
            onClicked: controller.bench_block_change()
        },
>>>>>>> origin/Train_Ctrl_integration
        AppButton {
            size: "small"
            variant: root.paused ? "primary" : "ghost"
            text: root.paused ? qsTr("Resume") : qsTr("Pause")
            onClicked: controller.set_paused(!root.paused)
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
                controller.apply_bench_inputs(root.payload());
                root.release();
            }
        }
    ]

    RowLayout {
        Layout.fillWidth: true
        Layout.fillHeight: true
        // The rows are shorter than the panel, and Panel centres
        // whatever cannot grow; letting this grow keeps them on top.
        Layout.maximumHeight: Number.POSITIVE_INFINITY
        spacing: theme.space_5
        // Nothing to read or write until a train exists.
        enabled: controller.snapshot.has_train

        // ------------------------------------------- Train Model
        ColumnLayout {
            Layout.fillWidth: true
            Layout.preferredWidth: 1
            // An even split, whatever the widest divider label.
            Layout.minimumWidth: 0
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
                rowHeight: 38
                valueWidth: 160
                unitWidth: 52
                name: "commanded_speed"
                kind: "float"
                unit: "mph"
                value: root.draft.commanded_speed
                pending: root.touched["commanded_speed"] === true
                    && root.pending("commanded_speed")
                onEdited: function (v) {
                    root.stage("commanded_speed", v);
                }
            }
            SignalEditRow {
                Layout.fillWidth: true
                editable: true
                showKind: false
                rowHeight: 38
                valueWidth: 160
                unitWidth: 52
                name: "actual_speed"
                kind: "float"
                unit: "mph"
                value: root.draft.actual_speed
                pending: root.touched["actual_speed"] === true
                    && root.pending("actual_speed")
                onEdited: function (v) {
                    root.stage("actual_speed", v);
                }
            }
            SignalEditRow {
                Layout.fillWidth: true
                editable: true
                showKind: false
                rowHeight: 38
                valueWidth: 160
                unitWidth: 52
                name: "authority_blocks"
                kind: "int"
                unit: "blocks"
                value: root.draft.authority_blocks
                pending: root.touched["authority_blocks"] === true
                    && root.pending("authority_blocks")
                onEdited: function (v) {
                    root.stage("authority_blocks", v);
                }
            }
<<<<<<< HEAD
=======
            // At a station the beacon rows below are heard every tick;
            // otherwise only once, when one of them is sent.
            SignalEditRow {
                Layout.fillWidth: true
                editable: true
                showKind: false
                rowHeight: 38
                valueWidth: 160
                unitWidth: 52
                name: "at_station"
                kind: "bool"
                value: root.draft.at_station
                pending: root.touched["at_station"] === true
                    && root.pending("at_station")
                onEdited: function (v) { root.stage("at_station", v); }
            }
>>>>>>> origin/Train_Ctrl_integration
            SignalEditRow {
                Layout.fillWidth: true
                editable: true
                showKind: false
                rowHeight: 38
                valueWidth: 160
                unitWidth: 52
                name: "station"
                kind: "string"
                value: root.draft.beacon_station
                pending: root.touched["beacon_station"] === true
                    && root.pending("beacon_station")
                onEdited: function (v) {
                    root.stage("beacon_station", v);
                }
            }
            SignalEditRow {
                Layout.fillWidth: true
                editable: true
                showKind: false
                rowHeight: 38
                valueWidth: 160
                unitWidth: 52
                name: "platform_side"
                kind: "enum"
                options: root.sideLabels
                value: root.sideLabels[
                    root.sideCodes.indexOf(root.draft.beacon_side)]
                pending: root.touched["beacon_side"] === true
                    && root.pending("beacon_side")
                onEdited: function (v) {
                    root.stage("beacon_side",
                               root.sideCodes[root.sideLabels.indexOf(v)]);
                }
            }
            SignalEditRow {
                Layout.fillWidth: true
                editable: true
                showKind: false
                rowHeight: 38
                valueWidth: 160
                unitWidth: 52
                name: "underground_state"
                kind: "bool"
                value: root.draft.beacon_underground
                pending: root.touched["beacon_underground"] === true
                    && root.pending("beacon_underground")
                onEdited: function (v) {
                    root.stage("beacon_underground", v);
                }
            }
            SignalEditRow {
                Layout.fillWidth: true
                editable: true
                showKind: false
                rowHeight: 38
                valueWidth: 160
                unitWidth: 52
                name: "cabin_temperature"
                kind: "int"
                unit: "\u00b0F"
                value: root.draft.cabin_temperature
                pending: root.touched["cabin_temperature"] === true
                    && root.pending("cabin_temperature")
                onEdited: function (v) {
                    root.stage("cabin_temperature", v);
                }
            }
            SignalEditRow {
                Layout.fillWidth: true
                editable: true
                showKind: false
                rowHeight: 38
                valueWidth: 160
                unitWidth: 52
<<<<<<< HEAD
                name: "brake_state_emergency"
                kind: "bool"
                value: root.draft.brake_state_emergency
                pending: root.touched["brake_state_emergency"] === true
                    && root.pending("brake_state_emergency")
                onEdited: function (v) {
                    root.stage("brake_state_emergency", v);
=======
                name: "emergency_brake_state"
                kind: "bool"
                value: root.draft.emergency_brake_state
                pending: root.touched["emergency_brake_state"] === true
                    && root.pending("emergency_brake_state")
                onEdited: function (v) {
                    root.stage("emergency_brake_state", v);
>>>>>>> origin/Train_Ctrl_integration
                }
            }
            SignalEditRow {
                Layout.fillWidth: true
                editable: true
                showKind: false
                rowHeight: 38
                valueWidth: 160
                unitWidth: 52
                name: "door_state_left"
                kind: "bool"
                trueLabel: qsTr("On")
                falseLabel: qsTr("Off")
                value: root.draft.door_state_left
                pending: root.touched["door_state_left"] === true
                    && root.pending("door_state_left")
                onEdited: function (v) {
                    root.stage("door_state_left", v);
                }
            }
            SignalEditRow {
                Layout.fillWidth: true
                editable: true
                showKind: false
                rowHeight: 38
                valueWidth: 160
                unitWidth: 52
                name: "door_state_right"
                kind: "bool"
                trueLabel: qsTr("On")
                falseLabel: qsTr("Off")
                value: root.draft.door_state_right
                pending: root.touched["door_state_right"] === true
                    && root.pending("door_state_right")
                onEdited: function (v) {
                    root.stage("door_state_right", v);
                }
            }
            SignalEditRow {
                Layout.fillWidth: true
                editable: true
                showKind: false
                rowHeight: 38
                valueWidth: 160
                unitWidth: 52
                name: "light_state_interior"
                kind: "bool"
                trueLabel: qsTr("On")
                falseLabel: qsTr("Off")
                value: root.draft.light_state_interior
                pending: root.touched["light_state_interior"] === true
                    && root.pending("light_state_interior")
                onEdited: function (v) {
                    root.stage("light_state_interior", v);
                }
            }
            SignalEditRow {
                Layout.fillWidth: true
                editable: true
                showKind: false
                rowHeight: 38
                valueWidth: 160
                unitWidth: 52
                name: "light_state_exterior"
                kind: "bool"
                trueLabel: qsTr("On")
                falseLabel: qsTr("Off")
                value: root.draft.light_state_exterior
                pending: root.touched["light_state_exterior"] === true
                    && root.pending("light_state_exterior")
                onEdited: function (v) {
                    root.stage("light_state_exterior", v);
                }
            }
        }

        // ------------------------------- failures and the Track Model
        ColumnLayout {
            Layout.fillWidth: true
            Layout.preferredWidth: 1
            // An even split, whatever the widest divider label.
            Layout.minimumWidth: 0
            Layout.alignment: Qt.AlignTop
            spacing: 0

            LabeledDivider {
                Layout.fillWidth: true
                Layout.bottomMargin: theme.space_1
                text: qsTr("Injected failures")
            }
            SignalEditRow {
                Layout.fillWidth: true
                editable: true
                showKind: false
                rowHeight: 38
                valueWidth: 160
                unitWidth: 52
                name: "failure_engine"
                kind: "bool"
                value: root.draft.failure_engine
                pending: root.touched["failure_engine"] === true
                    && root.pending("failure_engine")
                onEdited: function (v) {
                    root.stage("failure_engine", v);
                }
            }
            SignalEditRow {
                Layout.fillWidth: true
                editable: true
                showKind: false
                rowHeight: 38
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
                rule: false
                showKind: false
                rowHeight: 38
                valueWidth: 160
                unitWidth: 52
                name: "failure_brake"
                kind: "bool"
                value: root.draft.failure_brake
                pending: root.touched["failure_brake"] === true
                    && root.pending("failure_brake")
                onEdited: function (v) {
                    root.stage("failure_brake", v);
                }
            }

            LabeledDivider {
                Layout.fillWidth: true
                Layout.topMargin: theme.space_3
                Layout.bottomMargin: theme.space_1
                text: qsTr("From the Track Model")
            }

            SignalEditRow {
                Layout.fillWidth: true
                editable: true
                showKind: false
                rowHeight: 38
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

            // A refused send, in the shared format (REQ-INTF-004). It
            // sits below every row, so nothing moves when it appears.
            Callout {
                Layout.fillWidth: true
                Layout.topMargin: theme.space_3
                visible: root.s.bench_error !== ""
                variant: "warning"
                heading: qsTr("Not sent")
                body: root.s.bench_error
            }
        }
    }
}
