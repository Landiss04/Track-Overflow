// Track Controller test UI window.
//
// A separate process from the Track Controller UI. It plays the CTC and
// Track Model against a running controller, with source inputs separated
// from live controller outputs:
//
//   CTC and Track Model inputs change one selected block at a time
//   outputs show what the controller is driving in response
import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import QtQuick.Window
import "../ui/components"
import "components"

ApplicationWindow {
    id: window

    readonly property bool live: stimulus.connected
    readonly property string ctcBlockId:
        stimulus.blockIds[ctcBlockPick.index] || ""
    readonly property string trackBlockId:
        stimulus.blockIds[trackBlockPick.index] || ""
    readonly property string ctcSwitchId:
        stimulus.switchForBlock[window.ctcBlockId] || ""

    visible: true
    width: 1440
    height: 900
    minimumWidth: 900
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
                    label: stimulus.controllerReady
                        ? qsTr("Controller ready")
                        : qsTr("Controller not ready: CTC holding")
                    variant: stimulus.controllerReady ? "ok" : "warning"
                }

                StatusBadge {
                    visible: window.live && stimulus.maintenance
                    label: qsTr("CTC maintenance on")
                    variant: "warning"
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

                // The shared clock belongs to the central harness and is
                // set by the CTC Office (D017). Standing alone, the test
                // UI plays that part, so the controls live here and the
                // Track Controller UI only shows the clock.
                AppButton {
                    text: stimulus.clockPaused ? qsTr("Run") : qsTr("Pause")
                    variant: stimulus.clockPaused ? "primary" : "secondary"
                    size: "small"
                    enabled: window.live
                    onClicked: stimulus.clockPaused
                        ? stimulus.resumeClock() : stimulus.pauseClock()
                }

                SegmentedToggle {
                    options: [qsTr("1×"), qsTr("10×")]
                    currentIndex: stimulus.clockSpeed === 10 ? 1 : 0
                    enabled: window.live
                    onActivated: function (index) {
                        stimulus.setClockSpeed(index === 1 ? 10 : 1);
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

        // --- inputs and live outputs ---------------------------------------
        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.margins: theme.space_3
            spacing: theme.space_3

            // ==== source-specific inputs ==================================
            Panel {
                Layout.preferredWidth: 440
                Layout.minimumWidth: 440
                Layout.maximumWidth: 440
                Layout.fillHeight: true
                title: qsTr("Stimulus inputs")
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
                            text: qsTr("Choose a source and block. Each control "
                                + "changes only that block, except CTC "
                                + "maintenance mode, which is system-wide.")
                        }

                        Rectangle {
                            Layout.fillWidth: true
                            implicitHeight: trackModelColumn.implicitHeight
                                + 2 * theme.space_3
                            color: theme.bg_surface
                            border.color: theme.border
                            border.width: 1
                            radius: theme.radius_md

                            ColumnLayout {
                                id: trackModelColumn
                                anchors.fill: parent
                                anchors.margins: theme.space_3
                                spacing: theme.space_3

                                SectionTitle { text: qsTr("TRACK MODEL INPUTS") }

                                PickerRow {
                                    id: trackBlockPick
                                    label: qsTr("Block")
                                    model: stimulus.blockLabels
                                    enabled: window.live
                                    Layout.fillWidth: true
                                }

                                ToggleRow {
                                    Layout.fillWidth: true
                                    label: qsTr("Train present")
                                    hint: qsTr("Occupancy on ")
                                        + trackBlockPick.currentText
                                        + qsTr("; held until test UIs disconnect")
                                    checked: !!stimulus.occupied[window.trackBlockId]
                                    enabled: window.live
                                        && window.trackBlockId !== ""
                                    onToggled: function (value) {
                                        stimulus.setOccupancy(
                                            window.trackBlockId, value);
                                    }
                                }
                            }
                        }

                        Rectangle {
                            Layout.fillWidth: true
                            implicitHeight: ctcColumn.implicitHeight
                                + 2 * theme.space_3
                            color: theme.bg_surface
                            border.color: theme.border
                            border.width: 1
                            radius: theme.radius_md

                            ColumnLayout {
                                id: ctcColumn
                                anchors.fill: parent
                                anchors.margins: theme.space_3
                                spacing: theme.space_3

                                SectionTitle { text: qsTr("CTC INPUTS") }

                                PickerRow {
                                    id: ctcBlockPick
                                    label: qsTr("Block")
                                    model: stimulus.blockLabels
                                    enabled: window.live
                                    Layout.fillWidth: true
                                }

                                ToggleRow {
                                    Layout.fillWidth: true
                                    label: qsTr("Maintenance mode")
                                    hint: qsTr("System-wide: speed and authority "
                                        + "held at zero; switch commands enabled")
                                    checked: stimulus.maintenance
                                    enabled: window.live
                                    onToggled: function (value) {
                                        stimulus.setMaintenance(value);
                                    }
                                }

                                RowLayout {
                                    Layout.fillWidth: true
                                    spacing: theme.space_3

                                    FieldLabel {
                                        text: qsTr("Switch state")
                                        Layout.preferredWidth: 120
                                    }

                                    SegmentedToggle {
                                        Layout.fillWidth: true
                                        options: [qsTr("None"), qsTr("Normal"),
                                            qsTr("Reverse")]
                                        enabled: window.live
                                            && window.ctcSwitchId !== ""
                                        currentIndex: ({ none: 0, normal: 1,
                                            reverse: 2 })[
                                            stimulus.ctcCommand[
                                                window.ctcSwitchId] || "none"]
                                        onActivated: function (index) {
                                            stimulus.setSwitchCommand(
                                                window.ctcSwitchId,
                                                ["none", "normal", "reverse"][index]);
                                        }
                                    }
                                }

                                Note {
                                    visible: window.ctcBlockId !== ""
                                        && window.ctcSwitchId === ""
                                    text: qsTr("This block has no switch.")
                                }

                                ToggleRow {
                                    Layout.fillWidth: true
                                    label: qsTr("Close block")
                                    hint: qsTr("CTC closure for ")
                                        + ctcBlockPick.currentText
                                    onText: qsTr("CLOSED")
                                    offText: qsTr("OPEN")
                                    checked: !!stimulus.closed[window.ctcBlockId]
                                    enabled: window.live
                                        && window.ctcBlockId !== ""
                                    onToggled: function (value) {
                                        stimulus.setBlockClosed(
                                            window.ctcBlockId, value);
                                    }
                                }

                                NumberRow {
                                    id: sugSpeed
                                    Layout.fillWidth: true
                                    label: qsTr("Suggested speed")
                                    hint: isNaN(parseFloat(sugSpeed.text))
                                        ? qsTr("Sent as whole m/s, rounded down")
                                        : qsTr("Sent as ")
                                            + stimulus.wholeMps(
                                                parseFloat(sugSpeed.text))
                                            + qsTr(" m/s")
                                    unit: qsTr("MPH")
                                    reported: !stimulus.suggestedMph[
                                            window.ctcBlockId]
                                        && stimulus.suggestedMph[
                                            window.ctcBlockId] !== 0
                                        ? "" : stimulus.suggestedMph[
                                            window.ctcBlockId] < 0
                                            ? "" : String(stimulus.suggestedMph[
                                                window.ctcBlockId])
                                    decimals: 1
                                    maximum: 200
                                    enabled: window.live
                                        && window.ctcBlockId !== ""
                                    onCommitted: function (value) {
                                        stimulus.setSuggestedSpeed(
                                            window.ctcBlockId, value);
                                    }
                                }

                                NumberRow {
                                    Layout.fillWidth: true
                                    label: qsTr("Suggested authority")
                                    unit: qsTr("BLOCKS")
                                    reported: stimulus.suggestedBlocks[
                                            window.ctcBlockId] === undefined
                                        || stimulus.suggestedBlocks[
                                            window.ctcBlockId] < 0
                                        ? "" : String(stimulus.suggestedBlocks[
                                            window.ctcBlockId])
                                    maximum: 999
                                    enabled: window.live
                                        && window.ctcBlockId !== ""
                                    onCommitted: function (value) {
                                        stimulus.setSuggestedAuthority(
                                            window.ctcBlockId, value);
                                    }
                                }
                            }
                        }

                        Item { Layout.preferredHeight: theme.space_3 }
                    }
                }
            }

            // ==== controller outputs ====================================
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

                        OutputPicker {
                            Layout.fillWidth: true
                            title: qsTr("Block outputs")
                            items: stimulus.outputs.rows.filter(function (row) {
                                return row.kind === "circuit";
                            })
                        }

                        OutputPicker {
                            Layout.fillWidth: true
                            title: qsTr("Switches")
                            items: stimulus.outputs.rows.filter(function (row) {
                                return row.kind === "switch";
                            })
                        }

                        OutputPicker {
                            Layout.fillWidth: true
                            title: qsTr("Signals")
                            items: stimulus.outputs.rows.filter(function (row) {
                                return row.kind === "aspect";
                            })
                        }

                        OutputPicker {
                            Layout.fillWidth: true
                            title: qsTr("Crossings")
                            items: stimulus.outputs.rows.filter(function (row) {
                                return row.kind === "crossing";
                            })
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
                            visible: stimulus.overrides.rows.length > 0
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
                                        + stimulus.overrides.rows.length
                                    color: theme.warning
                                    font.family: theme.ui_family
                                    font.pixelSize: theme.size_label
                                    font.weight: theme.weight_bold
                                    font.letterSpacing: theme.label_letter_spacing
                                }

                                Repeater {
                                    model: stimulus.overrides.rows

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
