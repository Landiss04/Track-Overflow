// Proportion bar for a value against a ceiling. Colour is never the only
// signal, so the numeric readout above it carries the same information.
import QtQuick

Rectangle {
    id: root

    property real value: 0
    property real ceiling: 1
    readonly property real fraction: ceiling <= 0
        ? 0 : Math.max(0, Math.min(1, value / ceiling))

    implicitHeight: theme.space_2
    radius: theme.radius_sm
    color: theme.bg_sunken
    border.color: theme.border
    border.width: 1

    Rectangle {
        anchors.left: parent.left
        anchors.top: parent.top
        anchors.bottom: parent.bottom
        anchors.margins: 1
        width: Math.max(0, (parent.width - 2) * root.fraction)
        radius: theme.radius_sm
        // Accent identifies a primary action or selection, not a generic
        // measurement. The numeric readout above supplies the value.
        color: theme.border_strong
    }
}
