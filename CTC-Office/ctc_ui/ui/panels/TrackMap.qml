// Track map: every block of the Red and Green lines, drawn from
// ctc_ui/track_map.py (TrackMapModel). Each block is its own shape so
// per-block state (occupancy, closures) can style it later.
//
// The style guide has no line-color tokens yet, so the lines use neutral
// tokens and are told apart by pattern and label, never by color alone:
// Green is solid, Red is dashed. Swap in the line tokens once they are
// added to the style guide.
pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Shapes

Item {
    id: root

    // A TrackMapModel; nothing is drawn while it is null.
    property var model: null
    // 0 = both lines, 1 = Red only, 2 = Green only.
    property int lineFilter: 0

    readonly property real mapWidth: model ? model.mapWidth : 1
    readonly property real mapHeight: model ? model.mapHeight : 1
    readonly property real fitScale: Math.min(width / mapWidth,
                                              height / mapHeight)

    function lineShown(line) {
        return root.lineFilter === 0
            || (root.lineFilter === 1 && line === "Red")
            || (root.lineFilter === 2 && line === "Green");
    }

    function toPoints(flat) {
        const points = [];
        for (let i = 0; i + 1 < flat.length; i += 2)
            points.push(Qt.point(flat[i], flat[i + 1]));
        return points;
    }

    component TrackStroke: Shape {
        id: stroke

        property string line: ""
        property var points: []
        property real lineWidth: 4

        anchors.fill: parent
        preferredRendererType: Shape.CurveRenderer
        visible: root.lineShown(line)

        ShapePath {
            strokeColor: stroke.line === "Red"
                ? theme.text_primary : theme.text_secondary
            strokeWidth: stroke.lineWidth
            strokeStyle: stroke.line === "Red"
                ? ShapePath.DashLine : ShapePath.SolidLine
            dashPattern: [2.5, 1.5]
            fillColor: "transparent"
            capStyle: ShapePath.FlatCap
            joinStyle: ShapePath.RoundJoin

            PathPolyline { path: root.toPoints(stroke.points) }
        }
    }

    Item {
        id: canvas

        width: root.mapWidth
        height: root.mapHeight
        x: (root.width - width * root.fitScale) / 2
        y: (root.height - height * root.fitScale) / 2
        visible: root.model !== null
        transform: Scale {
            xScale: root.fitScale
            yScale: root.fitScale
        }

        // Yard connections (no blocks).
        Repeater {
            model: root.model ? root.model.spurs : []

            delegate: TrackStroke {
                required property var modelData
                line: modelData.line
                points: modelData.points
                lineWidth: 2
            }
        }

        // One shape per block.
        Repeater {
            model: root.model ? root.model.blocks : []

            delegate: TrackStroke {
                required property var modelData
                objectName: "block-" + modelData.line + "-"
                    + modelData.blockId
                line: modelData.line
                points: modelData.points
            }
        }

        // Yard.
        Rectangle {
            readonly property var rect: root.model ? root.model.yard
                : [0, 0, 0, 0]
            x: rect[0]
            y: rect[1]
            width: rect[2]
            height: rect[3]
            color: theme.bg_sunken
            border.color: theme.text_primary
            border.width: 2

            Text {
                anchors.centerIn: parent
                text: qsTr("YARD")
                color: theme.text_primary
                font.family: theme.ui_family
                font.pixelSize: theme.size_small
                font.weight: theme.weight_bold
            }
        }

        // Stations: hollow squares.
        Repeater {
            model: root.model ? root.model.stations : []

            delegate: Rectangle {
                required property var modelData
                visible: root.lineShown(modelData.line)
                x: modelData.x - 5
                y: modelData.y - 5
                width: 10
                height: 10
                color: theme.bg_surface
                border.color: theme.text_secondary
                border.width: 1.5
            }
        }

        // Railway crossings: squares with an X.
        Repeater {
            model: root.model ? root.model.crossings : []

            delegate: Item {
                id: crossing
                required property var modelData
                visible: root.lineShown(modelData.line)
                x: modelData.x - 8
                y: modelData.y - 8
                width: 16
                height: 16

                Rectangle {
                    anchors.fill: parent
                    color: theme.bg_surface
                    border.color: theme.text_secondary
                    border.width: 1.5
                }

                Shape {
                    anchors.fill: parent
                    preferredRendererType: Shape.CurveRenderer

                    ShapePath {
                        strokeColor: theme.text_secondary
                        strokeWidth: 1.5
                        fillColor: "transparent"
                        PathMove { x: 4; y: 4 }
                        PathLine { x: 12; y: 12 }
                        PathMove { x: 12; y: 4 }
                        PathLine { x: 4; y: 12 }
                    }
                }
            }
        }

        // Section letters.
        Repeater {
            model: root.model ? root.model.labels : []

            delegate: Text {
                required property var modelData
                visible: root.lineShown(modelData.line)
                x: modelData.x - width / 2
                y: modelData.y - height / 2
                text: modelData.text
                color: modelData.line === "Red"
                    ? theme.text_primary : theme.text_secondary
                font.family: theme.mono_family
                // The map renders at roughly 0.75x in the Track view,
                // so H3 keeps letters above the 12 px minimum.
                font.pixelSize: theme.size_h3
                font.weight: theme.weight_bold
            }
        }
    }
}
