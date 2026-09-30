// Toggle group, style guide 5 (--radius-pill) and 6.1. The selected segment
// carries the accent fill; the label is always present.
import QtQuick
import QtQuick.Layouts

Rectangle {
    id: root

    property var options: []
    property int currentIndex: 0
    signal activated(int index)

    // Segments split the track evenly, sized to fit the widest label.
    property real widestSegment: 0
    readonly property real segmentWidth: options.length > 0
        ? row.width / options.length : 0

    implicitHeight: theme.control_h_md
    implicitWidth: widestSegment * options.length + 2 * theme.space_1
    radius: theme.radius_pill
    color: theme.bg_sunken
    border.color: theme.border_strong
    border.width: 1
    opacity: enabled ? 1.0 : 0.42

    RowLayout {
        id: row
        anchors.fill: parent
        anchors.margins: theme.space_1
        spacing: 0

        Repeater {
            model: root.options

            delegate: AppButton {
                id: segment
                required property int index
                required property string modelData
                readonly property bool selected: index === root.currentIndex
                Layout.preferredWidth: root.segmentWidth
                Layout.fillHeight: true
                // The track already dims when disabled; do not dim twice.
                opacity: 1.0
                size: "small"
                implicitHeight: theme.control_h_sm
                text: modelData
                variant: selected ? "primary" : "ghost"
                Accessible.name: modelData
                onClicked: root.activated(index)
                onImplicitWidthChanged: root.widestSegment = Math.max(
                    root.widestSegment, implicitWidth)
                Component.onCompleted: root.widestSegment = Math.max(
                    root.widestSegment, implicitWidth)

                // Pill-shaped fill so the selected side matches the track.
                background: Rectangle {
                    radius: theme.radius_pill
                    color: !segment.enabled ? segment.restFill
                        : segment.pressed ? segment.pressFill
                        : segment.hovered ? segment.hoverFill : segment.restFill

                    Rectangle {
                        anchors.fill: parent
                        anchors.margins: -4
                        visible: segment.visualFocus
                        color: "transparent"
                        radius: theme.radius_pill
                        border.width: 2
                        border.color: theme.focus_ring
                    }
                }
            }
        }
    }
}
