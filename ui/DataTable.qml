// Small operator tables, style guide 6.6. The host supplies scrolling.
// ponytail: Repeater suits small tables; use TableView for virtualized datasets.
import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

ColumnLayout {
    id: root

    // Columns: { key, label, numeric?, mono?, width? }; rows: objects keyed by column.
    property var columns: []
    property var rows: []
    property int currentIndex: -1
    signal rowActivated(int index, var row)
    spacing: 0
    opacity: enabled ? 1.0 : 0.42

    RowLayout {
        Layout.fillWidth: true
        spacing: 0
        Repeater {
            model: root.columns
            delegate: FieldLabel {
                required property var modelData
                Layout.fillWidth: true
                Layout.preferredWidth: modelData.width || 100
                padding: theme.space_3
                text: modelData.label.toUpperCase()
                horizontalAlignment: modelData.numeric ? Text.AlignRight : Text.AlignLeft
            }
        }
    }
    Rectangle {
        Layout.fillWidth: true
        implicitHeight: 1
        color: theme.border_strong
    }
    Repeater {
        model: root.rows
        delegate: Button {
            id: rowControl
            required property int index
            required property var modelData
            Layout.fillWidth: true
            implicitHeight: cells.implicitHeight
            padding: 0
            hoverEnabled: true
            focusPolicy: Qt.StrongFocus
            Accessible.name: JSON.stringify(modelData)
            background: Rectangle {
                color: rowControl.hovered || rowControl.index === root.currentIndex
                    ? theme.accent_subtle : theme.bg_surface
                border.width: rowControl.visualFocus ? 2 : 0
                border.color: theme.focus_ring
                Rectangle {
                    anchors.bottom: parent.bottom
                    width: parent.width
                    height: 1
                    color: theme.border
                }
            }
            contentItem: RowLayout {
                id: cells
                spacing: 0
                Repeater {
                    model: root.columns
                    delegate: Text {
                        required property var modelData
                        readonly property var value: rowControl.modelData[modelData.key]
                        Layout.fillWidth: true
                        Layout.preferredWidth: modelData.width || 100
                        padding: theme.space_3
                        text: value === undefined || value === null || value === ""
                            ? "\u2014" : String(value)
                        textFormat: Text.PlainText
                        elide: Text.ElideRight
                        color: theme.text_primary
                        font.family: modelData.numeric || modelData.mono
                            ? theme.mono_family : theme.ui_family
                        font.pixelSize: theme.size_small
                        horizontalAlignment: modelData.numeric ? Text.AlignRight : Text.AlignLeft
                    }
                }
            }
            onClicked: root.rowActivated(index, modelData)
        }
    }
}
