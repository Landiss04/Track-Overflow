import QtQuick
import QtQuick.Layouts

import "components"
import "../../ui" as Shared

// PLC program details, opened from the info button beside the PLC program.
// Layout follows TrackCtrlHw/ui/html/track-controller-plc-details.html;
// every value is the running program's, not a placeholder.
ModalDialog {
    id: root

    property var program: ({})

    signal loadRequested()

    title: qsTr("PLC program details")
    dialogWidth: 640
    footerNote: qsTr("A new program replaces the running logic at the next "
        + "scan; every signal shows red until that scan completes.")

    footer: [
        Shared.AppButton {
            text: qsTr("Close")
            variant: "secondary"
            onClicked: root.close()
        },
        Shared.AppButton {
            text: qsTr("New PLC")
            variant: "primary"
            onClicked: {
                root.close();
                root.loadRequested();
            }
        }
    ]

    Shared.Panel {
        Layout.fillWidth: true
        title: qsTr("Running program")
        bodyPadding: theme.space_4

        headerItems: Shared.StatusBadge {
            variant: root.program.running ? "ok"
                : root.program.loaded ? "fault" : "idle"
            label: root.program.running ? qsTr("Scanning")
                : root.program.loaded ? qsTr("Held") : qsTr("No program")
        }

        Repeater {
            model: [
                [qsTr("File"), root.program.file],
                [qsTr("Loaded"), root.program.loadedAt],
                [qsTr("Checksum (CRC-32)"), root.program.checksum],
                [qsTr("Boolean variables"), root.program.booleans],
                [qsTr("Statements"), root.program.statements],
                [qsTr("Scan interval"), root.program.scanInterval],
                [qsTr("Last scan"), root.program.lastScan],
                [qsTr("Scan time"), root.program.scanTime],
                [qsTr("Scan overruns since load"), root.program.overruns]
            ]

            delegate: Shared.KeyValueRow {
                required property var modelData
                required property int index

                Layout.fillWidth: true
                label: modelData[0]
                value: modelData[1] === undefined ? "\u2014" : modelData[1]
                rule: index < 8
            }
        }

        Repeater {
            model: root.program.warnings !== undefined ? root.program.warnings : []

            delegate: Shared.HelperText {
                required property string modelData
                Layout.fillWidth: true
                text: modelData
                color: theme.warning
            }
        }
    }

    Shared.Panel {
        Layout.fillWidth: true
        title: qsTr("Outputs")
        bodyPadding: theme.space_4

        headerItems: Text {
            text: qsTr("Program, then vital block")
            textFormat: Text.PlainText
            color: theme.text_muted
            font.family: theme.ui_family
            font.pixelSize: theme.size_small
        }

        Shared.KeyValueRow {
            Layout.fillWidth: true
            label: qsTr("Channel A / B")
            value: root.program.channels !== undefined ? root.program.channels : "\u2014"
        }

        Shared.KeyValueRow {
            Layout.fillWidth: true
            label: qsTr("Channel fault")
            value: root.program.channelFault !== undefined ? root.program.channelFault : "\u2014"
        }

        Shared.KeyValueRow {
            Layout.fillWidth: true
            label: qsTr("Held fail-safe")
            value: root.program.holding !== undefined ? root.program.holding : "\u2014"
        }

        Shared.KeyValueRow {
            Layout.fillWidth: true
            label: qsTr("Vital block checksum (CRC-32)")
            value: root.program.vitalChecksum !== undefined ? root.program.vitalChecksum : "\u2014"
        }

        Shared.KeyValueRow {
            Layout.fillWidth: true
            label: qsTr("Vital block statements")
            value: root.program.vitalStatements !== undefined ? root.program.vitalStatements : "\u2014"
        }

        Shared.KeyValueRow {
            Layout.fillWidth: true
            label: qsTr("Overridden last scan")
            value: root.program.overrides !== undefined && root.program.overrides.length > 0
                ? root.program.overrides.join(", ") : qsTr("None")
            rule: false
        }

        Shared.HelperText {
            Layout.fillWidth: true
            text: qsTr("After the program, the wayside scans a read-only "
                + "vital block generated from its database, on both "
                + "channels. It can only restrict: no authority in a "
                + "closed block, beside an occupied block a train could "
                + "move into, or over a moving switch; no speed above the "
                + "block's limit; the CTC Office's switch commands obeyed "
                + "and switches locked under a train; a signal red unless "
                + "exactly one aspect is lit and its point is clear; a "
                + "crossing active for a train on or beside it. Every "
                + "output is held fail-safe only while no program runs: "
                + "none loaded, a new one not yet scanned, or channels A "
                + "and B disagreeing, which lasts until a new program is "
                + "loaded.")
        }
    }

    Shared.Panel {
        Layout.fillWidth: true
        title: qsTr("Vital block source")
        bodyPadding: theme.space_4

        Flickable {
            Layout.fillWidth: true
            Layout.preferredHeight: 180
            clip: true
            contentWidth: vitalText.implicitWidth
            contentHeight: vitalText.implicitHeight

            Shared.MonoText {
                id: vitalText
                text: root.program.vitalSource !== undefined ? root.program.vitalSource : ""
            }
        }
    }
}
