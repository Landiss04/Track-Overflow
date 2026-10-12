// Track map: every block of the Red and Green lines, drawn from
// ctc_ui/track_map.py (TrackMapModel). Each block is its own shape,
// styled by its state.
//
// Lines take their line-identity color (style guide 4.6) and also
// differ by pattern and label, never by color alone: Green is solid, Red
// is dashed. A block's state (6.4) overrides its line color: closed
// --warning, failure --danger. Occupancy is shown as trains: a small
// --info car on the track at the train's position, labeled with its ID.
//
// To tell blocks apart: a tick in the line color marks every block
// boundary; zoomed in to 2x or more, every block shows its number; and
// hovering a block highlights it and shows a card with what it is.
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
    // The selected train's route, CtcHost.routeStates: "Line:block" ->
    // authority | beyond. Drawn as an --accent band under the track.
    property var routeStates: ({})
    // The selected train's ID; its tag is outlined in --accent.
    property string selectedTrain: ""

    // Block numbers show from this zoom on; below it they would crowd.
    readonly property real numbersFromZoom: 2
    // The block under the pointer, "Line:block", or "".
    property string hoveredKey: ""
    // Its entry from the model, or null. Looked up in Python: looping
    // over model.blocks in QML re-reads the whole list on every element.
    readonly property var hoveredBlock: {
        if (!root.model || root.hoveredKey === "")
            return null;
        const block = root.model.blockInfo(root.hoveredKey);
        return block.blockId !== undefined ? block : null;
    }
    // Where the pointer is, in map units.
    property point hoverPoint: Qt.point(0, 0)

    function updateHover(position) {
        if (!root.model) {
            root.hoveredKey = "";
            return;
        }
        // Within about 10 px on screen of the track.
        const found = root.model.blockAt(position.x, position.y,
                                         10 / root.mapScale,
                                         root.lineFilter);
        root.hoveredKey = found.line ? found.line + ":" + found.blockId : "";
        root.hoverPoint = position;
    }

    // Who is in a block: train IDs, "" for occupancy with no train.
    function occupants(key) {
        const found = [];
        for (const train of root.trains) {
            if (train.line + ":" + train.block === key)
                found.push(train.train);
        }
        return found;
    }

    function stateText(key) {
        const state = root.blockStates[key] || "";
        if (state === "failure")
            return qsTr("Failure");
        if (state === "closed")
            return qsTr("Closed");
        const inBlock = root.occupants(key);
        if (inBlock.length === 0)
            return qsTr("Free");
        const named = inBlock.filter(id => id !== "");
        return named.length > 0
            ? qsTr("Occupied by %1").arg(named.join(", "))
            : qsTr("Occupied");
    }

    readonly property real mapWidth: model ? model.mapWidth : 1
    readonly property real mapHeight: model ? model.mapHeight : 1
    // Room above the drawing, in map units, so the ID tag of a train on
    // the topmost track (about 40 units above its car) is not clipped.
    readonly property real topHeadroom: 32
    readonly property real canvasHeight: mapHeight + topHeadroom
    readonly property real fitScale: Math.min(width / mapWidth,
                                              height / canvasHeight)
    // Zoom over the fitted map: 1 shows it whole; above 1 it can be
    // dragged to pan.
    property real zoom: 1
    readonly property real minZoom: 1
    readonly property real maxZoom: 4
    readonly property real mapScale: fitScale * zoom

    // Zoom by a factor, keeping the point at the centre of the view.
    function zoomBy(factor) {
        const next = Math.max(root.minZoom,
                              Math.min(root.maxZoom, root.zoom * factor));
        if (next === root.zoom)
            return;
        const centreX = (view.contentX + view.width / 2 - canvas.x)
            / root.mapScale;
        const centreY = (view.contentY + view.height / 2 - canvas.y)
            / root.mapScale;
        root.zoom = next;
        view.contentX = Math.max(0, Math.min(
            view.contentWidth - view.width,
            canvas.x + centreX * root.mapScale - view.width / 2));
        view.contentY = Math.max(0, Math.min(
            view.contentHeight - view.height,
            canvas.y + centreY * root.mapScale - view.height / 2));
    }

    // Back to the whole map.
    function fit() {
        root.zoom = 1;
        view.contentX = 0;
        view.contentY = 0;
    }

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

    Flickable {
        id: view

        anchors.fill: parent
        clip: true
        contentWidth: Math.max(width, root.mapWidth * root.mapScale)
        contentHeight: Math.max(height, root.canvasHeight * root.mapScale)
        // Panning only makes sense once zoomed in.
        interactive: root.zoom > root.minZoom
        boundsBehavior: Flickable.StopAtBounds

        Item {
            id: canvas

            width: root.mapWidth
            height: root.canvasHeight
            x: (view.contentWidth - width * root.mapScale) / 2
            y: (view.contentHeight - height * root.mapScale) / 2
            visible: root.model !== null
            // Map coordinates start below the headroom.
            transform: [
                Translate { y: root.topHeadroom },
                Scale {
                    xScale: root.mapScale
                    yScale: root.mapScale
                }
            ]

            HoverHandler {
                onPointChanged: root.updateHover(point.position)
                onHoveredChanged: {
                    if (!hovered)
                        root.hoveredKey = "";
                }
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

            // The selected train's route (--accent, style guide 4.3), under
            // the track so a block's own state still shows on top. Within
            // authority the band is solid; beyond it, thinner and dashed,
            // so the two differ by pattern as well as weight. Only the
            // route's blocks get a shape.
            Repeater {
                model: root.model
                    ? root.model.blocksIn(Object.keys(root.routeStates)) : []

                delegate: Shape {
                    id: band

                    required property var modelData
                    readonly property string part: root.routeStates[
                        modelData.line + ":" + modelData.blockId] || ""

                    anchors.fill: parent
                    preferredRendererType: Shape.CurveRenderer
                    visible: part !== "" && root.lineShown(modelData.line)

                    ShapePath {
                        strokeColor: theme.accent
                        strokeWidth: band.part === "authority" ? 14 : 9
                        strokeStyle: band.part === "authority"
                            ? ShapePath.SolidLine : ShapePath.DashLine
                        dashPattern: [1.2, 0.8]
                        fillColor: "transparent"
                        capStyle: band.part === "authority"
                            ? ShapePath.RoundCap : ShapePath.FlatCap
                        joinStyle: ShapePath.RoundJoin

                        PathPolyline { path: root.toPoints(band.modelData.points) }
                    }
                }
            }

            // The hovered block: a soft halo under the track.
            Shape {
                id: hoverHalo
                readonly property var block: root.hoveredBlock
                anchors.fill: parent
                preferredRendererType: Shape.CurveRenderer
                visible: block !== null
                opacity: 0.3

                ShapePath {
                    strokeColor: theme.text_secondary
                    strokeWidth: 16
                    fillColor: "transparent"
                    capStyle: ShapePath.RoundCap
                    joinStyle: ShapePath.RoundJoin

                    PathPolyline {
                        path: hoverHalo.block
                            ? root.toPoints(hoverHalo.block.points) : []
                    }
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

            // Block boundaries: a short tick across the track, in the line
            // color, where each block starts.
            Repeater {
                model: root.model ? root.model.blocks : []

                delegate: Rectangle {
                    required property var modelData
                    visible: root.lineShown(modelData.line)
                    width: 1.5
                    height: 11
                    x: modelData.tick[0] - width / 2
                    y: modelData.tick[1] - height / 2
                    rotation: modelData.tick[2]
                    color: root.lineColor(modelData.line)
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

            // Block numbers beside the track, once zoomed in far enough to
            // read them. Sized in screen pixels, so 12 px at any zoom; a
            // block shorter than 18 px on screen is left unnumbered until
            // zoomed further (hovering still names it).
            Repeater {
                model: root.zoom >= root.numbersFromZoom && root.model
                    ? root.model.blocks : []

                delegate: Text {
                    required property var modelData
                    // Clear of the route band (7 map units each side of
                    // the track), plus half the text across the track.
                    readonly property real offset: 9
                        + (Math.abs(modelData.normal[0]) * width
                           + Math.abs(modelData.normal[1]) * height) / 2
                    visible: root.lineShown(modelData.line)
                        && modelData.drawnLength * root.mapScale >= 18
                    x: modelData.mid[0] + modelData.normal[0] * offset
                        - width / 2
                    y: modelData.mid[1] + modelData.normal[1] * offset
                        - height / 2
                    text: modelData.blockId
                    color: root.lineColor(modelData.line)
                    font.family: theme.mono_family
                    font.pixelSize: 12 / root.mapScale
                    font.weight: theme.weight_bold
                }
            }

            // A badge for every closed or failed block, beside the track
            // and above the trains (style guide 6.4 fill and label): on a
            // short block a train next to it would hide the block's own
            // state color. Sized in screen pixels.
            Repeater {
                model: root.model
                    ? root.model.blocksIn(Object.keys(root.blockStates)) : []

                delegate: Rectangle {
                    id: badge
                    required property var modelData
                    readonly property string state: root.blockStates[
                        modelData.line + ":" + modelData.blockId] || ""
                    // Map units per screen pixel.
                    readonly property real px: 1 / root.mapScale
                    // Clear of the track and the route band, plus half
                    // the badge across the track.
                    readonly property real offset: 12 * px
                        + (Math.abs(modelData.normal[0]) * width
                           + Math.abs(modelData.normal[1]) * height) / 2

                    visible: root.lineShown(modelData.line)
                    z: 2
                    width: badgeText.implicitWidth + 8 * px
                    height: badgeText.implicitHeight + 2 * px
                    radius: 3 * px
                    x: modelData.mid[0] + modelData.normal[0] * offset
                        - width / 2
                    y: modelData.mid[1] + modelData.normal[1] * offset
                        - height / 2
                    color: state === "failure" ? theme.danger : theme.warning
                    border.color: theme.bg_surface
                    border.width: px

                    Text {
                        id: badgeText
                        anchors.centerIn: parent
                        text: badge.modelData.blockId + " · "
                            + (badge.state === "failure" ? qsTr("FAILURE")
                                : qsTr("CLOSED"))
                        color: theme.text_inverse
                        font.family: theme.mono_family
                        font.pixelSize: 12 * badge.px
                        font.weight: theme.weight_bold
                    }
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

                    // The ID stays upright, above the car. The selected
                    // train's tag is outlined in --accent.
                    Rectangle {
                        readonly property bool selected:
                            placed.modelData.train === root.selectedTrain
                        visible: placed.modelData.train !== ""
                        x: -width / 2
                        y: -height - 14
                        width: idText.implicitWidth + 8
                        height: idText.implicitHeight + 2
                        radius: 3
                        color: selected ? theme.accent_subtle : theme.bg_surface
                        border.color: selected ? theme.accent : theme.info
                        border.width: selected ? 2.5 : 1

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

    // What the hovered block is. Kept inside the map, beside the pointer.
    Rectangle {
        id: card

        readonly property var block: root.hoveredBlock
        readonly property point anchor: {
            // Re-place when the map zooms or pans.
            view.contentX; view.contentY; root.mapScale;
            return canvas.mapToItem(root, root.hoverPoint.x,
                                    root.hoverPoint.y);
        }

        visible: block !== null
        z: 10
        x: Math.max(0, Math.min(root.width - width, anchor.x + 14))
        y: Math.max(0, Math.min(root.height - height, anchor.y + 14))
        width: details.implicitWidth + 2 * theme.space_3
        height: details.implicitHeight + 2 * theme.space_2
        radius: theme.radius_md
        color: theme.bg_surface
        border.color: theme.border_strong
        border.width: 1

        Column {
            id: details
            x: theme.space_3
            y: theme.space_2
            spacing: 2

            Text {
                text: card.block ? qsTr("%1 line · Block %2")
                    .arg(card.block.line).arg(card.block.blockId) : ""
                color: theme.text_primary
                font.family: theme.ui_family
                font.pixelSize: theme.size_body
                font.weight: theme.weight_bold
            }
            Text {
                text: card.block ? qsTr("Section %1 · %2 mph · %3 ft")
                    .arg(card.block.section).arg(card.block.speedLimitMph)
                    .arg(card.block.lengthFt) : ""
                color: theme.text_secondary
                font.family: theme.ui_family
                font.pixelSize: theme.size_small
            }
            Text {
                // null: no station; "": a station with no name.
                visible: card.block !== null
                    && card.block.station !== null
                    && card.block.station !== undefined
                text: card.block && card.block.station
                    ? qsTr("Station: %1").arg(card.block.station)
                    : qsTr("Station")
                color: theme.text_secondary
                font.family: theme.ui_family
                font.pixelSize: theme.size_small
            }
            Text {
                text: root.hoveredKey !== ""
                    ? root.stateText(root.hoveredKey) : ""
                color: theme.text_primary
                font.family: theme.ui_family
                font.pixelSize: theme.size_small
            }
            Text {
                readonly property string part:
                    root.routeStates[root.hoveredKey] || ""
                visible: part !== ""
                text: part === "authority"
                    ? qsTr("On %1's route, within authority")
                        .arg(root.selectedTrain)
                    : qsTr("On %1's route, beyond authority")
                        .arg(root.selectedTrain)
                color: theme.accent
                font.family: theme.ui_family
                font.pixelSize: theme.size_small
            }
        }
    }
}
