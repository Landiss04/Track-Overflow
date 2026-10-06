// Train Model application window.
import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import QtQuick.Window
import "../../ui"

ApplicationWindow {
    id: window

    readonly property var snapshot: trainModel.snapshot
    readonly property int referenceWidth: 1440
    readonly property int referenceHeight: 900
    readonly property real canvasScale: Math.min(
        width / referenceWidth, height / referenceHeight)

    visible: true
    width: referenceWidth
    height: referenceHeight
    minimumWidth: 720
    minimumHeight: 450
    title: qsTr("Train Model")
    color: theme.bg_app

    // The design is laid out once at the reference size and scaled as a
    // whole. On Windows, main.py keeps the window at 16:10 while it is
    // resized; any other shape (maximized, snapped, fullscreen, Linux) is
    // letterboxed around the centered canvas.
    Item {
        id: designCanvas

        width: window.referenceWidth
        height: window.referenceHeight
        x: (window.width - width * window.canvasScale) / 2
        y: (window.height - height * window.canvasScale) / 2
        transform: Scale {
            origin.x: 0
            origin.y: 0
            xScale: window.canvasScale
            yScale: window.canvasScale
        }

        ColumnLayout {
            anchors.fill: parent
            spacing: 0

            ModuleHeader {
                Layout.fillWidth: true
                moduleName: qsTr("Train Model")
                instance: window.snapshot.train_id
                // Running while steps arrive, from the test UI or, once
                // integrated, the central harness.
                mode: trainModel.running ? qsTr("Running") : qsTr("Paused")
                line: window.snapshot.line
                clock: window.snapshot.clock
                faulted: window.snapshot.emergency_brake
            }

            // This fills the fixed reference canvas; the canvas transform
            // scales the complete design uniformly with the window. The
            // test UI is a separate window in its own process (test_ui.py).
            MainView {
                Layout.fillWidth: true
                Layout.fillHeight: true
            }
        }

        // The Train Controller's announcement, shown to passengers as a
        // popup each time a new one arrives. It is not modal, so the
        // passenger emergency brake stays in reach; an empty announcement
        // closes it.
        Popup {
            id: announcementPopup

            readonly property string message: window.snapshot.announcement

            objectName: "announcementPopup"
            parent: designCanvas
            // Over the left column, clear of the emergency brake button.
            x: (designCanvas.width / 2 - width) / 2
            y: theme.control_h_lg * 3
            width: 560
            padding: theme.space_5
            modal: false
            closePolicy: Popup.CloseOnEscape

            onMessageChanged: {
                if (message !== "")
                    open();
                else
                    close();
            }

            background: Rectangle {
                color: theme.bg_surface
                border.color: theme.border_strong
                border.width: 1
                radius: theme.radius_lg
            }

            contentItem: ColumnLayout {
                spacing: theme.space_4

                Text {
                    Layout.fillWidth: true
                    text: qsTr("Announcement")
                    color: theme.text_primary
                    font.family: theme.ui_family
                    font.pixelSize: theme.size_h3
                    font.weight: theme.weight_bold
                }

                Text {
                    objectName: "announcementText"
                    Layout.fillWidth: true
                    text: announcementPopup.message
                    textFormat: Text.PlainText
                    wrapMode: Text.Wrap
                    color: theme.text_primary
                    font.family: theme.ui_family
                    font.pixelSize: theme.size_body
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
}
