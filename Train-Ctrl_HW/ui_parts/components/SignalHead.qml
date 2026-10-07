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

    // Semantic tokens (guide 4.4). Green and super green share a
    // colour; the ring and the panel's words tell them apart.
    readonly property var lamps: [theme.danger, theme.warning,
                                  theme.success, theme.success]
    // Full spacing: a 5 px ring outside each lamp (every slot reserves
    // it), 8 px between lamps, 12 px inside the housing. When a notice
    // above leaves too little height for that, the ring, gap and
    // padding shrink with the lamp instead, so four lamps always fit
    // inside the housing rather than spilling out of it.
    readonly property real fullRing: 5
    readonly property real minLamp: 8
    readonly property bool roomy: (height - 2 * theme.space_3
        - 3 * theme.space_2) / 4 - 2 * fullRing >= minLamp
    readonly property real fitLamp: height / (4 * (1 + 2 * 0.15)
        + 3 * 0.2 + 2 * 0.25)
    readonly property real ring: roomy ? fullRing
        : Math.min(fullRing, 0.15 * fitLamp)
    readonly property real gap: roomy ? theme.space_2
        : Math.min(theme.space_2, 0.2 * fitLamp)
    readonly property real pad: roomy ? theme.space_3
        : Math.min(theme.space_3, 0.25 * fitLamp)
    readonly property real lampSize: Math.max(0, Math.min(
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
