// A figure in the mono face with a narrow decimal point. In a mono face
// the point takes a whole digit's width, so "20.0" reads as "20 . 0"
// beside "72"; here the point gets only its own width, from the UI face.
// A value with no point ("72", "--") is drawn as one plain text.
import QtQuick

Row {
    id: root

    property string text: ""
    property color color: theme.text_primary
    property int pixelSize: theme.size_body
    property int weight: theme.weight_bold

    readonly property int point: text.indexOf(".")

    spacing: 0

    Text {
        text: root.point < 0 ? root.text : root.text.slice(0, root.point)
        color: root.color
        font.family: theme.mono_family
        font.pixelSize: root.pixelSize
        font.weight: root.weight
    }

    Text {
        visible: root.point >= 0
        text: "."
        color: root.color
        font.family: theme.ui_family
        font.pixelSize: root.pixelSize
        font.weight: root.weight
    }

    Text {
        visible: root.point >= 0
        text: root.point < 0 ? "" : root.text.slice(root.point + 1)
        color: root.color
        font.family: theme.mono_family
        font.pixelSize: root.pixelSize
        font.weight: root.weight
    }
}
