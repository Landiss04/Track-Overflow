// Automatic dispatch: schedule file and upcoming departures.
import QtQuick
import QtQuick.Dialogs
import QtQuick.Layouts
import "../../../../ui"

Panel {
    id: root

    property string scheduleFile: ""
    property bool running: false
    property var departures: []
    readonly property bool scheduleLoaded: scheduleFile !== ""

    // The backend reads and parses the file; the panel only picks it.
    signal scheduleFileSelected(url fileUrl)
    signal pauseRequested()

    title: qsTr("Auto dispatch")

    headerItems: [
        StatusBadge {
            label: root.running ? qsTr("Running") : qsTr("Stopped")
            variant: root.running ? "ok" : "idle"
        }
    ]

    RowLayout {
        Layout.fillWidth: true
        spacing: theme.space_3

        AppButton {
            Layout.fillWidth: true
            variant: "primary"
            text: qsTr("Pause dispatch")
            enabled: root.running
            onClicked: root.pauseRequested()
        }

        AppButton {
            variant: "secondary"
            text: root.scheduleLoaded ? qsTr("Reload") : qsTr("Load schedule")
            onClicked: scheduleDialog.open()
        }
    }

    FileDialog {
        id: scheduleDialog

        title: qsTr("Load schedule")
        fileMode: FileDialog.OpenFile
        // No schedule file format is decided yet, so accept any file.
        nameFilters: [qsTr("All files (*)")]
        onAccepted: {
            const path = decodeURIComponent(selectedFile.toString());
            root.scheduleFile = path.substring(path.lastIndexOf("/") + 1);
            root.scheduleFileSelected(selectedFile);
        }
    }

    Rectangle {
        Layout.fillWidth: true
        implicitHeight: wellColumn.implicitHeight + 2 * theme.space_3
        color: theme.bg_sunken
        border.color: theme.border
        border.width: 1
        radius: theme.radius_md

        ColumnLayout {
            id: wellColumn
            anchors.fill: parent
            anchors.topMargin: theme.space_3
            anchors.bottomMargin: theme.space_3
            anchors.leftMargin: theme.space_4
            anchors.rightMargin: theme.space_4
            spacing: theme.space_1

            FieldLabel { text: qsTr("SCHEDULE FILE") }

            MonoText {
                Layout.fillWidth: true
                text: root.scheduleLoaded
                    ? root.scheduleFile : qsTr("No schedule loaded")
                color: root.scheduleLoaded
                    ? theme.text_primary : theme.text_muted
                elide: Text.ElideMiddle
            }
        }
    }

    FieldLabel { text: qsTr("NEXT DEPARTURES") }

    DataTable {
        Layout.fillWidth: true
        columns: [
            { label: qsTr("Time"), key: "time", width: 64, mono: true },
            { label: qsTr("Train"), key: "train", width: 72, mono: true },
            { label: qsTr("Status"), key: "status" }
        ]
        rows: root.departures
    }

    HelperText {
        Layout.fillWidth: true
        Layout.topMargin: theme.space_2
        visible: root.departures.length === 0
        horizontalAlignment: Text.AlignHCenter
        text: qsTr("No departures scheduled")
    }

    Item { Layout.fillHeight: true }
}
