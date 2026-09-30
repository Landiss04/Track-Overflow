// PLC source editor: line-number gutter, monospaced buffer, error
// underlines fed from the compiler.
//
// The editor is a plain TextArea rather than a rich code widget. The
// language is small enough that the useful signal is which lines the
// compiler objected to, so highlighting is applied to the gutter and
// the error strip instead of being painted into the text.
import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

Rectangle {
    id: root

    property alias text: editor.text
    property var errorLines: []
    property bool readOnly: false
    signal edited(string text)

    color: theme.editor_bg

    RowLayout {
        anchors.fill: parent
        spacing: 0

        // Gutter. Scrolls with the buffer and marks the lines the
        // compiler rejected.
        Rectangle {
            Layout.fillHeight: true
            implicitWidth: 46
            color: theme.editor_gutter_bg

            Rectangle {
                anchors.right: parent.right
                anchors.top: parent.top
                anchors.bottom: parent.bottom
                implicitWidth: 1
                color: theme.border
            }

            Column {
                id: gutter
                width: parent.width
                y: editor.topPadding - scroll.contentItem.contentY

                Repeater {
                    model: editor.lineCount

                    delegate: Item {
                        required property int index

                        readonly property bool failed:
                            root.errorLines.indexOf(index + 1) !== -1

                        width: gutter.width
                        height: theme.editor_line_height

                        Rectangle {
                            anchors.fill: parent
                            color: theme.danger_bg
                            visible: parent.failed
                        }

                        Text {
                            anchors.right: parent.right
                            anchors.rightMargin: theme.space_2
                            anchors.verticalCenter: parent.verticalCenter
                            text: parent.failed
                                ? "▶ " + (index + 1) : index + 1
                            color: parent.failed
                                ? theme.danger : theme.text_muted
                            font.family: theme.mono_family
                            font.pixelSize: theme.size_label
                        }
                    }
                }
            }
        }

        ScrollView {
            id: scroll
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true

            TextArea {
                id: editor

                readOnly: root.readOnly
                selectByMouse: true
                persistentSelection: true
                wrapMode: TextArea.NoWrap
                topPadding: theme.space_2
                leftPadding: theme.space_3
                color: theme.text_primary
                selectionColor: theme.accent_subtle
                selectedTextColor: theme.text_primary
                font.family: theme.mono_family
                font.pixelSize: theme.size_code
                // A fixed line box keeps the gutter numbers aligned
                // with the rows they label.
                renderType: Text.NativeRendering

                background: Rectangle { color: "transparent" }

                onTextChanged: root.edited(text)
            }
        }
    }

    // Read-only history buffers say so rather than silently swallowing
    // keystrokes.
    Rectangle {
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.margins: theme.space_2
        visible: root.readOnly
        implicitWidth: readOnlyLabel.implicitWidth + 2 * theme.space_2
        implicitHeight: theme.control_h_sm
        radius: theme.radius_sm
        color: theme.warning_bg
        border.color: theme.warning
        border.width: 1

        Text {
            id: readOnlyLabel
            anchors.centerIn: parent
            text: qsTr("READ ONLY")
            color: theme.warning
            font.family: theme.ui_family
            font.pixelSize: theme.size_label
            font.weight: theme.weight_bold
            font.letterSpacing: theme.label_letter_spacing
        }
    }
}
