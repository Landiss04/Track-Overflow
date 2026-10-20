import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "../../../ui" as Shared

Shared.ScaledWindow {
    id: window
    objectName: "harnessWindow"
    title: "Track Overflow — Central Harness"
    palette.window: theme.bg_app
    palette.windowText: theme.text_primary
    palette.base: theme.bg_surface
    palette.text: theme.text_primary
    palette.button: theme.bg_raised
    palette.buttonText: theme.text_primary
    palette.highlight: theme.accent
    palette.highlightedText: theme.on_accent
    palette.mid: theme.border_strong

    onClosing: function(close) {
        close.accepted = false
        endDialog.open()
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        Shared.ModuleHeader {
            Layout.fillWidth: true
            moduleName: window.title
            clock: backend.snapshot.time
            statusExtras: [
                Shared.StatusBadge {
                    label: backend.snapshot.state
                    variant: label === "RUNNING" ? "ok" : "warning"
                }
            ]
        }

        ColumnLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.margins: theme.space_5
            spacing: theme.space_4

            Shared.Card {
                Layout.fillWidth: true
                title: "Simulation"
                RowLayout {
                    Layout.fillWidth: true
                    spacing: theme.space_4
                    Shared.TelemetryReadout {
                        Layout.fillWidth: true
                        Layout.preferredWidth: 240
                        label: "Time of day"
                        value: backend.snapshot.time
                    }
                    Shared.TelemetryReadout {
                        Layout.fillWidth: true
                        Layout.preferredWidth: 180
                        label: "Tick"
                        value: backend.snapshot.tick
                    }
                    Shared.TelemetryReadout {
                        Layout.fillWidth: true
                        Layout.preferredWidth: 140
                        label: "Speed"
                        value: backend.snapshot.speed
                    }
                    ColumnLayout {
                        Layout.fillWidth: true
                        Layout.preferredWidth: 520
                        Shared.HelperText {
                            text: "Round trip per tick · last 5 s"
                        }
                        Shared.DataTable {
                            Layout.fillWidth: true
                            columns: [
                                {key: "mean", label: "Mean (ms)",
                                 numeric: true},
                                {key: "max", label: "Max (ms)",
                                 numeric: true},
                                {key: "slipped", label: "Slipped",
                                 numeric: true}
                            ]
                            rows: [{
                                mean: backend.snapshot.mean_ms,
                                max: backend.snapshot.max_ms,
                                slipped: backend.snapshot.slipped
                            }]
                        }
                    }
                }
                Shared.HelperText {
                    Layout.fillWidth: true
                    text: backend.snapshot.hold
                    font.pixelSize: theme.size_body
                }
            }

            RowLayout {
                Layout.fillWidth: true
                Layout.fillHeight: true
                spacing: theme.space_4

                Shared.Panel {
                    Layout.preferredWidth: 500
                    Layout.fillHeight: true
                    title: "Modules"
                    headerItems: [
                        Shared.StatusBadge {
                            label: backend.snapshot.ready + " / "
                                + backend.snapshot.total + " READY"
                            variant: backend.snapshot.ready
                                === backend.snapshot.total ? "ok" : "warning"
                        }
                    ]
                    Shared.HelperText {
                        Layout.fillWidth: true
                        visible: backend.snapshot.startup_timeout !== ""
                        text: "Startup timeout: "
                            + backend.snapshot.startup_timeout
                        color: theme.danger
                    }
                    ScrollView {
                        id: moduleScroll
                        objectName: "moduleScroll"
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        focusPolicy: Qt.StrongFocus
                        contentWidth: availableWidth
                        contentHeight: moduleRows.implicitHeight
                        clip: true
                        background: Rectangle {
                            color: theme.bg_surface
                            border.width: moduleScroll.visualFocus ? 2 : 0
                            border.color: theme.focus_ring
                            radius: theme.radius_md
                        }
                        ColumnLayout {
                            id: moduleRows
                            width: moduleScroll.availableWidth
                            spacing: theme.space_3
                            Repeater {
                                model: backend.modules
                                delegate: ColumnLayout {
                                    required property var modelData
                                    Layout.fillWidth: true
                                    spacing: theme.space_1
                                    RowLayout {
                                        Layout.fillWidth: true
                                        Shared.HelperText {
                                            Layout.fillWidth: true
                                            text: modelData.label
                                            font.pixelSize: theme.size_body
                                            font.weight: theme.weight_bold
                                        }
                                        Shared.StatusBadge {
                                            label: modelData.state
                                            variant: modelData.variant
                                        }
                                        Shared.AppButton {
                                            objectName: "show-" +
                                                modelData.name
                                            text: "Show window"
                                            size: "small"
                                            enabled: modelData.can_show
                                            onActiveFocusChanged: {
                                                if (!activeFocus)
                                                    return
                                                const view =
                                                    moduleScroll.contentItem
                                                const pos = mapToItem(
                                                    moduleRows, 0, 0)
                                                if (pos.y < view.contentY)
                                                    view.contentY = pos.y
                                                else if (pos.y + height >
                                                    view.contentY +
                                                    view.height)
                                                    view.contentY = pos.y
                                                        + height - view.height
                                            }
                                            Accessible.name: "Show "
                                                + modelData.label + " window"
                                            onClicked: backend.show_window(
                                                modelData.name)
                                        }
                                    }
                                    Shared.MonoText {
                                        Layout.fillWidth: true
                                        text: "PID " + modelData.pid_text
                                            + " · " + modelData.exit_text
                                        elide: Text.ElideRight
                                    }
                                }
                            }
                        }
                    }
                }

                ColumnLayout {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    spacing: theme.space_4
                    Shared.Panel {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        Layout.preferredHeight: 340
                        title: "Events"
                        EventList {
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                        }
                    }
                    Shared.Panel {
                        Layout.fillWidth: true
                        Layout.preferredHeight: 190
                        title: "Last outputs"
                        RowLayout {
                            Layout.fillWidth: true
                            Shared.SelectField {
                                Layout.fillWidth: true
                                label: "Module"
                                labelVisible: false
                                model: backend.modules
                                textRole: "label"
                                valueRole: "name"
                                currentIndex: {
                                    for (let i = 0;
                                         i < backend.modules.length; ++i)
                                        if (backend.modules[i].name
                                            === backend.selected_module)
                                            return i
                                    return -1
                                }
                                onCommitted: function(value) {
                                    backend.select_module(value)
                                }
                            }
                            Shared.HelperText {
                                text: "Read-only · 2 Hz"
                            }
                        }
                        ScrollView {
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            visible: backend.output_text !== "—"
                                && backend.output_module
                                    === backend.selected_module
                            TextArea {
                                objectName: "outputInspector"
                                text: backend.output_text
                                readOnly: true
                                selectByMouse: true
                                textFormat: TextEdit.PlainText
                                wrapMode: TextEdit.WrapAnywhere
                                font.family: theme.mono_family
                                font.pixelSize: theme.size_small
                                color: theme.text_primary
                                selectedTextColor: theme.on_accent
                                selectionColor: theme.accent
                                Accessible.name: "Selected module outputs"
                                background: Rectangle {
                                    color: theme.bg_sunken
                                    border.color: parent.activeFocus
                                        ? theme.focus_ring : theme.border
                                    border.width: parent.activeFocus ? 2 : 1
                                    radius: theme.radius_md
                                }
                            }
                        }
                        Shared.EmptyState {
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            visible: backend.output_text === "—"
                                || backend.output_module
                                    !== backend.selected_module
                            heading: "No outputs selected"
                            body: "Select a module to inspect its last reply."
                        }
                    }
                }
            }
            TextEdit {
                Layout.fillWidth: true
                Layout.preferredHeight: theme.control_h_sm
                text: "Event log: " + backend.snapshot.log_path
                readOnly: true
                selectByMouse: true
                textFormat: TextEdit.PlainText
                wrapMode: TextEdit.NoWrap
                font.family: theme.mono_family
                font.pixelSize: theme.size_small
                color: theme.text_secondary
                selectedTextColor: theme.on_accent
                selectionColor: theme.accent
                activeFocusOnTab: true
                Accessible.name: "Event log path"
                Rectangle {
                    anchors.fill: parent
                    color: "transparent"
                    border.width: parent.activeFocus ? 2 : 0
                    border.color: theme.focus_ring
                }
            }
        }
    }

    Dialog {
        id: endDialog
        objectName: "endRunDialog"
        parent: window.canvas
        anchors.centerIn: parent
        width: 520
        padding: theme.space_5
        modal: true
        focus: true
        closePolicy: Popup.NoAutoClose
        onOpened: cancelButton.forceActiveFocus(Qt.TabFocusReason)
        background: Rectangle {
            color: theme.bg_surface
            border.color: theme.border_strong
            radius: theme.radius_lg
        }
        contentItem: ColumnLayout {
            Keys.onEscapePressed: endDialog.close()
            spacing: theme.space_5
            Shared.HelperText {
                text: "End this run?"
                font.pixelSize: theme.size_h2
                font.weight: theme.weight_bold
            }
            Shared.HelperText {
                Layout.fillWidth: true
                text: "Every module will be asked to quit. Any module "
                    + "that remains will be stopped."
            }
            RowLayout {
                Layout.fillWidth: true
                Item { Layout.fillWidth: true }
                Shared.AppButton {
                    id: cancelButton
                    objectName: "cancelEndRun"
                    text: "Keep running"
                    onClicked: endDialog.close()
                }
                Shared.AppButton {
                    objectName: "confirmEndRun"
                    text: "End run"
                    variant: "danger"
                    onClicked: {
                        endDialog.close()
                        backend.end_run()
                    }
                }
            }
        }
    }
}
