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
            id: mainView

            Layout.fillWidth: true
            trainModel: window.trainModel
            Layout.fillHeight: true
        }
    }

    // The Train Controller's announcement, shown to passengers as a
    // popup each time a new one arrives. It is not modal, so the
    // passenger emergency brake stays in reach; an empty announcement
    // closes it, and so does the timeout. A panel in the design canvas
    // rather than a Popup: a Popup draws in the window overlay, which
    // the canvas scale does not reach, so in a small window it outgrew
    // the rest of the UI.
    Rectangle {
        id: announcementPopup

        readonly property string message: window.snapshot.announcement
        property bool opened: false
        // How long an announcement stays up before it closes itself.
        property int timeout: 30000
        // Shorter announcements read larger, stepping down the type
        // scale as the text grows.
        readonly property int textSize: message.length <= 40
            ? theme.size_display
            : message.length <= 100 ? theme.size_h1
            : message.length <= 200 ? theme.size_h2
            : message.length <= 400 ? theme.size_h3
            : theme.size_body
        // Its top edge, kept below the passenger emergency brake. Found
        // on each open: mapToItem is not a binding, and at startup the
        // layout has not placed the button yet.
        property real minY: 0

        function open() {
            const brake = mainView.passengerBrake;
            minY = brake.mapToItem(window.canvas, 0, brake.height).y
                + theme.space_5;
            opened = true;
            closeTimer.restart();
        }
        function close() {
            opened = false;
            closeTimer.stop();
        }

        objectName: "announcementPopup"
        visible: opened
        z: 1
        // Three quarters of the canvas wide and centered on it, but
        // never over the emergency brake button.
        width: window.canvas.width * 0.75
        x: (window.canvas.width - width) / 2
        y: Math.max(minY, (window.canvas.height - height) / 2)
        // Never taller than the canvas: a long announcement scrolls,
        // and Dismiss stays in sight.
        height: Math.min(announcementContent.implicitHeight
                + 2 * theme.space_5,
            window.canvas.height - minY - theme.space_5)
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

        Timer {
            id: closeTimer

            interval: announcementPopup.timeout
            onTriggered: announcementPopup.close()
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

            // As tall as the Dismiss row, so the text sits at the
            // panel's vertical center.
            Item {
                Layout.preferredHeight: dismissButton.implicitHeight
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
                    horizontalAlignment: Text.AlignHCenter
                    color: theme.text_primary
                    font.family: theme.ui_family
                    font.pixelSize: announcementPopup.textSize
                    // Bold on the heading steps of the scale, regular
                    // at body size, as the type scale gives them.
                    font.weight: announcementPopup.textSize > theme.size_body
                        ? theme.weight_bold : theme.weight_regular
                }
            }

            AppButton {
                id: dismissButton

                Layout.alignment: Qt.AlignRight
                variant: "ghost"
                text: qsTr("Dismiss")
                onClicked: announcementPopup.close()
            }
        }
    }
}
