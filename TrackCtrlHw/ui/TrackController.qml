import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

import "components"
import "../../ui" as Shared

// Track Controller — page 4. Layout and information architecture are a direct
// port of TrackCtrlHw/ui/html/track-controller.html; styling comes from the
// shared ui/ kit and its theme tokens.
Item {
    id: page

    property int simSeconds: 14 * 3600 + 32 * 60 + 7
    property int modeIndex: 0
    property int zoomPercent: 100

    readonly property bool maintenanceMode: modeIndex === 1

    readonly property string clockText: pad2(Math.floor(simSeconds / 3600) % 24) + ":" + pad2(Math.floor(simSeconds / 60) % 60) + ":" + pad2(simSeconds % 60)

    function pad2(n) {
        return n < 10 ? "0" + n : "" + n;
    }

    Timer {
        interval: 1000
        running: true
        repeat: true
        onTriggered: page.simSeconds += 1
    }

    // ---- data ------------------------------------------------------------
    readonly property var occupancyColumns: [
        { title: "Section", width: 100 },
        { title: "Block", width: 70 },
        { title: "Length", width: 96, align: "right" },
        { title: "Speed limit", width: 110, align: "right" },
        { title: "Occupancy", fill: true }
    ]

    readonly property var occupancyRows: [
        [{ text: "GREEN D", mono: true }, { text: "11", mono: true }, { text: "984 ft", mono: true }, { text: "25 mph", mono: true }, { badge: "ok", badgeText: "Clear" }],
        [{ text: "GREEN D", mono: true }, { text: "12", mono: true }, { text: "984 ft", mono: true }, { text: "25 mph", mono: true }, { badge: "ok", badgeText: "Clear" }],
        [{ text: "GREEN D", mono: true }, { text: "13", mono: true }, { text: "820 ft", mono: true }, { text: "25 mph", mono: true }, { badge: "ok", badgeText: "Clear" }],
        [{ text: "GREEN D", mono: true }, { text: "14", mono: true }, { text: "820 ft", mono: true }, { text: "25 mph", mono: true }, { badge: "ok", badgeText: "Clear" }],
        [{ text: "GREEN E", mono: true }, { text: "15", mono: true }, { text: "656 ft", mono: true }, { text: "15 mph", mono: true }, { badge: "info", badgeText: "Occupied", text: "T-104 \u2192", mono: true }],
        [{ text: "GREEN E", mono: true }, { text: "16", mono: true }, { text: "820 ft", mono: true }, { text: "25 mph", mono: true }, { badge: "ok", badgeText: "Clear" }],
        [{ text: "GREEN E", mono: true }, { text: "17", mono: true }, { text: "984 ft", mono: true }, { text: "25 mph", mono: true }, { badge: "info", badgeText: "Occupied", text: "T-117 \u2192", mono: true }],
        [{ text: "GREEN F", mono: true }, { text: "18", mono: true }, { text: "492 ft", mono: true }, { text: "10 mph", mono: true }, { badge: "ok", badgeText: "Clear", text: "Siding" }],
        [{ text: "GREEN F", mono: true }, { text: "19", mono: true }, { text: "492 ft", mono: true }, { text: "10 mph", mono: true }, { badge: "warning", badgeText: "Closed", text: "By dispatcher" }]
    ]

    readonly property var officeColumns: [
        { title: "Train", width: 90 },
        { title: "Block", width: 140 },
        { title: "Suggested speed", width: 150, align: "right" },
        { title: "Authority", fill: true }
    ]

    readonly property var officeRows: [
        [{ text: "T-104", mono: true }, { text: "GREEN E-15", mono: true }, { text: "15 mph", mono: true }, { text: "\u2192 GREEN E-16", mono: true }],
        [{ text: "T-117", mono: true }, { text: "GREEN E-17", mono: true }, { text: "25 mph", mono: true }, { text: "\u2192 GREEN G-21", mono: true }]
    ]

    readonly property var switchColumns: [
        { title: "Switch", width: 90 },
        { title: "Commanded", width: 100 },
        { title: "Reported", width: 100 },
        { title: "Set by", fill: true },
        { title: "", width: 130 }
    ]

    readonly property var switchRows: [
        [{ text: "SW-1", mono: true }, { text: "Normal" }, { text: "Normal" }, { text: "PLC \u00B7 14 / 18", mono: true, tone: "secondary" }, { button: "Set reverse", enabled: page.maintenanceMode }],
        [{ text: "SW-2", mono: true }, { text: "Normal" }, { text: "Normal" }, { text: "PLC \u00B7 17 / yard", mono: true, tone: "secondary" }, { button: "Set reverse", enabled: page.maintenanceMode }]
    ]

    readonly property var signalColumns: [
        { title: "Device", width: 90 },
        { title: "Location", width: 112 },
        { title: "State 1", fill: true },
        { title: "State 2", fill: true },
        { title: "Set by", width: 52 }
    ]

    readonly property var signalRows: [
        [{ text: "SIG-11/12", mono: true }, { text: "GREEN D 11/12", mono: true }, { text: "11\u219212: SUPER GREEN", mono: true }, { text: "12\u219211: SUPER GREEN", mono: true }, { text: "PLC", tone: "secondary" }],
        [{ text: "SIG-12/13", mono: true }, { text: "GREEN D 12/13", mono: true }, { text: "12\u219213: GREEN", mono: true }, { text: "13\u219212: SUPER GREEN", mono: true }, { text: "PLC", tone: "secondary" }],
        [{ text: "SIG-14/15", mono: true }, { text: "GREEN D/E 14/15", mono: true }, { text: "14\u219215: RED", mono: true }, { text: "15\u219214: SUPER GREEN", mono: true }, { text: "PLC", tone: "secondary" }],
        [{ text: "SIG-15/16", mono: true }, { text: "GREEN E 15/16", mono: true }, { text: "15\u219216: YELLOW", mono: true }, { text: "16\u219215: RED", mono: true }, { text: "PLC", tone: "secondary" }],
        [{ text: "XING-15", mono: true }, { text: "GREEN E 15", mono: true }, { text: "Lights, gates down" }, { text: "" }, { text: "PLC", tone: "secondary" }]
    ]

    // ---- shell -----------------------------------------------------------
    Rectangle {
        anchors.fill: parent
        color: theme.bg_app
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        TrackCtrlHeader {
            Layout.fillWidth: true
            moduleName: "Track Controller"
            instance: "Green Line \u00B7 Wayside 1"
            mode: page.maintenanceMode ? "Maintenance" : "Automatic"
            modeKind: page.maintenanceMode ? "warning" : "info"
            clock: page.clockText

            controls: [
                Shared.SelectField {
                    label: "Wayside"
                    model: ["1", "2", "3"]
                    // A ColumnLayout fills by default; this field is fixed width.
                    Layout.fillWidth: false
                    Layout.preferredWidth: 96
                },
                Shared.AppButton {
                    text: "Load database"
                    Layout.alignment: Qt.AlignVCenter
                },
                Shared.SegmentedToggle {
                    options: ["Automatic", "Maintenance"]
                    currentIndex: page.modeIndex
                    Layout.alignment: Qt.AlignVCenter
                    onActivated: index => page.modeIndex = index
                }
            ]
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.margins: theme.space_5
            spacing: theme.space_4

            // ---- dominant visual + the occupancy it comes from ----------
            ColumnLayout {
                Layout.fillWidth: true
                Layout.fillHeight: true
                spacing: theme.space_4

                Panel {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    title: "Wayside territory"
                    bodyPadding: theme.space_3

                    headerContent: [
                        Text {
                            text: "Sections D\u2013F \u00B7 Blocks 11\u201319"
                            color: theme.text_muted
                            font.family: theme.ui_family
                            font.pixelSize: theme.size_small
                        },
                        IconButton {
                            size: "sm"
                            glyph: "\u2212"
                            tip: "Zoom out"
                            onClicked: page.zoomPercent = Math.max(50, page.zoomPercent - 25)
                        },
                        Text {
                            text: page.zoomPercent + "%"
                            color: theme.text_muted
                            font.family: theme.mono_family
                            font.pixelSize: theme.size_small
                        },
                        IconButton {
                            size: "sm"
                            glyph: "+"
                            tip: "Zoom in"
                            onClicked: page.zoomPercent = Math.min(200, page.zoomPercent + 25)
                        }
                    ]

                    TerritoryDiagram {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        zoom: page.zoomPercent / 100
                    }
                }

                Panel {
                    Layout.fillWidth: true
                    // Panel header 44 + table header 32 + 4 whole rows.
                    Layout.preferredHeight: 220
                    title: "Block occupancy"
                    bodyPadding: 0

                    headerContent: Text {
                        text: "From track model \u00B7 14:32:05"
                        color: theme.text_muted
                        font.family: theme.ui_family
                        font.pixelSize: theme.size_small
                    }

                    DataTable {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        columns: page.occupancyColumns
                        rows: page.occupancyRows
                    }
                }
            }

            // ---- control / readout column -------------------------------
            // Heights are fixed to the 1440 x 900 canvas, so nothing here
            // reacts to the window. A table taller than its panel scrolls
            // inside the panel rather than the column scrolling as a whole.
            // Pinned: the banner's wrapped text reports its unwrapped width as
            // implicit width and would otherwise crowd out the territory view.
            ColumnLayout {
                Layout.fillWidth: false
                Layout.preferredWidth: 616
                Layout.minimumWidth: 616
                Layout.maximumWidth: 616
                Layout.fillHeight: true
                spacing: theme.space_4

                Banner {
                    Layout.fillWidth: true
                    kind: page.maintenanceMode ? "warning" : "info"
                    heading: page.maintenanceMode ? "Maintenance mode" : "Automatic mode"
                    body: page.maintenanceMode ? "Manual switch commands are unlocked. The PLC program no longer has sole authority over switches, signals and the crossing." : "The loaded PLC program is setting switches, signals and the crossing, so manual switch commands unlock only in Maintenance mode."
                }

                Panel {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 148
                    title: "Wayside PLC"

                    RowLayout {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        spacing: theme.space_3

                        Readout {
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            Layout.minimumWidth: 150
                            label: "Program running"
                            value: "wayside-1-v7.plc"
                            compact: true
                        }

                        Readout {
                            Layout.fillHeight: true
                            Layout.minimumWidth: 90
                            label: "Uploaded"
                            value: "14:02"
                            compact: true
                        }

                        Readout {
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            Layout.minimumWidth: 140
                            label: "CTC uplink"
                            value: "sent 14:32:06"
                            compact: true
                        }

                        ColumnLayout {
                            Layout.alignment: Qt.AlignVCenter
                            Layout.preferredWidth: 150
                            spacing: theme.space_2

                            Shared.AppButton {
                                Layout.fillWidth: true
                                variant: "primary"
                                text: "Load PLC file"
                            }

                            Shared.AppButton {
                                Layout.fillWidth: true
                                size: "small"
                                text: "Last report"
                            }
                        }
                    }
                }

                Panel {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 148
                    title: "From the office"
                    bodyPadding: 0

                    headerContent: Text {
                        text: "Received 14:31:58"
                        color: theme.text_muted
                        font.family: theme.ui_family
                        font.pixelSize: theme.size_small
                    }

                    DataTable {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        columns: page.officeColumns
                        rows: page.officeRows
                    }
                }

                Panel {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 148
                    title: "Switches"
                    bodyPadding: 0

                    headerContent: Shared.StatusBadge {
                        variant: "ok"
                        label: "2 of 2 agreeing"
                    }

                    DataTable {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        columns: page.switchColumns
                        rows: page.switchRows
                    }
                }

                Panel {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    Layout.minimumHeight: 148
                    title: "Signals & crossings"
                    bodyPadding: 0

                    headerContent: Text {
                        text: "Set by PLC \u00B7 14:32:06"
                        color: theme.text_muted
                        font.family: theme.ui_family
                        font.pixelSize: theme.size_small
                    }

                    DataTable {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        columns: page.signalColumns
                        rows: page.signalRows
                    }
                }
            }
        }
    }
}
