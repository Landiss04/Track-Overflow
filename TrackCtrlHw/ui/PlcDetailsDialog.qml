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
            text: qsTr("Nothing above the program")
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
            rule: false
        }

        Shared.HelperText {
            Layout.fillWidth: true
            text: qsTr("The wayside runs the program and decides nothing "
                + "itself: separation, closures, switch locking and "
                + "correspondence, and crossings are all the program's. "
                + "A signal shows red if R is lit or none is, otherwise "
                + "the first lit of Y, G and SG. Every output is held "
                + "fail-safe only while no program runs: none loaded, a "
                + "new one not yet scanned, or channels A and B "
                + "disagreeing, which lasts until a new program is loaded.")
        }
    }
}
