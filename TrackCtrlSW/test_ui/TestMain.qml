// Track Controller test UI window.
//
// A separate process from the Track Controller UI. It plays the CTC,
// the Track Model and the programmer against a running controller, and
// its three columns separate what each of them can do:
//
//   physical inputs   change the world the controller reacts to, so the
//                     PLC program sees them and its outputs move
//   outputs           what the controller is driving in response
//   user inputs       press the programmer's controls in the other UI
import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import QtQuick.Window
import "../ui/components"
import "components"

ApplicationWindow {
    id: window

    readonly property bool live: stimulus.connected
    readonly property var ui: stimulus.ui
    readonly property var inputs: stimulus.inputs
    readonly property string occId: stimulus.blockIds[occPick.index] || ""
    readonly property string closeId: stimulus.blockIds[closePick.index] || ""
    readonly property string switchId: stimulus.switchIds[switchPick.index] || ""
    readonly property string handSwitchId:
        stimulus.uiSwitchIds[handPick.index] || ""
    property bool handReverse: false

    visible: true
    width: 1440
    height: 900
    minimumWidth: 1180
    minimumHeight: 720
    title: qsTr("Track Controller — Test UI")
    color: theme.bg_app

    component SectionTitle: Text {
        Layout.fillWidth: true
        color: theme.text_secondary
        font.family: theme.ui_family
        font.pixelSize: theme.size_label
        font.weight: theme.weight_bold
        font.letterSpacing: theme.label_letter_spacing
    }

    component Note: Text {
        Layout.fillWidth: true
        color: theme.text_muted
        font.family: theme.ui_family
        font.pixelSize: theme.size_label
        wrapMode: Text.WordWrap
    }

    component Rule: Rectangle {
        Layout.fillWidth: true
        implicitHeight: 1
        color: theme.border
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        // --- header ----------------------------------------------------
        Rectangle {
            Layout.fillWidth: true
            implicitHeight: 64
            color: theme.bg_surface

            Rectangle {
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.bottom: parent.bottom
                implicitHeight: 1
                color: theme.border
            }

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: theme.space_5
                anchors.rightMargin: theme.space_5
                spacing: theme.space_4

                ColumnLayout {
                    spacing: 2
                    Layout.maximumWidth: 330

                    Text {
                        Layout.fillWidth: true
                        text: qsTr("Track Controller Test UI")
                        color: theme.text_primary
                        font.family: theme.ui_family
                        font.pixelSize: theme.size_h3
                        font.weight: theme.weight_bold
                        elide: Text.ElideRight
                    }

                    Text {
                        Layout.fillWidth: true
                        text: qsTr("Plays the CTC, Track Model and programmer")
                        color: theme.text_muted
                        font.family: theme.ui_family
                        font.pixelSize: theme.size_label
                        elide: Text.ElideRight
                    }
                }

                StatusBadge {
                    label: window.live ? qsTr("Connected") : qsTr("Waiting")
                    variant: window.live ? "ok" : "warning"
                }

                StatusBadge {
                    visible: window.live
                    label: stimulus.standin
                        ? qsTr("Stand-in running") : qsTr("Test UI drives inputs")
                    variant: stimulus.standin ? "idle" : "info"
                }

                Item { Layout.fillWidth: true }

                RowLayout {
                    spacing: theme.space_2

                    FieldLabel { text: qsTr("Target controller") }

                    ComboBox {
                        id: targetBox
                        implicitWidth: 230
                        enabled: window.live
                        opacity: enabled ? 1.0 : 0.42
                        font.family: theme.mono_family
                        font.pixelSize: theme.size_small
                        model: stimulus.controllerLabels
                        onActivated: function (index) {
                            stimulus.selectTarget(stimulus.controllerIds[index]);
                        }

                        Binding {
                            target: targetBox
                            property: "currentIndex"
                            value: stimulus.controllerIds.indexOf(stimulus.target)
                            when: stimulus.controllerIds.indexOf(stimulus.target) >= 0
                        }
                    }
                }

                MonoText {
                    text: stimulus.clock
                    color: theme.text_primary
                    font.pixelSize: theme.size_h3
                    font.weight: theme.weight_bold
                }
            }
        }

        // --- not connected -----------------------------------------------
        Rectangle {
            Layout.fillWidth: true
            visible: !window.live
            implicitHeight: waiting.implicitHeight + 2 * theme.space_3
            color: theme.warning_bg
            border.color: theme.warning
            border.width: 1

            Text {
                id: waiting
                anchors.fill: parent
                anchors.margins: theme.space_3
                text: qsTr("No Track Controller is running. Start it with "
                    + "\"python main.py\" and this window connects by itself. "
                    + "Every control below is disabled until it does.")
                color: theme.warning
                font.family: theme.ui_family
                font.pixelSize: theme.size_small
                wrapMode: Text.WordWrap
            }
        }

        // --- the three columns ---------------------------------------------
        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.margins: theme.space_3
            spacing: theme.space_3

            // ==== physical inputs ========================================
            Panel {
                Layout.preferredWidth: 440
                Layout.minimumWidth: 440
                Layout.maximumWidth: 440
                Layout.fillHeight: true
                title: qsTr("Physical inputs")
                status: stimulus.target

                ScrollView {
                    id: physicalScroll
                    anchors.fill: parent
                    clip: true
                    contentWidth: availableWidth
                    enabled: window.live

                    ColumnLayout {
                        x: theme.space_3
                        y: theme.space_3
                        width: physicalScroll.availableWidth - 2 * theme.space_3
                        spacing: theme.space_3

                        Note {
                            text: qsTr("These change the world the controller "
                                + "reacts to. They are written onto its input "
                                + "card, so its PLC program sees them and its "
                                + "outputs move.")
                        }

                        SectionTitle { text: qsTr("TRACK MODEL") }

                        PickerRow {
                            id: occPick
                            label: qsTr("Block")
                            model: stimulus.blockLabels
                            enabled: window.live
                            Layout.fillWidth: true
                        }

                        ToggleRow {
                            Layout.fillWidth: true
                            label: qsTr("Train present")
                            hint: qsTr("Block occupancy on ") + occPick.currentText
                            checked: !!stimulus.occupied[window.occId]
                            enabled: window.live && window.occId !== ""
                            onToggled: function (value) {
                                stimulus.setOccupancy(window.occId, value);
                            }
                        }

                        AppButton {
                            text: qsTr("Clear all occupancy")
                            size: "small"
                            enabled: window.live
                            onClicked: stimulus.clearOccupancy()
                        }

                        Rule {}

                        PickerRow {
                            id: switchPick
                            label: qsTr("Switch")
                            model: stimulus.switchIds
                            enabled: window.live && stimulus.switchIds.length > 0
                            Layout.fillWidth: true
                        }

                        ToggleRow {
                            Layout.fillWidth: true
                            label: qsTr("Fault")
                            hint: qsTr("Machine cannot be trusted to be in position")
                            checked: !!stimulus.switchFault[window.switchId]
                            enabled: window.live && window.switchId !== ""
                            onToggled: function (value) {
                                stimulus.setSwitchFault(window.switchId, value);
                            }
                        }

                        ToggleRow {
                            Layout.fillWidth: true
                            label: qsTr("Moving")
                            hint: qsTr("Mid-throw, locked in neither position")
                            checked: !!stimulus.switchMoving[window.switchId]
                            enabled: window.live && window.switchId !== ""
                            onToggled: function (value) {
                                stimulus.setSwitchMoving(window.switchId, value);
                            }
                        }

                        Rule {}

                        SectionTitle { text: qsTr("CTC OFFICE") }

                        PickerRow {
                            id: closePick
                            label: qsTr("Block")
                            model: stimulus.blockLabels
                            enabled: window.live
                            Layout.fillWidth: true
                        }

                        ToggleRow {
                            Layout.fillWidth: true
                            label: qsTr("Closed")
                            hint: qsTr("Closed for maintenance: ") + closePick.currentText
                            onText: qsTr("CLOSED")
                            offText: qsTr("OPEN")
                            checked: !!stimulus.closed[window.closeId]
                            enabled: window.live && window.closeId !== ""
                            onToggled: function (value) {
                                stimulus.setBlockClosed(window.closeId, value);
                            }
                        }

                        NumberRow {
                            Layout.fillWidth: true
                            label: qsTr("Suggested speed")
                            unit: qsTr("MPH")
                            reported: window.inputs.suggested_speed === undefined
                                ? "" : String(window.inputs.suggested_speed)
                            maximum: 200
                            enabled: window.live
                            onCommitted: function (value) {
                                stimulus.setSuggestedSpeed(value);
                            }
                        }

                        NumberRow {
                            Layout.fillWidth: true
                            label: qsTr("Suggested authority")
                            unit: qsTr("BLOCKS")
                            reported: window.inputs.suggested_authority === undefined
                                ? "" : String(window.inputs.suggested_authority)
                            maximum: 999
                            enabled: window.live
                            onCommitted: function (value) {
                                stimulus.setSuggestedAuthority(value);
                            }
                        }

                        NumberRow {
                            Layout.fillWidth: true
                            label: qsTr("Speed limit")
                            hint: qsTr("0 keeps each block's posted limit")
                            unit: qsTr("MPH")
                            reported: !window.inputs.speed_limit
                                ? "0" : String(window.inputs.speed_limit)
                            maximum: 200
                            enabled: window.live
                            onCommitted: function (value) {
                                stimulus.setSpeedLimit(value);
                            }
                        }

                        Item { Layout.preferredHeight: theme.space_3 }
                    }
                }
            }

            // ==== outputs ================================================
            Panel {
                Layout.fillWidth: true
                Layout.minimumWidth: 300
                Layout.fillHeight: true
                title: qsTr("Controller outputs — live")
                status: stimulus.target

                ScrollView {
                    id: outputScroll
                    anchors.fill: parent
                    clip: true
                    contentWidth: availableWidth

                    ColumnLayout {
                        x: theme.space_3
                        y: theme.space_3
                        width: outputScroll.availableWidth - 2 * theme.space_3
                        spacing: theme.space_3

                        Note {
                            text: qsTr("What the controller is driving onto the "
                                + "track after its PLC program and the vital "
                                + "supervisor have run. Watch the Track "
                                + "Controller UI change as you stimulate it.")
                        }

                        Repeater {
                            model: stimulus.outputs

                            delegate: SignalRow {
                                required property var modelData

                                Layout.fillWidth: true
                                label: modelData.label
                                value: modelData.value
                                kind: modelData.kind
                            }
                        }

                        Rule {}

                        Text {
                            Layout.fillWidth: true
                            text: qsTr("Train presence reported to the CTC")
                            color: theme.text_secondary
                            font.family: theme.ui_family
                            font.pixelSize: theme.size_small
                        }

                        MonoText {
                            Layout.fillWidth: true
                            text: stimulus.presence
                            wrapMode: Text.WordWrap
                            font.weight: theme.weight_bold
                        }

                        Rule {}

                        SignalRow {
                            Layout.fillWidth: true
                            label: qsTr("Mode")
                            value: stimulus.targetInfo.mode || ""
                        }

                        SignalRow {
                            Layout.fillWidth: true
                            label: qsTr("Program")
                            value: stimulus.targetInfo.file || ""
                        }

                        SignalRow {
                            Layout.fillWidth: true
                            label: qsTr("Iteration")
                            value: "#" + (stimulus.targetInfo.iteration || 0)
                        }

                        Rectangle {
                            Layout.fillWidth: true
                            Layout.preferredHeight: overrideColumn.implicitHeight
                                + 2 * theme.space_2
                            visible: stimulus.overrides.length > 0
                            color: theme.warning_bg
                            border.color: theme.warning
                            border.width: 1
                            radius: theme.radius_sm

                            ColumnLayout {
                                id: overrideColumn
                                anchors.left: parent.left
                                anchors.right: parent.right
                                anchors.top: parent.top
                                anchors.margins: theme.space_2
                                spacing: 2

                                Text {
                                    text: qsTr("VITAL OVERRIDES · ")
                                        + stimulus.overrides.length
                                    color: theme.warning
                                    font.family: theme.ui_family
                                    font.pixelSize: theme.size_label
                                    font.weight: theme.weight_bold
                                    font.letterSpacing: theme.label_letter_spacing
                                }

                                Repeater {
                                    model: stimulus.overrides

                                    delegate: Text {
                                        required property var modelData

                                        Layout.fillWidth: true
                                        text: modelData.signal + ": "
                                            + modelData.message
                                        color: theme.warning
                                        font.family: theme.ui_family
                                        font.pixelSize: theme.size_label
                                        wrapMode: Text.WordWrap
                                    }
                                }
                            }
                        }

                        Item { Layout.preferredHeight: theme.space_3 }
                    }
                }
            }

            // ==== user inputs ============================================
            Panel {
                Layout.preferredWidth: 440
                Layout.minimumWidth: 440
                Layout.maximumWidth: 440
                Layout.fillHeight: true
                title: qsTr("User inputs")
                status: qsTr("PROGRAMMER UI")

                ScrollView {
                    id: userScroll
                    anchors.fill: parent
                    clip: true
                    contentWidth: availableWidth
                    enabled: window.live

                    ColumnLayout {
                        x: theme.space_3
                        y: theme.space_3
                        width: userScroll.availableWidth - 2 * theme.space_3
                        spacing: theme.space_3

                        Note {
                            text: qsTr("These press the programmer's own "
                                + "controls in the Track Controller UI. They "
                                + "exercise its features and nothing else: "
                                + "each does what the same click would, "
                                + "including being refused.")
                        }

                        SectionTitle { text: qsTr("SELECTION") }

                        PickerRow {
                            label: qsTr("Line")
                            model: stimulus.lineNames
                            mirror: stimulus.lineNames.indexOf(window.ui.line)
                            enabled: window.live
                            Layout.fillWidth: true
                            onPicked: function (index) {
                                stimulus.selectLine(stimulus.lineNames[index]);
                            }
                        }

                        PickerRow {
                            label: qsTr("Controller")
                            model: stimulus.controllerLabels
                            mirror: stimulus.controllerIds.indexOf(
                                window.ui.controller)
                            enabled: window.live
                            Layout.fillWidth: true
                            onPicked: function (index) {
                                stimulus.selectController(
                                    stimulus.controllerIds[index]);
                            }
                        }

                        RowLayout {
                            Layout.fillWidth: true
                            spacing: theme.space_3

                            FieldLabel {
                                text: qsTr("Tab")
                                Layout.preferredWidth: 120
                            }

                            SegmentedToggle {
                                Layout.fillWidth: true
                                options: [qsTr("Program"), qsTr("View")]
                                currentIndex: window.ui.tab || 0
                                onActivated: function (index) {
                                    stimulus.setTab(index);
                                }
                            }
                        }

                        RowLayout {
                            Layout.fillWidth: true
                            spacing: theme.space_3

                            FieldLabel {
                                text: qsTr("Mode")
                                Layout.preferredWidth: 120
                            }

                            SegmentedToggle {
                                Layout.fillWidth: true
                                options: [qsTr("Automatic"), qsTr("Maintenance")]
                                currentIndex: window.ui.maintenance ? 1 : 0
                                onActivated: function (index) {
                                    stimulus.setMaintenance(index === 1);
                                }
                            }
                        }

                        Rule {}

                        SectionTitle { text: qsTr("SET SWITCH MANUALLY") }

                        PickerRow {
                            id: handPick
                            label: qsTr("Switch")
                            model: stimulus.uiSwitchIds
                            enabled: window.live
                                && stimulus.uiSwitchIds.length > 0
                            Layout.fillWidth: true
                        }

                        RowLayout {
                            Layout.fillWidth: true
                            spacing: theme.space_3

                            FieldLabel {
                                text: qsTr("Position")
                                Layout.preferredWidth: 120
                            }

                            SegmentedToggle {
                                Layout.fillWidth: true
                                options: [qsTr("Normal"), qsTr("Reverse")]
                                currentIndex: window.handReverse ? 1 : 0
                                onActivated: function (index) {
                                    window.handReverse = index === 1;
                                }
                            }
                        }

                        RowLayout {
                            Layout.fillWidth: true
                            spacing: theme.space_2

                            AppButton {
                                text: qsTr("Apply")
                                variant: "primary"
                                size: "small"
                                enabled: window.live
                                    && window.handSwitchId !== ""
                                onClicked: stimulus.setSwitchByHand(
                                    window.handSwitchId, window.handReverse)
                            }

                            AppButton {
                                text: qsTr("Release")
                                size: "small"
                                enabled: window.live
                                    && window.handSwitchId !== ""
                                onClicked: stimulus.releaseSwitch(
                                    window.handSwitchId)
                            }
                        }

                        Note {
                            text: qsTr("The dialog only works in maintenance "
                                + "mode; outside it the controller refuses.")
                        }

                        Rule {}

                        SectionTitle { text: qsTr("EDITOR") }

                        Flow {
                            Layout.fillWidth: true
                            spacing: theme.space_2

                            AppButton {
                                text: qsTr("Edit buffer")
                                size: "small"
                                enabled: window.live
                                onClicked: stimulus.editBuffer()
                            }

                            AppButton {
                                text: qsTr("Run")
                                variant: "primary"
                                size: "small"
                                enabled: window.live
                                onClicked: stimulus.run()
                            }

                            AppButton {
                                text: qsTr("Commit iteration")
                                variant: "success"
                                size: "small"
                                enabled: window.live
                                onClicked: stimulus.commit()
                            }

                            AppButton {
                                text: qsTr("New")
                                size: "small"
                                enabled: window.live
                                onClicked: stimulus.newFile()
                            }
                        }

                        PickerRow {
                            id: historyPick
                            label: qsTr("Iteration")
                            model: stimulus.historyLabels
                            enabled: window.live
                                && stimulus.historyLabels.length > 0
                            Layout.fillWidth: true
                        }

                        RowLayout {
                            Layout.fillWidth: true
                            spacing: theme.space_2

                            AppButton {
                                text: qsTr("Open iteration")
                                size: "small"
                                enabled: window.live
                                    && stimulus.historyNumbers.length > 0
                                onClicked: stimulus.openIteration(
                                    stimulus.historyNumbers[historyPick.index])
                            }

                            AppButton {
                                text: qsTr("Live buffer")
                                size: "small"
                                enabled: window.live
                                onClicked: stimulus.openIteration(0)
                            }
                        }

                        RowLayout {
                            Layout.fillWidth: true
                            spacing: theme.space_2

                            TextField {
                                id: pathField
                                Layout.fillWidth: true
                                implicitHeight: theme.control_h_sm
                                placeholderText: qsTr("path/to/program.plc")
                                selectByMouse: true
                                color: theme.text_primary
                                font.family: theme.mono_family
                                font.pixelSize: theme.size_label
                                background: Rectangle {
                                    radius: theme.radius_md
                                    color: theme.bg_surface
                                    border.width: pathField.activeFocus ? 2 : 1
                                    border.color: pathField.activeFocus
                                        ? theme.focus_ring : theme.border_strong
                                }
                                onAccepted: stimulus.loadProgram(text)
                            }

                            AppButton {
                                text: qsTr("Load")
                                size: "small"
                                enabled: window.live && pathField.text !== ""
                                onClicked: stimulus.loadProgram(pathField.text)
                            }
                        }

                        Rule {}

                        SectionTitle {
                            text: qsTr("WHAT THE PROGRAMMER'S UI SHOWS")
                        }

                        SignalRow {
                            Layout.fillWidth: true
                            label: qsTr("Line")
                            value: window.ui.line || ""
                        }

                        SignalRow {
                            Layout.fillWidth: true
                            label: qsTr("Controller")
                            value: window.ui.controller || ""
                        }

                        SignalRow {
                            Layout.fillWidth: true
                            label: qsTr("Tab")
                            value: window.ui.tab === 1
                                ? qsTr("View") : qsTr("Program")
                        }

                        SignalRow {
                            Layout.fillWidth: true
                            label: qsTr("Buffer")
                            value: window.ui.buffer_read_only
                                ? qsTr("History")
                                : window.ui.buffer_dirty
                                    ? qsTr("Edited") : qsTr("Committed")
                        }

                        SignalRow {
                            Layout.fillWidth: true
                            label: qsTr("Ready to commit")
                            value: window.ui.can_commit
                                ? qsTr("YES") : qsTr("NO")
                        }

                        SignalRow {
                            Layout.fillWidth: true
                            label: qsTr("Compile errors")
                            value: String(window.ui.errors || 0)
                        }

                        Item { Layout.preferredHeight: theme.space_3 }
                    }
                }
            }
        }

        // --- last reply from the controller ---------------------------------
        Rectangle {
            Layout.fillWidth: true
            implicitHeight: theme.control_h_md
            color: stimulus.replyIsError ? theme.danger_bg : theme.bg_sunken

            Rectangle {
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.top: parent.top
                implicitHeight: 1
                color: stimulus.replyIsError ? theme.danger : theme.border
            }

            Text {
                anchors.fill: parent
                anchors.leftMargin: theme.space_5
                anchors.rightMargin: theme.space_5
                verticalAlignment: Text.AlignVCenter
                text: (stimulus.replyIsError ? qsTr("REFUSED — ") : "")
                    + stimulus.reply
                color: stimulus.replyIsError
                    ? theme.danger : theme.text_secondary
                font.family: theme.mono_family
                font.pixelSize: theme.size_small
                font.weight: stimulus.replyIsError
                    ? theme.weight_bold : theme.weight_regular
                elide: Text.ElideRight
            }
        }
    }
}
