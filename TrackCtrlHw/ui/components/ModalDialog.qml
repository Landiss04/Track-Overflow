import QtQuick
import QtQuick.Layouts

import "../../../ui" as Shared

// Modal window, drawn inside the scaled canvas so it scales with the window
// (a Popup lives in the window overlay, outside ScaledWindow's transform).
// Style guide 5: dialogs carry a 1 px --border-strong edge and --radius-lg.
// The scrim is --text-primary at low alpha, not a new colour.
//
// Usage: anchors.fill the canvas, put the body in `content` and any footer
// buttons in `footer`, then call open(). Escape and the close button call
// close().
Item {
    id: root

    property string title: ""
    property string meta: ""
    property real dialogWidth: 640
    property real maxHeight: parent ? parent.height - 2 * theme.space_6 : 600
    default property alias content: body.data
    property alias footer: footerRow.data
    property alias footerNote: note.text

    signal closed()

    function open() {
        visible = true;
        frame.forceActiveFocus();
    }

    function close() {
        if (!visible)
            return;
        visible = false;
        closed();
    }

    visible: false
    z: 100

    Rectangle {
        anchors.fill: parent
        color: Qt.alpha(theme.text_primary, 0.28)

        // Swallow clicks so nothing under the dialog reacts.
        MouseArea {
            anchors.fill: parent
            acceptedButtons: Qt.AllButtons
            hoverEnabled: true
            onWheel: function (wheel) { wheel.accepted = true; }
        }
    }

    Rectangle {
        id: frame

        anchors.centerIn: parent
        width: root.dialogWidth
        height: Math.min(root.maxHeight, layout.implicitHeight)
        radius: theme.radius_lg
        color: theme.bg_surface
        border.width: 1
        border.color: theme.border_strong
        clip: true
        focus: true

        Keys.onEscapePressed: root.close()

        ColumnLayout {
            id: layout
            anchors.fill: parent
            anchors.margins: 1
            spacing: 0

            Rectangle {
                Layout.fillWidth: true
                implicitHeight: theme.control_h_lg + theme.space_1
                color: theme.bg_raised
                radius: theme.radius_lg

                RowLayout {
                    anchors.fill: parent
                    anchors.leftMargin: theme.space_4
                    anchors.rightMargin: theme.space_3
                    spacing: theme.space_3

                    Text {
                        Layout.fillWidth: true
                        text: root.title
                        textFormat: Text.PlainText
                        color: theme.text_primary
                        font.family: theme.ui_family
                        font.pixelSize: theme.size_h3
                        font.weight: theme.weight_bold
                        elide: Text.ElideRight
                    }

                    Text {
                        visible: root.meta !== ""
                        text: root.meta
                        textFormat: Text.PlainText
                        color: theme.text_muted
                        font.family: theme.mono_family
                        font.pixelSize: theme.size_small
                    }

                    IconButton {
                        size: "sm"
                        glyph: "\u00d7"
                        tip: qsTr("Close")
                        onClicked: root.close()
                    }
                }

                Rectangle {
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.bottom: parent.bottom
                    height: 1
                    color: theme.border
                }
            }

            Flickable {
                id: scroller

                Layout.fillWidth: true
                Layout.fillHeight: true
                implicitHeight: body.implicitHeight + 2 * theme.space_4
                contentWidth: width
                contentHeight: body.implicitHeight + 2 * theme.space_4
                clip: true
                boundsBehavior: Flickable.StopAtBounds

                ColumnLayout {
                    id: body
                    x: theme.space_4
                    y: theme.space_4
                    width: scroller.width - 2 * theme.space_4
                    spacing: theme.space_4
                }
            }

            Rectangle {
                Layout.fillWidth: true
                implicitHeight: 1
                color: theme.border
                visible: footerRow.children.length > 0
            }

            RowLayout {
                Layout.fillWidth: true
                Layout.margins: theme.space_4
                spacing: theme.space_3
                visible: footerRow.children.length > 0

                Shared.HelperText {
                    id: note
                    Layout.fillWidth: true
                    visible: text !== ""
                }

                Item {
                    Layout.fillWidth: true
                    visible: note.text === ""
                }

                RowLayout {
                    id: footerRow
                    spacing: theme.space_3
                }
            }
        }
    }
}
