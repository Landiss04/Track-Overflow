// One signal light's aspect, as a marker: a shape per aspect, so it
// reads without colour (style guide 2, 8), filled with the aspect's
// colour and outlined in --aspect-outline.
//
//   RED          square
//   YELLOW       triangle, point up
//   GREEN        circle
//   SUPER_GREEN  diamond
//   ""           not reported: a hollow circle with "?"
//
// `size` is the marker's box; on the map it is given in map units that
// come to the same screen pixels at any zoom (TrackMap.qml).
import QtQuick
import QtQuick.Shapes

Item {
    id: root

    // RED | YELLOW | GREEN | SUPER_GREEN, or "" when not reported.
    property string aspect: ""
    property real size: 16
    // Outline width, in the same units as `size`.
    property real outline: 1.5

    readonly property bool reported: aspect === "RED"
        || aspect === "YELLOW" || aspect === "GREEN"
        || aspect === "SUPER_GREEN"
    readonly property color fill: aspect === "RED" ? theme.aspect_red
        : aspect === "YELLOW" ? theme.aspect_yellow
        : aspect === "GREEN" ? theme.aspect_green
        : aspect === "SUPER_GREEN" ? theme.aspect_super_green
        : theme.bg_surface

    width: size
    height: size

    // Square, circle and the unreported hollow circle.
    Rectangle {
        objectName: root.aspect === "RED" ? "square"
            : root.reported ? "circle" : "hollow"
        visible: root.aspect === "RED" || root.aspect === "GREEN"
            || !root.reported
        // The square is drawn a little smaller than the box, so it
        // weighs the same as the circle beside it.
        anchors.centerIn: parent
        width: root.aspect === "RED" ? root.size * 0.86 : root.size
        height: width
        radius: root.aspect === "RED" ? root.size * 0.08 : width / 2
        color: root.fill
        border.color: root.reported ? theme.aspect_outline
            : theme.text_secondary
        border.width: root.outline
        antialiasing: true
    }

    // Diamond: a square turned 45 degrees, its corners on the box.
    Rectangle {
        objectName: "diamond"
        visible: root.aspect === "SUPER_GREEN"
        anchors.centerIn: parent
        width: root.size / Math.SQRT2
        height: width
        rotation: 45
        color: root.fill
        border.color: theme.aspect_outline
        border.width: root.outline
        antialiasing: true
    }

    // Triangle, point up.
    Shape {
        objectName: "triangle"
        visible: root.aspect === "YELLOW"
        anchors.fill: parent
        preferredRendererType: Shape.CurveRenderer

        ShapePath {
            fillColor: root.fill
            strokeColor: theme.aspect_outline
            strokeWidth: root.outline
            joinStyle: ShapePath.MiterJoin
            startX: root.size / 2
            startY: root.outline / 2
            PathLine { x: root.size - root.outline / 2; y: root.size * 0.93 }
            PathLine { x: root.outline / 2; y: root.size * 0.93 }
            PathLine { x: root.size / 2; y: root.outline / 2 }
        }
    }

    Text {
        visible: !root.reported
        anchors.centerIn: parent
        text: "?"
        color: theme.text_secondary
        font.family: theme.ui_family
        // 12 px on screen at the marker's 16 px (style guide floor).
        font.pixelSize: root.size * 0.75
        font.weight: theme.weight_bold
    }
}
