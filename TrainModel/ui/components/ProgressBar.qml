import QtQuick

// Progress indicator: sunken track with an accent fill. `fraction` is 0..1.
Item {
    id: root

    property real fraction: 0.0

    implicitWidth: 0
    implicitHeight: theme.progress_bar_height

    Rectangle {
        anchors.fill: parent
        color: theme.bg_sunken
        border.width: 1
        border.color: theme.border
        radius: theme.radius_sm
    }

    Rectangle {
        anchors.left: parent.left
        anchors.top: parent.top
        anchors.bottom: parent.bottom
        width: Math.max(0, Math.min(1, root.fraction)) * (parent.width - 2)
        color: theme.accent
        radius: theme.radius_sm
    }
}
