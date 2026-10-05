// Four lamps, one per aspect, in the order a real head carries them.
// Position identifies the state and the lit lamp is a solid fill, so
// it reads without colour; the panel repeats it in words (guide 2, 8).
//
// The lamps are sized from the space the panel actually gives this
// item, including the ring super green carries and the padding inside
// the body, so nothing ever overflows the housing.
import QtQuick
import "../../../ui"

Item {
    id: root

    // 0 red, 1 yellow, 2 green, 3 super green.
    property int aspectIndex: 0

    readonly property var lamps: [theme.signal_red, theme.signal_yellow,
                                  theme.signal_green, theme.signal_super]
    readonly property real pad: theme.space_3
    readonly property real gap: theme.space_2
    // The ring sits 5 px outside its lamp, so every slot reserves it.
    readonly property real ring: 5
    readonly property real lampSize: Math.max(8, Math.min(
        (height - 2 * pad - 3 * gap) / 4 - 2 * ring,
        width - 2 * theme.space_4 - 2 * ring))

    implicitWidth: 92
    implicitHeight: 150

    Rectangle {
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.verticalCenter: parent.verticalCenter
        width: root.lampSize + 2 * root.ring + 2 * theme.space_4
        height: parent.height
        color: theme.bg_sunken
        border.color: theme.border_strong
        border.width: 1
        radius: theme.radius_md

        Column {
            anchors.centerIn: parent
            spacing: root.gap

            Repeater {
                model: 4

                delegate: Item {
                    id: lamp
                    required property int index
                    readonly property bool lit: index === root.aspectIndex

                    width: root.lampSize + 2 * root.ring
                    height: root.lampSize + 2 * root.ring

                    // Super green carries a ring as well as a colour,
                    // so it cannot be read as plain green.
                    Rectangle {
                        anchors.centerIn: parent
                        visible: lamp.index === 3
                        width: root.lampSize + 2 * root.ring
                        height: width
                        radius: width / 2
                        color: "transparent"
                        border.width: 2
                        border.color: lamp.lit ? root.lamps[3]
                                               : theme.border_strong
                    }

                    Rectangle {
                        anchors.centerIn: parent
                        width: root.lampSize
                        height: width
                        radius: width / 2
                        color: lamp.lit ? root.lamps[lamp.index]
                                        : theme.bg_surface
                        border.width: lamp.lit ? 2 : 1
                        border.color: lamp.lit ? root.lamps[lamp.index]
                                               : theme.border_strong
                    }
                }
            }
        }
    }
}
