// One name/value row in the watch and output panes.
//
// Aspect values carry their colour as well as their word, because a
// four-aspect signal is the one output where the programmer is reading
// for the aspect rather than for a boolean.
import QtQuick
import QtQuick.Layouts

RowLayout {
    id: root

    property string label: ""
    property string value: ""
    property string kind: "scalar"
    property bool mono: true

    readonly property color valueColor: kind !== "aspect" ? theme.text_primary
        : value === "RED" ? theme.aspect_red
        : value === "ORANGE" ? theme.aspect_orange
        : value === "SUPER GREEN" ? theme.aspect_super_green
        : theme.aspect_green

    spacing: theme.space_3

    Text {
        text: root.label
        color: theme.text_secondary
        font.family: theme.ui_family
        font.pixelSize: theme.size_small
        elide: Text.ElideRight
        Layout.fillWidth: true
    }

    Rectangle {
        visible: root.kind === "aspect"
        implicitWidth: 9
        implicitHeight: 9
        radius: 4.5
        color: root.valueColor
        Layout.alignment: Qt.AlignVCenter
    }

    Text {
        text: root.value
        color: root.valueColor
        font.family: root.mono ? theme.mono_family : theme.ui_family
        font.pixelSize: theme.size_small
        font.weight: theme.weight_bold
    }
}
