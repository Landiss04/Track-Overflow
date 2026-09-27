// Train Occupancy window. Rendered as a plain item on the design canvas
// rather than a Popup, because Popups reparent to the window overlay and
// would escape the canvas scale transform.
import QtQuick
import QtQuick.Layouts
import "../components"

Rectangle {
    id: root

    property var trains: []
    property int lineFilterIndex: 0
    property int statusFilterIndex: 0

    signal minimizeRequested()
    signal closeRequested()
    signal trainSelected(string trainId)

    color: theme.bg_surface
    border.color: theme.border
    border.width: 1
    radius: theme.radius_lg
    clip: true
    focus: visible

    Keys.onEscapePressed: root.closeRequested()

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 1
        spacing: 0

        // Title bar.
        RowLayout {
            Layout.fillWidth: true
            Layout.preferredHeight: theme.control_h_lg + theme.space_2
            Layout.leftMargin: theme.space_4
            Layout.rightMargin: theme.space_2
            spacing: theme.space_2

            Text {
                text: qsTr("Train occupancy")
                color: theme.text_primary
                font.family: theme.ui_family
                font.pixelSize: theme.size_h3
                font.weight: theme.weight_bold
            }

            HelperText {
                text: qsTr("%n active", "", root.trains.length)
                color: theme.text_muted
            }

            Item { Layout.fillWidth: true }

            AppButton {
                variant: "ghost"
                size: "small"
                text: "–"
                Accessible.name: qsTr("Minimize")
                onClicked: root.minimizeRequested()
            }

            AppButton {
                variant: "ghost"
                size: "small"
                text: "×"
                Accessible.name: qsTr("Close")
                onClicked: root.closeRequested()
            }
        }

        Rectangle {
            Layout.fillWidth: true
            implicitHeight: 1
            color: theme.border
        }

        // Filters.
        RowLayout {
            Layout.fillWidth: true
            Layout.margins: theme.space_4
            spacing: theme.space_3

            FormField {
                Layout.preferredWidth: 240
                label: qsTr("Search")

                ValueField {
                    Layout.fillWidth: true
                    placeholderText: qsTr("Train or block ID")
                }
            }

            FormField {
                label: qsTr("Line")

                SegmentedToggle {
                    options: [qsTr("All lines"), qsTr("Green"), qsTr("Red")]
                    currentIndex: root.lineFilterIndex
                    onActivated: function (index) {
                        root.lineFilterIndex = index;
                    }
                }
            }

            FormField {
                label: qsTr("Status")

                SegmentedToggle {
                    options: [qsTr("All"), qsTr("En route")]
                    currentIndex: root.statusFilterIndex
                    onActivated: function (index) {
                        root.statusFilterIndex = index;
                    }
                }
            }

            Item { Layout.fillWidth: true }
        }

        Rectangle {
            Layout.fillWidth: true
            implicitHeight: 1
            color: theme.border
        }

        DataTable {
            Layout.fillWidth: true
            Layout.margins: theme.space_4
            columns: [
                { title: qsTr("Train"), key: "train", width: 72,
                  mono: true },
                { title: qsTr("Line"), key: "line", width: 72 },
                { title: qsTr("Block"), key: "block", width: 64,
                  mono: true },
                { title: qsTr("Speed (m/s)"), key: "speed", width: 96,
                  numeric: true },
                { title: qsTr("Authority"), key: "authority", width: 88,
                  mono: true },
                { title: qsTr("Destination"), key: "destination" },
                { title: qsTr("ETA"), key: "eta", width: 64, mono: true },
                { title: qsTr("Status"), key: "status", width: 110 }
            ]
            rows: root.trains
            emptyText: qsTr("No trains on the network")
        }

        Item { Layout.fillHeight: true }

        // Footer.
        Rectangle {
            Layout.fillWidth: true
            implicitHeight: 1
            color: theme.border
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.margins: theme.space_3
            Layout.leftMargin: theme.space_4
            Layout.rightMargin: theme.space_4
            spacing: theme.space_3

            HelperText {
                Layout.fillWidth: true
                text: qsTr("Selecting a train highlights its route on the "
                    + "track view and loads its metrics into the CTC screen "
                    + "behind this window.")
            }

            AppButton {
                variant: "secondary"
                text: qsTr("Keep open at bottom")
                onClicked: root.minimizeRequested()
            }

            AppButton {
                variant: "primary"
                text: qsTr("Select train")
                // Enabled once row selection exists in the table.
                enabled: false
            }
        }
    }
}
