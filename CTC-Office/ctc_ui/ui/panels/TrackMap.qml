// Track map: every block of the Red and Green lines, drawn from
// ctc_ui/track_map.py (TrackMapModel). Each block is its own shape,
// styled by its state.
//
// Lines take their line-identity color (style guide 4.6) and also
// differ by pattern and label, never by color alone: Green is solid, Red
// is dashed. A block's state (6.4) overrides its line color: closed
// --warning, failure --danger. Occupancy is shown as trains: a small
// --info car on the track at the train's position, labeled with its ID.
pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Shapes

Item {
    id: root

    // A TrackMapModel; nothing is drawn while it is null.
    property var model: null
    // 0 = both lines, 1 = Red only, 2 = Green only.
    property int lineFilter: 0
    // "Line:block" -> closed | failure; absent means no state.
    property var blockStates: ({})
    // Trains placed by TrackMapModel.placeTrains:
    // [{ train, line, x, y, angle }]. An empty ID is an occupied block
    // with no train reported on it.
    property var trains: []
    // "Line:crossing" -> inactive | active, as reported.
    property var crossingStates: ({})

    readonly property real mapWidth: model ? model.mapWidth : 1
    readonly property real mapHeight: model ? model.mapHeight : 1
    readonly property real fitScale: Math.min(width / mapWidth,
                                              height / mapHeight)

    function lineShown(line) {
        return root.lineFilter === 0
            || (root.lineFilter === 1 && line === "Red")
            || (root.lineFilter === 2 && line === "Green");
    }

    function lineColor(line) {
        return line === "Red" ? theme.line_red : theme.line_green;
    }

    function stateColor(state, line) {
        return state === "closed" ? theme.warning
            : state === "failure" ? theme.danger
            : root.lineColor(line);
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
        // A block state from blockStates, or "" when free.
        property string blockState: ""

        readonly property bool hasState: blockState !== ""
        // A block with a state is drawn solid, three times as heavy and
        // with round ends, on a --bg-surface halo that parts it from the
        // track around it: a closed block's --warning is close in hue to
        // the line colors, so width and the halo carry it, not hue alone.
        readonly property real stateWidth: lineWidth * 3
        readonly property real haloWidth: stateWidth + 6

        anchors.fill: parent
        preferredRendererType: Shape.CurveRenderer
        visible: root.lineShown(line)

        ShapePath {
            strokeColor: stroke.hasState ? theme.bg_surface : "transparent"
            strokeWidth: stroke.hasState ? stroke.haloWidth : 0
            fillColor: "transparent"
            capStyle: ShapePath.RoundCap
            joinStyle: ShapePath.RoundJoin

            PathPolyline { path: root.toPoints(stroke.points) }
        }

        ShapePath {
            strokeColor: root.stateColor(stroke.blockState, stroke.line)
            strokeWidth: stroke.hasState ? stroke.stateWidth : stroke.lineWidth
            strokeStyle: stroke.line === "Red" && !stroke.hasState
                ? ShapePath.DashLine : ShapePath.SolidLine
            dashPattern: [2.5, 1.5]
            fillColor: "transparent"
            capStyle: stroke.hasState ? ShapePath.RoundCap
                : ShapePath.FlatCap
            joinStyle: ShapePath.RoundJoin

            PathPolyline { path: root.toPoints(stroke.points) }
        }
    }

    // A light-rail car seen from the side: an --info body with window
    // cutouts and a --bg-surface outline that parts it from the track.
    // Round at both ends, since the map does not know which way it runs.
    component TrainCar: Rectangle {
        // Map units; the map renders at about 0.7x, so this is roughly
        // 31 x 13 px on screen.
        width: 44
        height: 18
        radius: 6
        color: theme.info
        border.color: theme.bg_surface
        border.width: 2

        Row {
            anchors.centerIn: parent
            spacing: 2.5

            Repeater {
                model: 5

                delegate: Rectangle {
                    width: 5.5
                    height: 6
                    radius: 1.5
                    color: theme.bg_surface
                }
            }
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
                blockState: root.blockStates[modelData.line + ":"
                    + modelData.blockId] || ""
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

        // Railway crossings: squares with an X, filled --warning while
        // the crossing is active.
        Repeater {
            model: root.model ? root.model.crossings : []

            delegate: Item {
                id: crossing
                required property var modelData
                readonly property bool active: root.crossingStates[
                    modelData.line + ":" + modelData.blockId] === "active"
                visible: root.lineShown(modelData.line)
                x: modelData.x - 8
                y: modelData.y - 8
                width: 16
                height: 16

                Rectangle {
                    anchors.fill: parent
                    color: crossing.active ? theme.warning : theme.bg_surface
                    border.color: crossing.active
                        ? theme.warning : theme.text_secondary
                    border.width: 1.5
                }

                Shape {
                    anchors.fill: parent
                    preferredRendererType: Shape.CurveRenderer

                    ShapePath {
                        strokeColor: crossing.active
                            ? theme.text_inverse : theme.text_secondary
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
                color: root.lineColor(modelData.line)
                font.family: theme.mono_family
                // The map renders at roughly 0.75x in the Track view,
                // so H3 keeps letters above the 12 px minimum.
                font.pixelSize: theme.size_h3
                font.weight: theme.weight_bold
            }
        }

        // Trains, on top of everything else.
        Repeater {
            model: root.trains

            delegate: Item {
                id: placed

                required property var modelData

                visible: root.lineShown(modelData.line)
                x: modelData.x
                y: modelData.y
                objectName: "train-" + modelData.train

                TrainCar {
                    x: -width / 2
                    y: -height / 2
                    rotation: placed.modelData.angle
                }

                // The ID stays upright, above the car.
                Rectangle {
                    visible: placed.modelData.train !== ""
                    x: -width / 2
                    y: -height - 14
                    width: idText.implicitWidth + 8
                    height: idText.implicitHeight + 2
                    radius: 3
                    color: theme.bg_surface
                    border.color: theme.info
                    border.width: 1

                    Text {
                        id: idText
                        anchors.centerIn: parent
                        text: placed.modelData.train
                        color: theme.text_primary
                        font.family: theme.mono_family
                        // The map renders at about 0.7x; H3, like the
                        // section letters, keeps the ID above 12 px.
                        font.pixelSize: theme.size_h3
                        font.weight: theme.weight_bold
                    }
                }
            }
        }
    }
}
