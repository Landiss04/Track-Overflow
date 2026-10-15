// Automatic dispatch: schedule file and upcoming departures.
import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Dialogs
import QtQuick.Layouts
import "../../../../ui"

Panel {
    id: root

    property string scheduleFile: ""
    // Dispatching a loaded schedule; paused by the dispatcher.
    property bool running: false
    property bool paused: false
    property var departures: []
    // Why the last schedule file was rejected; empty when it loaded.
    property string scheduleError: ""
    readonly property bool scheduleLoaded: scheduleFile !== ""

    // The backend reads and parses the file; the panel only picks it.
    signal scheduleFileSelected(url fileUrl)
    signal pauseRequested()
    signal resumeRequested()

    title: qsTr("Auto dispatch")

    headerItems: [
        StatusBadge {
            label: root.running ? qsTr("Running")
                : root.paused ? qsTr("Paused") : qsTr("Stopped")
            variant: root.running ? "ok" : root.paused ? "warning" : "idle"
        }
    ]

    RowLayout {
        Layout.fillWidth: true
        spacing: theme.space_3

        AppButton {
            Layout.fillWidth: true
            variant: "primary"
            text: root.paused ? qsTr("Resume dispatch")
                : qsTr("Pause dispatch")
            enabled: root.scheduleLoaded
            onClicked: root.paused ? root.resumeRequested()
                : root.pauseRequested()
        }

        AppButton {
            variant: "secondary"
            text: root.scheduleLoaded ? qsTr("Reload") : qsTr("Load schedule")
            onClicked: scheduleDialog.open()
        }
    }

    HelperText {
        Layout.fillWidth: true
        visible: root.paused
        color: theme.text_muted
        text: qsTr("Paused: no run leaves the yard or a stop until "
            + "dispatch resumes.")
    }

    FileDialog {
        id: scheduleDialog

        title: qsTr("Load schedule")
        fileMode: FileDialog.OpenFile
        nameFilters: [qsTr("Schedule files (*.json)"),
            qsTr("All files (*)")]
        // The CTC loads it and reports back scheduleFile or scheduleError.
        onAccepted: root.scheduleFileSelected(selectedFile)
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

    HelperText {
        Layout.fillWidth: true
        visible: root.scheduleError !== ""
        text: qsTr("Schedule not loaded: %1").arg(root.scheduleError)
        color: theme.danger
    }

    FieldLabel { text: qsTr("DEPARTURES") }

    HelperText {
        Layout.fillWidth: true
        visible: root.departures.length > 0
        text: qsTr("Each run leaves the yard when due (the schedule "
            + "starts at 05:00), stops 45 s at each of its scheduled "
            + "stations in track order and nowhere else, then returns "
            + "to the yard.")
        color: theme.text_muted
    }

    // A full schedule is taller than the panel, so the list scrolls.
    ScrollView {
        id: departuresScroll

        Layout.fillWidth: true
        Layout.fillHeight: true
        clip: true
        contentWidth: availableWidth

        ColumnLayout {
            width: departuresScroll.availableWidth
            spacing: 0

            DataTable {
                Layout.fillWidth: true
                columns: [
                    { label: qsTr("Due"), key: "time", width: 64,
                      mono: true },
                    { label: qsTr("Train"), key: "train", width: 56,
                      mono: true },
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
        }
    }
}
