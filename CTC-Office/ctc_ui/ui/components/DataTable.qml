// Data table, style guide 6.6. Header in the Label token over a 1 px
// --border-strong rule; 13 px rows over 1 px --border rules. Numeric
// columns are mono and right-aligned; empty values render as an em dash.
pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts

ColumnLayout {
    id: root

    // Each column: { title, key, width (omit to fill), numeric, mono }.
    property var columns: []
    // Each row: an object keyed by the column keys.
    property var rows: []
    property string emptyText: qsTr("No data")

    spacing: 0

    function cellText(row, key) {
        const value = row[key];
        return value === undefined || value === null || value === ""
            ? "—" : String(value);
    }

    RowLayout {
        Layout.fillWidth: true
        Layout.bottomMargin: theme.space_2
        spacing: theme.space_3

        Repeater {
            model: root.columns

            delegate: FieldLabel {
                required property var modelData

                Layout.fillWidth: !modelData.width
                Layout.preferredWidth: modelData.width || -1
                text: modelData.title.toUpperCase()
                horizontalAlignment: modelData.numeric
                    ? Text.AlignRight : Text.AlignLeft
                elide: Text.ElideRight
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

        delegate: ColumnLayout {
            id: rowItem

            required property var modelData

            Layout.fillWidth: true
            spacing: 0

            RowLayout {
                Layout.fillWidth: true
                Layout.topMargin: theme.space_3
                Layout.bottomMargin: theme.space_3
                spacing: theme.space_3

                Repeater {
                    model: root.columns

                    delegate: Text {
                        id: cell

                        required property var modelData

                        Layout.fillWidth: !cell.modelData.width
                        Layout.preferredWidth: cell.modelData.width || -1
                        text: root.cellText(rowItem.modelData,
                            cell.modelData.key)
                        color: theme.text_primary
                        font.family: cell.modelData.numeric
                            || cell.modelData.mono
                            ? theme.mono_family : theme.ui_family
                        font.pixelSize: theme.size_small
                        horizontalAlignment: cell.modelData.numeric
                            ? Text.AlignRight : Text.AlignLeft
                        elide: Text.ElideRight
                    }
                }
            }

            Rectangle {
                Layout.fillWidth: true
                implicitHeight: 1
                color: theme.border
            }
        }
    }

    HelperText {
        Layout.fillWidth: true
        Layout.topMargin: theme.space_4
        visible: root.rows.length === 0
        text: root.emptyText
        horizontalAlignment: Text.AlignHCenter
    }
}
