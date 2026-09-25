import QtQuick

// Label/value row (Style Guide §6.6 rows): small label left, mono value
// right, 1 px bottom rule. Read-only — no click target anywhere in the item.
Item {
    id: root

    property string label: ""
    property string value: ""
    property bool lastRow: false   // suppresses the bottom rule on the final row

    implicitWidth: 0
    implicitHeight: theme.table_row_height

    Text {
        id: labelText
        anchors.left: parent.left
        anchors.verticalCenter: parent.verticalCenter
        text: root.label
        font.family: theme.ui_family
        font.pixelSize: theme.font_small
        color: theme.text_secondary
    }

    Text {
        id: valueText
        anchors.right: parent.right
        anchors.verticalCenter: parent.verticalCenter
        text: root.value
        font.family: theme.mono_family
        font.pixelSize: theme.font_body
        color: theme.text_primary
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
