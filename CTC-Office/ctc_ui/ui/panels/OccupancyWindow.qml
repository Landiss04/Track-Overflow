// Train Occupancy window. Rendered as a plain item on the design canvas
// rather than a Popup, because Popups reparent to the window overlay and
// would escape the canvas scale transform.
import QtQuick
import QtQuick.Layouts
import "../../../../ui"

Rectangle {
    id: root

    // Every known train, from CtcHost.trains.
    property var trains: []
    property int lineFilterIndex: 0
    property int statusFilterIndex: 0
    property string search: ""
    // The trains the filters let through.
    readonly property var shownTrains: trains.filter(function (train) {
        const line = ["", "Green", "Red"][root.lineFilterIndex];
        return (line === "" || train.line === line)
            && (root.statusFilterIndex === 0
                || train.status === "En route")
            && (root.search === ""
                || train.train.toLowerCase().indexOf(
                    root.search.toLowerCase()) >= 0);
    })
    property string pickedTrain: ""
    readonly property int pickedIndex: {
        for (let i = 0; i < shownTrains.length; ++i) {
            if (shownTrains[i].train === root.pickedTrain)
                return i;
        }
        return -1;
    }

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
                text: qsTr("%n known", "", root.trains.length)
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

            ValueField {
                Layout.preferredWidth: 240
                label: qsTr("Search train")
                onCommitted: function (value) { root.search = value; }
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
                { label: qsTr("Train"), key: "train", width: 72,
                  mono: true },
                { label: qsTr("Line"), key: "line", width: 72 },
                { label: qsTr("Block"), key: "block", width: 64,
                  mono: true },
                { label: qsTr("Speed (mph)"), key: "speed", width: 96,
                  numeric: true },
                { label: qsTr("Authority"), key: "authority", width: 104,
                  mono: true },
                { label: qsTr("Destination"), key: "destination" },
                { label: qsTr("Arrive"), key: "eta", width: 64,
                  mono: true },
                { label: qsTr("Status"), key: "status", width: 110 }
            ]
            rows: root.shownTrains
            currentIndex: root.pickedIndex
            onRowActivated: function (index, row) {
                root.pickedTrain = row.train;
            }
        }

        HelperText {
            Layout.fillWidth: true
            Layout.topMargin: theme.space_2
            visible: root.shownTrains.length === 0
            horizontalAlignment: Text.AlignHCenter
            text: root.trains.length === 0
                ? qsTr("No trains on the network")
                : qsTr("No trains match the filters")
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
                enabled: root.pickedIndex >= 0
                onClicked: root.trainSelected(root.pickedTrain)
            }
        }
    }
}
