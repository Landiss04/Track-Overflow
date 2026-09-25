import QtQuick

// Data-table header (Style Guide §6.6): Label-token columns in muted text
// with a 1 px --border-strong bottom rule. `columns` is the label list;
// `fractions` are the relative column widths (they should sum to ~1).
Item {
    id: root

    property var columns: []
    property var fractions: []

    implicitWidth: 0
    implicitHeight: theme.table_row_height

    Rectangle {
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        height: 1
        color: theme.border_strong
    }

    Row {
        anchors.fill: parent
        spacing: 0

        Repeater {
            model: root.columns
            delegate: Item {
                width: (root.fractions[index] || 1 / root.columns.length)
                       * parent.width
                height: parent.height

                Text {
                    anchors.left: parent.left
                    anchors.leftMargin: index === 0 ? 0 : theme.space_3
                    anchors.verticalCenter: parent.verticalCenter
                    text: modelData
                    elide: Text.ElideRight
                    font.family: theme.ui_family
                    font.pixelSize: theme.font_label
                    font.weight: Font.Bold
                    font.letterSpacing: theme.label_tracking_em * theme.font_label
                    color: theme.text_muted
                }
            }
        }
    }
}
