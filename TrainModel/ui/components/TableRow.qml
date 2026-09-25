import QtQuick

// Data-table row (Style Guide §6.6): 13 px text, cell padding, 1 px bottom
// rule. `cells` is the value list; `monoColumns` marks which columns render
// in the mono face (IDs and numerics). Empty cells render as an em dash.
Item {
    id: root

    property var cells: []
    property var fractions: []
    property var monoColumns: []
    property bool lastRow: false    // suppresses the bottom rule on the final row

    implicitWidth: 0
    implicitHeight: theme.table_row_height

    Row {
        anchors.fill: parent
        spacing: 0

        Repeater {
            model: root.cells
            delegate: Item {
                width: (root.fractions ? (root.fractions[index] || 1 / root.cells.length)
                                       : 1 / root.cells.length) * parent.width
                height: parent.height

                Text {
                    anchors.left: parent.left
                    anchors.leftMargin: index === 0 ? 0 : theme.space_3
                    anchors.verticalCenter: parent.verticalCenter
                    text: modelData.length > 0 ? modelData : "—"
                    elide: Text.ElideRight
                    font.family: (root.monoColumns[index] || false)
                                 ? theme.mono_family : theme.ui_family
                    font.pixelSize: theme.font_small
                    color: theme.text_primary
                }
            }
        }
    }

    Rectangle {
        visible: !root.lastRow
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        height: 1
        color: theme.border
    }
}
