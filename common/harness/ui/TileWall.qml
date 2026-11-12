// Every window on one screen, for projector demonstrations: the harness
// first, then each module. Each tile is a recent image of that window,
// saved by the process that owns it. Selecting
// a tile brings that window up full screen, and Escape in it returns it
// to normal.
//
// A plain window rather than a ScaledWindow: the wall is a harness tool,
// not a module UI, and a 16:10 canvas letterboxed on a 16:9 screen would
// give up a sixth of the width the tiles need.
import QtQuick
import QtQuick.Window
import "../../../ui" as Shared

Window {
    id: wall
    objectName: "tileWall"
    title: "Track Overflow — Tiled view"
    color: theme.bg_app
    visible: false
    // Not kept above the harness window, which can be a tile too.
    transientParent: null
    width: 1440
    height: 900

    // The harness window, which its tile shows full screen.
    required property var harnessWindow
    // How often the tiles ask for new images while the wall is shown.
    // Tune on the projector machine.
    property int refreshIntervalMs: 500
    // Changes on every request, so each Image reloads its file.
    property int frame: 0

    readonly property var tiles: [{
        name: "harness",
        label: "Central Harness",
        state: backend.snapshot.state ?? "",
        variant: backend.snapshot.state === "RUNNING" ? "ok" : "warning",
        can_show: true,
        snapshot_url: backend.snapshot.harness_snapshot_url ?? ""
    }].concat(backend.modules)
    readonly property int gap: theme.space_4
    readonly property int stripHeight: theme.control_h_sm + 2 * theme.space_2
    readonly property real snapshotAspect: 16 / 10
    // The column count that gives the largest tiles; set a number here
    // to force one.
    property int columns: bestColumns()
    readonly property real tileWidth: tileWidthFor(columns)

    // Widest 16:10 tile, label strip included, that fits `count` columns.
    function tileWidthFor(count) {
        const rows = Math.ceil(tiles.length / count)
        const cellWidth = (area.width - (count - 1) * gap) / count
        const cellHeight = (area.height - (rows - 1) * gap) / rows
        return Math.max(0, Math.min(
            cellWidth, (cellHeight - stripHeight) * snapshotAspect))
    }

    // On a tie, the count that leaves no empty cell.
    function bestColumns() {
        let best = 1
        for (let count = 2; count <= tiles.length; ++count) {
            const width = tileWidthFor(count)
            const bestWidth = tileWidthFor(best)
            if (width > bestWidth || (width === bestWidth
                    && tiles.length % count === 0))
                best = count
        }
        return best
    }

    Timer {
        interval: wall.refreshIntervalMs
        running: wall.visible
        repeat: true
        triggeredOnStart: true
        onTriggered: {
            backend.request_snapshots()
            wall.frame++
        }
    }

    Shared.HelperText {
        id: hint
        x: theme.space_5
        y: theme.space_5
        text: "Select a tile to show that window full screen. "
            + "Press Esc there to come back."
    }

    Item {
        id: area
        anchors.fill: parent
        anchors.margins: theme.space_5
        anchors.topMargin: hint.y + hint.height + theme.space_4

        Grid {
            anchors.centerIn: parent
            columns: wall.columns
            spacing: wall.gap

            Repeater {
                model: wall.tiles.length
                delegate: Rectangle {
                    id: tile
                    required property int index
                    readonly property var modelData: wall.tiles[index] ?? ({})
                    readonly property bool live: modelData.can_show === true
                        && modelData.snapshot_url !== ""
                    function open() {
                        if (modelData.name === "harness") {
                            wall.harnessWindow.showFullScreen()
                            wall.harnessWindow.raise()
                            wall.harnessWindow.requestActivate()
                        } else {
                            backend.show_full_screen(modelData.name)
                        }
                    }
                    objectName: "tile-" + modelData.name
                    width: wall.tileWidth
                    height: wall.stripHeight + width / wall.snapshotAspect
                    color: theme.bg_surface
                    radius: theme.radius_md
                    clip: true
                    border.color: activeFocus ? theme.focus_ring : theme.border
                    border.width: activeFocus ? 2 : 1
                    activeFocusOnTab: true
                    Accessible.role: Accessible.Button
                    Accessible.name: "Show " + modelData.label
                        + " full screen"
                    Keys.onReturnPressed: open()
                    Keys.onSpacePressed: open()

                    Text {
                        anchors.left: parent.left
                        anchors.right: badge.left
                        anchors.leftMargin: theme.space_3
                        anchors.rightMargin: theme.space_2
                        height: wall.stripHeight
                        verticalAlignment: Text.AlignVCenter
                        text: modelData.label ?? ""
                        textFormat: Text.PlainText
                        color: theme.text_primary
                        font.family: theme.ui_family
                        font.pixelSize: theme.size_body
                        font.weight: theme.weight_bold
                        elide: Text.ElideRight
                    }
                    Shared.StatusBadge {
                        id: badge
                        anchors.right: parent.right
                        anchors.rightMargin: theme.space_2
                        y: theme.space_2
                        label: modelData.state ?? ""
                        variant: modelData.variant ?? "idle"
                    }
                    Image {
                        id: image
                        objectName: "tileImage"
                        y: wall.stripHeight
                        width: parent.width
                        height: parent.height - y
                        visible: tile.live
                        cache: false
                        fillMode: Image.PreserveAspectFit
                        source: tile.live
                            ? modelData.snapshot_url + "?" + wall.frame : ""
                    }
                    Shared.EmptyState {
                        anchors.centerIn: image
                        visible: !tile.live
                        heading: "No image yet"
                        body: modelData.can_show
                            ? "Waiting for the window."
                            : "The module is not running."
                    }

                    MouseArea {
                        anchors.fill: parent
                        enabled: modelData.can_show === true
                        cursorShape: enabled ? Qt.PointingHandCursor
                            : Qt.ArrowCursor
                        onClicked: tile.open()
                    }
                }
            }
        }
    }
}
