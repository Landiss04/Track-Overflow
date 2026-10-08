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
        title: qsTr("Collision protection")
        bodyPadding: theme.space_4

        headerItems: Text {
            text: qsTr("Above the program")
            textFormat: Text.PlainText
            color: theme.text_muted
            font.family: theme.ui_family
            font.pixelSize: theme.size_small
        }

        Repeater {
            model: root.program.rules !== undefined ? root.program.rules : []

            delegate: Shared.KeyValueRow {
                required property var modelData
                Layout.fillWidth: true
                label: modelData.rule
                value: modelData.action
            }
        }

        Shared.KeyValueRow {
            Layout.fillWidth: true
            label: qsTr("Channel A / B")
            value: root.program.channels !== undefined ? root.program.channels : "\u2014"
        }

        Shared.KeyValueRow {
            Layout.fillWidth: true
            label: qsTr("Vital fault")
            value: root.program.vitalFault !== undefined ? root.program.vitalFault : "\u2014"
            rule: false
        }

        Shared.HelperText {
            Layout.fillWidth: true
            text: qsTr("A loaded program cannot override these checks. They "
                + "run after every scan, before any command reaches the "
                + "track, and can only make an output more restrictive. "
                + "Both channels run the program by different algorithms; "
                + "if they ever disagree, the wayside holds every output.")
        }

        Shared.FieldLabel {
            Layout.fillWidth: true
            Layout.topMargin: theme.space_2
            text: qsTr("INTERVENTIONS ON THE LAST SCAN")
        }

        Shared.HelperText {
            Layout.fillWidth: true
            visible: root.program.interventions === undefined
                || root.program.interventions.length === 0
            text: qsTr("None.")
        }

        Repeater {
            model: root.program.interventions !== undefined ? root.program.interventions : []

            delegate: Shared.MonoText {
                required property string modelData
                Layout.fillWidth: true
                text: modelData
                wrapMode: Text.WordWrap
            }
        }
    }
}
