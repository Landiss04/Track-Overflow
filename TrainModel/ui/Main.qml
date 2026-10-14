// Train Model application window.
import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import QtQuick.Window
import "../../ui"

ScaledWindow {
    id: window

    // The selected train; an idle stand-in while the fleet is empty.
    readonly property var trainModel: fleet.current
    readonly property var snapshot: window.trainModel.snapshot

    title: qsTr("Train Model")

    // The design is laid out once at the reference size and scaled as a
    // whole. On Windows, main.py keeps the window at 16:10 while it is
    // resized; any other shape (maximized, snapped, fullscreen, Linux) is
    // letterboxed around the centered canvas.
    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        ModuleHeader {
            Layout.fillWidth: true
            moduleName: qsTr("Train Model")
            instance: window.snapshot.train_id
            // Running while steps arrive, from the test UI or, once
            // integrated, the central harness.
            mode: window.trainModel.running ? qsTr("Running") : qsTr("Paused")
            line: window.snapshot.line
            clock: window.snapshot.clock
            faulted: window.snapshot.emergency_brake

            // Which train the window shows, right after the badges. The
            // header's open middle is reserved for advertisements.
            statusExtras: SelectField {
                objectName: "trainSelector"
                Layout.preferredWidth: 240
                Layout.fillWidth: false
                label: qsTr("Train")
                labelVisible: false
                enabled: fleet.count > 0
                model: fleet.count > 0
                    ? fleet.trains
                    : [{"id": "", "label": qsTr("No trains")}]
                textRole: "label"
                valueRole: "id"
                currentIndex: Math.max(fleet.selectedIndex, 0)
                onCommitted: function (value) {
                    fleet.selectTrain(value);
                }
            }
        }

        // This fills the fixed reference canvas; the canvas transform
        // scales the complete design uniformly with the window. The
        // test UI is a separate window in its own process (test_ui.py).
        MainView {
            Layout.fillWidth: true
            trainModel: window.trainModel
            Layout.fillHeight: true
        }
    }

    // The Train Controller's announcement, shown to passengers as a
    // popup each time a new one arrives. It is not modal, so the
    // passenger emergency brake stays in reach; an empty announcement
    // closes it. A panel in the design canvas rather than a Popup: a
    // Popup draws in the window overlay, which the canvas scale does
    // not reach, so in a small window it outgrew the rest of the UI.
    Rectangle {
        id: announcementPopup

        readonly property string message: window.snapshot.announcement
        property bool opened: false

        function open() { opened = true; }
        function close() { opened = false; }

        objectName: "announcementPopup"
        visible: opened
        z: 1
        // Over the left column, clear of the emergency brake button.
        x: (window.canvas.width / 2 - width) / 2
        y: theme.control_h_lg * 3
        width: 560
        // Never taller than the canvas: a long announcement scrolls,
        // and Dismiss stays in sight.
        height: Math.min(announcementContent.implicitHeight
                + 2 * theme.space_5,
            window.canvas.height - y - theme.space_5)
        color: theme.bg_surface
        border.color: theme.border_strong
        border.width: 1
        radius: theme.radius_lg

        onMessageChanged: {
            if (message !== "")
                open();
            else
                close();
        }

        // Clicks on the panel stay on it, off the card underneath.
        MouseArea {
            anchors.fill: parent
        }

        Shortcut {
            sequence: "Esc"
            enabled: announcementPopup.visible
            onActivated: announcementPopup.close()
        }

        ColumnLayout {
            id: announcementContent

            anchors.fill: parent
            anchors.margins: theme.space_5
            spacing: theme.space_4

            Text {
                Layout.fillWidth: true
                text: qsTr("Announcement")
                color: theme.text_primary
                font.family: theme.ui_family
                font.pixelSize: theme.size_h3
                font.weight: theme.weight_bold
            }

            ScrollView {
                id: announcementScroll

                objectName: "announcementScroll"
                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.preferredHeight: announcementText.implicitHeight
                clip: true
                contentWidth: availableWidth

                Text {
                    id: announcementText

                    objectName: "announcementText"
                    width: announcementScroll.availableWidth
                    text: announcementPopup.message
                    textFormat: Text.PlainText
                    wrapMode: Text.Wrap
                    color: theme.text_primary
                    font.family: theme.ui_family
                    font.pixelSize: theme.size_body
                }
            }

            AppButton {
                Layout.alignment: Qt.AlignRight
                variant: "ghost"
                text: qsTr("Dismiss")
                onClicked: announcementPopup.close()
            }
        }
    }
}
