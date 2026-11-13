// Confirm loading a track configuration.
//
// Loading a layout replaces the line of the same name: its waysides are
// divided up again, so the controllers on it and every program they hold
// go. That is the one destructive thing this window does, so the dialog
// says what the file is and what it will replace. How many waysides a
// line has is fixed by the track, so it is shown, never chosen.
import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

Dialog {
    id: root

    property url file
    property var info: ({})
    property string failure: ""

    readonly property bool readable: info.ok === true

    function openFor(url) {
        file = url;
        info = wayside.inspectTrackConfig(url);
        failure = "";
        open();
    }

    modal: true
    anchors.centerIn: parent
    width: 460
    padding: 0
    closePolicy: Popup.CloseOnEscape

    background: Rectangle {
        color: theme.bg_surface
        border.color: theme.border_strong
        border.width: 1
        radius: theme.radius_md
    }

    contentItem: ColumnLayout {
        spacing: 0

        Rectangle {
            Layout.fillWidth: true
            implicitHeight: theme.control_h_md
            color: theme.bg_sunken

            Text {
                anchors.left: parent.left
                anchors.leftMargin: theme.space_4
                anchors.verticalCenter: parent.verticalCenter
                text: qsTr("LOAD TRACK CONFIGURATION")
                color: theme.text_secondary
                font.family: theme.ui_family
                font.pixelSize: theme.size_label
                font.weight: theme.weight_bold
                font.letterSpacing: theme.label_letter_spacing
            }

            Rectangle {
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.bottom: parent.bottom
                implicitHeight: 1
                color: theme.border
            }
        }

        ColumnLayout {
            Layout.fillWidth: true
            Layout.margins: theme.space_4
            spacing: theme.space_4

            // The file could not be used: say why and offer nothing else.
            Rectangle {
                Layout.fillWidth: true
                visible: !root.readable
                implicitHeight: refusal.implicitHeight + 2 * theme.space_3
                color: theme.danger_bg
                border.color: theme.danger
                border.width: 1
                radius: theme.radius_sm

                Text {
                    id: refusal
                    anchors.fill: parent
                    anchors.margins: theme.space_3
                    text: root.info.error === undefined ? "" : root.info.error
                    color: theme.danger
                    font.family: theme.ui_family
                    font.pixelSize: theme.size_small
                    wrapMode: Text.WordWrap
                }
            }

            ColumnLayout {
                Layout.fillWidth: true
                visible: root.readable
                spacing: theme.space_2

                SignalRow {
                    Layout.fillWidth: true
                    label: qsTr("File")
                    value: root.info.file === undefined ? "" : root.info.file
                }

                SignalRow {
                    Layout.fillWidth: true
                    label: qsTr("Line")
                    value: root.info.line === undefined ? "" : root.info.line
                }

                SignalRow {
                    Layout.fillWidth: true
                    label: qsTr("Blocks")
                    value: String(root.info.blocks || 0)
                }

                SignalRow {
                    Layout.fillWidth: true
                    label: qsTr("Switches")
                    value: String(root.info.switches || 0)
                }

                SignalRow {
                    Layout.fillWidth: true
                    label: qsTr("Crossings")
                    value: String(root.info.crossings || 0)
                }
            }

            ColumnLayout {
                Layout.fillWidth: true
                visible: root.readable
                spacing: theme.space_2

                FieldLabel { text: qsTr("Wayside controllers on this line") }

                RowLayout {
                    spacing: theme.space_3

                    MonoText {
                        text: root.readable ? String(root.info.controllers) : ""
                        color: theme.text_primary
                        font.pixelSize: theme.size_body
                    }

                    Text {
                        Layout.fillWidth: true
                        text: root.readable
                            ? qsTr("Fixed by the track. About %1 blocks each; "
                                + "each needs its own PLC program.").arg(
                                    Math.round(root.info.blocks
                                        / root.info.controllers))
                            : ""
                        color: theme.text_muted
                        font.family: theme.ui_family
                        font.pixelSize: theme.size_label
                        wrapMode: Text.WordWrap
                    }
                }
            }

            Rectangle {
                Layout.fillWidth: true
                visible: root.readable && root.info.replaces > 0
                implicitHeight: warning.implicitHeight + 2 * theme.space_3
                color: theme.warning_bg
                border.color: theme.warning
                border.width: 1
                radius: theme.radius_sm

                Text {
                    id: warning
                    anchors.fill: parent
                    anchors.margins: theme.space_3
                    text: qsTr("This replaces the %1 controllers now on %2, "
                        + "and every program and committed iteration they "
                        + "hold. That cannot be undone.")
                        .arg(root.info.replaces).arg(root.info.line)
                    color: theme.warning
                    font.family: theme.ui_family
                    font.pixelSize: theme.size_label
                    wrapMode: Text.WordWrap
                }
            }

            Text {
                Layout.fillWidth: true
                visible: root.failure !== ""
                text: root.failure
                color: theme.danger
                font.family: theme.ui_family
                font.pixelSize: theme.size_small
                wrapMode: Text.WordWrap
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: theme.space_2

                Item { Layout.fillWidth: true }

                AppButton {
                    text: root.readable ? qsTr("Cancel") : qsTr("Close")
                    variant: "secondary"
                    onClicked: root.close()
                }

                AppButton {
                    text: qsTr("Load")
                    variant: root.info.replaces > 0 ? "danger" : "primary"
                    visible: root.readable
                    onClicked: {
                        const message = wayside.loadTrackConfig(root.file);
                        if (message === "")
                            root.close();
                        else
                            root.failure = message;
                    }
                }
            }
        }
    }
}
