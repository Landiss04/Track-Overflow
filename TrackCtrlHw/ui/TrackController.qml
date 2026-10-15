import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Dialogs
import QtQuick.Layouts

import "components"
import "../../ui" as Shared

// Track Controller window. Every value comes from the module through the
// `trackController` context property (track_ctrl_hw.state); nothing here is
// sample data. Layout follows TrackCtrlHw/ui/html/; styling comes from the
// shared ui/ kit and its theme tokens.
Item {
    id: page

    readonly property var tc: trackController
    readonly property bool loaded: tc.selectedWayside !== ""
    readonly property string waysideName: loaded ? qsTr("Wayside %1").arg(tc.selectedWayside) : ""

    Rectangle {
        anchors.fill: parent
        color: theme.bg_app
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        TrackCtrlHeader {
            Layout.fillWidth: true
            moduleName: qsTr("Track Controller")
            instance: page.loaded ? tc.line + qsTr(" Line \u00b7 ") + page.waysideName : ""
            mode: tc.maintenance ? qsTr("Maintenance") : qsTr("Automatic")
            modeKind: tc.maintenance ? "warning" : "info"
            faultText: tc.vitalFault !== "" ? qsTr("Vital fault") : ""
            source: tc.sourceText
            clock: tc.clockText

            controls: [
                Shared.SelectField {
                    label: qsTr("Wayside")
                    model: tc.waysides
                    currentIndex: tc.waysides.indexOf(tc.selectedWayside)
                    enabled: tc.waysides.length > 0
                    // A ColumnLayout fills by default; this field is fixed width.
                    Layout.fillWidth: false
                    Layout.preferredWidth: 96
                    onCommitted: function (value) { tc.selectWayside(value); }
                },
                Shared.AppButton {
                    text: qsTr("Load database")
                    Layout.alignment: Qt.AlignBottom
                    onClicked: databaseDialog.open()
                }
            ]
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.margins: theme.space_5
            spacing: theme.space_4

            // ---- territory and the blocks it is made of ----------------
            ColumnLayout {
                Layout.fillWidth: true
                Layout.fillHeight: true
                spacing: theme.space_3

                Shared.Panel {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    Layout.preferredHeight: 340
                    title: qsTr("Wayside territory")
                    bodyPadding: theme.space_3

                    headerItems: [
                        Text {
                            text: tc.territorySummary
                            textFormat: Text.PlainText
                            color: theme.text_muted
                            font.family: theme.ui_family
                            font.pixelSize: theme.size_small
                        },
                        IconButton {
                            size: "sm"
                            glyph: "\u2212"
                            tip: qsTr("Zoom out")
                            enabled: page.loaded && diagram.zoom > 1
                            onClicked: diagram.zoomOut()
                        },
                        Text {
                            text: Math.round(diagram.zoom * 100) + "%"
                            textFormat: Text.PlainText
                            color: theme.text_muted
                            font.family: theme.mono_family
                            font.pixelSize: theme.size_small
                            horizontalAlignment: Text.AlignHCenter
                            Layout.preferredWidth: 44
                        },
                        IconButton {
                            size: "sm"
                            glyph: "+"
                            tip: qsTr("Zoom in")
                            enabled: page.loaded && diagram.zoom < diagram.maxZoom
                            onClicked: diagram.zoomIn()
                        },
                        Shared.AppButton {
                            size: "small"
                            text: qsTr("Fit")
                            tooltip: qsTr("Show the whole territory (double-click the drawing)")
                            enabled: page.loaded && diagram.zoom > 1
                            onClicked: diagram.fit()
                        }
                    ]

                    Item {
                        Layout.fillWidth: true
                        Layout.fillHeight: true

                        TerritoryDiagram {
                            id: diagram
                            objectName: "territoryDiagram"
                            anchors.fill: parent
                            diagram: tc.diagram
                            visible: page.loaded
                        }

                        Shared.EmptyState {
                            anchors.centerIn: parent
                            visible: !page.loaded
                            heading: qsTr("No wayside loaded")
                            body: qsTr("Load a wayside database to see its territory.")
                        }
                    }

                    DiagramLegend {
                        Layout.fillWidth: true
                        visible: page.loaded
                    }
                }

                Shared.Panel {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 420
                    title: qsTr("Block occupancy")
                    bodyPadding: 0

                    headerItems: Text {
                        text: tc.receivedText === "" ? qsTr("From Track Model")
                            : qsTr("From Track Model \u00b7 ") + tc.receivedText
                        textFormat: Text.PlainText
                        color: theme.text_muted
                        font.family: theme.ui_family
                        font.pixelSize: theme.size_small
                    }

                    DataTable {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        model: tc.blocks
                        emptyText: qsTr("Load a wayside database to list its blocks.")
                        columns: [
                            { title: qsTr("Section"), role: "section", width: 72, mono: true },
                            { title: qsTr("Block"), role: "block", width: 56, mono: true },
                            { title: qsTr("Length"), role: "length", width: 80, mono: true, align: "right" },
                            { title: qsTr("Speed limit"), role: "limit", width: 96, mono: true, align: "right" },
                            { title: qsTr("Occupancy"), role: "stateText", badgeRole: "badge", width: 148 },
                            { title: qsTr("Track circuit"), role: "circuit", fill: true, mono: true }
                        ]
                    }
                }
            }

            // ---- control and readout column ------------------------------
            // Pinned width: wrapped text would otherwise report its unwrapped
            // width and crowd out the territory view.
            ColumnLayout {
                Layout.fillWidth: false
                Layout.preferredWidth: 616
                Layout.minimumWidth: 616
                Layout.maximumWidth: 616
                Layout.fillHeight: true
                spacing: theme.space_3

                Banner {
                    Layout.fillWidth: true
                    compact: true
                    kind: tc.maintenance ? "warning" : "info"
                    heading: tc.maintenance ? qsTr("MAINTENANCE") : qsTr("AUTOMATIC")
                    body: tc.maintenance
                        ? qsTr("The CTC Office sets the switches. The PLC still sets signals and crossings.")
                        : qsTr("The PLC program sets switches, signals and crossings.")
                }

                RowLayout {
                    Layout.fillWidth: true
                    spacing: theme.space_3

                    StatusStrip {
                        Layout.fillWidth: true
                        Layout.preferredWidth: 3
                        label: qsTr("Wayside PLC")
                        value: tc.program.loaded ? tc.program.file : qsTr("No program loaded")
                        detail: tc.program.loaded ? qsTr("Loaded ") + tc.program.loadedAt : ""

                        Shared.AppButton {
                            size: "small"
                            variant: "primary"
                            text: qsTr("New PLC")
                            enabled: page.loaded
                            tooltip: page.loaded ? "" : qsTr("Load a database first")
                            onClicked: programDialog.open()
                        }

                        IconButton {
                            size: "sm"
                            glyph: "i"
                            tip: qsTr("PLC program details")
                            enabled: page.loaded
                            onClicked: plcDetails.open()
                        }
                    }

                    StatusStrip {
                        Layout.fillWidth: true
                        Layout.preferredWidth: 2
                        label: qsTr("CTC uplink")
                        value: page.loaded ? tc.uplinkText : "\u2014"

                        Shared.AppButton {
                            size: "small"
                            text: qsTr("View")
                            tooltip: qsTr("Last report sent to the CTC Office")
                            enabled: page.loaded
                            onClicked: lastReport.open()
                        }
                    }
                }

                Shared.Panel {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    Layout.preferredHeight: 150
                    title: qsTr("From the office")
                    bodyPadding: 0

                    headerItems: Text {
                        text: tc.receivedText === "" ? "" : qsTr("Received ") + tc.receivedText
                        textFormat: Text.PlainText
                        color: theme.text_muted
                        font.family: theme.ui_family
                        font.pixelSize: theme.size_small
                    }

                    DataTable {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        model: tc.office
                        emptyText: qsTr("No speed or authority suggested for this wayside's blocks.")
                        columns: [
                            { title: qsTr("Block"), role: "block", width: 96, mono: true },
                            { title: qsTr("Suggested speed"), role: "speed", fill: true, mono: true, align: "right" },
                            { title: qsTr("Authority"), role: "authority", fill: true, mono: true, align: "right" }
                        ]
                    }
                }

                Shared.Panel {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    Layout.preferredHeight: 150
                    title: qsTr("Switches")
                    bodyPadding: 0

                    headerItems: Shared.StatusBadge {
                        visible: tc.switchCount > 0
                        variant: tc.switchesAgreeing === tc.switchCount ? "ok" : "fault"
                        label: qsTr("%1 of %2 agreeing").arg(tc.switchesAgreeing).arg(tc.switchCount)
                    }

                    DataTable {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        model: tc.switches
                        emptyText: page.loaded ? qsTr("This wayside has no switches.") : ""
                        columns: [
                            { title: qsTr("Switch"), role: "name", width: 72, mono: true },
                            { title: qsTr("Commanded"), role: "commanded", fill: true, mono: true },
                            { title: qsTr("Reported"), role: "reported", width: 80 },
                            { title: qsTr("Set by"), role: "setBy", width: 96, tone: "secondary" },
                            { title: qsTr("Agreement"), role: "agreeText", badgeRole: "agreeBadge", width: 144 }
                        ]
                    }
                }

                Shared.Panel {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    Layout.preferredHeight: 190
                    title: qsTr("Signals & crossings")
                    bodyPadding: 0

                    headerItems: Text {
                        text: tc.program.lastScan !== undefined && tc.program.lastScan !== "--:--:--"
                            ? qsTr("Last scan ") + tc.program.lastScan : ""
                        textFormat: Text.PlainText
                        color: theme.text_muted
                        font.family: theme.ui_family
                        font.pixelSize: theme.size_small
                    }

                    DataTable {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        model: tc.devices
                        emptyText: page.loaded ? qsTr("This wayside has no signals or crossings.") : ""
                        columns: [
                            { title: qsTr("Device"), role: "name", width: 80, mono: true },
                            { title: qsTr("Block"), role: "location", width: 56, mono: true },
                            { title: qsTr("Commanded"), role: "commanded", fill: true },
                            { title: qsTr("Reported"), role: "reported", fill: true },
                            { title: qsTr("Set by"), role: "setBy", width: 56, tone: "secondary" }
                        ]
                    }
                }
            }
        }
    }

    PlcDetailsDialog {
        id: plcDetails
        objectName: "plcDetails"
        anchors.fill: parent
        program: tc.program
        meta: page.waysideName
        onLoadRequested: programDialog.open()
    }

    LastReportDialog {
        id: lastReport
        objectName: "lastReport"
        anchors.fill: parent
        model: tc.report
        waysideName: page.waysideName
        sentText: tc.uplinkText
    }

    ModalDialog {
        id: messageDialog
        anchors.fill: parent
        dialogWidth: 560
        property string message: ""
        property var details: []

        footer: Shared.AppButton {
            text: qsTr("Close")
            variant: "primary"
            onClicked: messageDialog.close()
        }

        Shared.HelperText {
            Layout.fillWidth: true
            text: messageDialog.message
            color: theme.text_primary
        }

        Repeater {
            model: messageDialog.details

            delegate: Shared.MonoText {
                required property string modelData
                Layout.fillWidth: true
                text: modelData
                color: theme.danger
                wrapMode: Text.WordWrap
            }
        }
    }

    Connections {
        target: trackController
        function onProblem(title, message, details) {
            messageDialog.title = title;
            messageDialog.message = message;
            messageDialog.details = details;
            messageDialog.open();
        }
        function onNotice(title, message) {
            messageDialog.title = title;
            messageDialog.message = message;
            messageDialog.details = [];
            messageDialog.open();
        }
    }

    FileDialog {
        id: databaseDialog
        title: qsTr("Load a wayside database")
        nameFilters: [qsTr("Wayside database (*.json)"), qsTr("All files (*)")]
        currentFolder: databaseFolder
        onAccepted: tc.loadDatabase(String(selectedFile))
    }

    FileDialog {
        id: programDialog
        title: qsTr("Load a PLC program into %1").arg(page.waysideName)
        nameFilters: [qsTr("PLC program (*.plc)"), qsTr("All files (*)")]
        currentFolder: programFolder
        onAccepted: tc.loadProgram(String(selectedFile))
    }
}
