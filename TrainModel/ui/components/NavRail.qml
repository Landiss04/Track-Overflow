import QtQuick

// Collapsed navigation rail (Figma export): 44 px items with 18 px stub
// glyphs drawn as stroked outlines — the mockup's placeholders are
// rectangles with per-item border insets, reproduced here from
// refrence-docs/TestUIwireframe.css. The active item gets a sunken tint
// and a darker stroke; both states keep their text-free glyph per the
// "color is never the only signal" rule (the rail is a stub — labels are
// not part of the design).
Item {
    id: root

    property int activeIndex: 4   // item 5, per the mockup

    signal activated(int index)

    // Per-glyph top/bottom inset as a fraction of the glyph box; left and
    // right stay at the default inset. Values are the Figma border insets.
    readonly property var glyphInsets: [
        [0.2778, 0.2778],
        [0.1667, 0.1667],
        [0.1667, 0.1667],
        [0.2222, 0.2222],
        [0.1667, 0.1667],
        [0.1667, 0.2222],
        [0.1667, 0.1667],
        [0.2222, 0.2222]
    ]
    readonly property real defaultInset: 0.1667

    Rectangle {
        anchors.fill: parent
        color: theme.bg_raised
    }

    Column {
        anchors.fill: parent

        Repeater {
            model: root.glyphInsets.length

        delegate: Item {
            width: parent.width
            height: theme.nav_item_height

            readonly property bool active: index === root.activeIndex

            // Active-item tint (mockup #EFEFEF → --bg-sunken).
            Rectangle {
                anchors.fill: parent
                visible: active
                color: theme.bg_sunken
            }

            Canvas {
                anchors.centerIn: parent
                width: theme.icon_size
                height: theme.icon_size
                onPaint: {
                    var ctx = getContext("2d")
                    ctx.clearRect(0, 0, width, height)
                    var insets = root.glyphInsets[index]
                    var x = width * root.defaultInset
                    var y = width * insets[0]
                    var w = width - 2 * x
                    var h = width - width * (insets[0] + insets[1])
                    ctx.strokeStyle = active ? theme.text_primary
                                             : theme.text_muted
                    ctx.lineWidth = theme.stroke_width
                    ctx.strokeRect(x, y, w, h)
                }
            }

            // 1 px vertical rule between items (Figma "VerticalBorder").
            Rectangle {
                visible: index > 0
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.top: parent.top
                height: 1
                color: theme.border
            }

            MouseArea {
                anchors.fill: parent
                cursorShape: Qt.PointingHandCursor
                onClicked: root.activated(index)
            }
        }
        }
    }
}
