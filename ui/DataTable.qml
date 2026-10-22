// Small operator tables, style guide 6.6. The host supplies scrolling.
// ponytail: Repeater suits small tables; use TableView for virtualized datasets.
<<<<<<< HEAD
// Rows are kept by index: a new rows array updates each row's cells in
// place, and rows are made or dropped only when the count changes. A
// Repeater over the array itself rebuilt every row on any change, which
// took up to a second for the Track Model's 150 blocks.
=======
>>>>>>> origin/Train_Ctrl_integration
import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

ColumnLayout {
    id: root

    // Columns: { key, label, numeric?, mono?, width? }; rows: objects keyed by column.
    property var columns: []
    property var rows: []
    property int currentIndex: -1
<<<<<<< HEAD
    // Optional: the Flickable (e.g. ScrollView.contentItem) this table is a
    // direct child of. When set, the header row stays pinned at the top of
    // the view while the rows scroll beneath it.
    property Flickable stickyFlickable: null
=======
>>>>>>> origin/Train_Ctrl_integration
    signal rowActivated(int index, var row)
    spacing: 0
    opacity: enabled ? 1.0 : 0.42

<<<<<<< HEAD
    Item {
        id: headerSlot
        Layout.fillWidth: true
        implicitHeight: headerBar.implicitHeight
        z: 1 // Above the row buttons so the pinned header covers them

        Rectangle {
            id: headerBar
            width: parent.width
            implicitHeight: headerRow.implicitHeight + 1
            height: implicitHeight
            color: theme.bg_surface
            // Slide down with the scroll, but never out of the table.
            y: root.stickyFlickable === null ? 0
                : Math.max(0, Math.min(
                    root.stickyFlickable.contentY - root.y,
                    root.height - headerSlot.height))

            RowLayout {
                id: headerRow
                width: parent.width
                spacing: 0
                Repeater {
                    model: root.columns
                    delegate: FieldLabel {
                        required property var modelData
                        Layout.fillWidth: true
                        Layout.preferredWidth: modelData.width || 100
                        padding: theme.space_3
                        text: (modelData.label || "").toUpperCase()
                        horizontalAlignment: modelData.numeric ? Text.AlignRight : Text.AlignLeft
                    }
                }
            }
            Rectangle {
                anchors.bottom: parent.bottom
                width: parent.width
                height: 1
                color: theme.border_strong
            }
        }
    }
    Repeater {
        model: root.rows ? root.rows.length : 0
        delegate: Button {
            id: rowControl
            required property int index
            // Empty for a moment while a shorter array replaces a
            // longer one, until the count catches up.
            readonly property var modelData: root.rows[index] ?? ({})
            Layout.fillWidth: true
            implicitHeight: cells.implicitHeight
            padding: 0
            horizontalPadding: 0 // Basic binds it to padding + 2, offsetting cells from the header
=======
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
>>>>>>> origin/Train_Ctrl_integration
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
