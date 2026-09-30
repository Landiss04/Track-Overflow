import QtQuick
import QtQuick.Controls.Basic

// Pill toggle group (--radius-pill, §5). The selected option carries the accent
// fill; the group is keyboard reachable and every option is labelled.
Rectangle {
    id: root

    property var options: []
    property int currentIndex: 0
    property string size: "md"

    signal activated(int index)

    readonly property int controlHeight: size === "sm" ? Theme.controlHSm : Theme.controlHMd

    implicitHeight: controlHeight
    implicitWidth: row.implicitWidth + 2 * inset
    radius: height / 2
    color: Theme.bgSunken
    border.width: 1
    border.color: Theme.borderStrong

    readonly property int inset: 3

    Row {
        id: row
        anchors.fill: parent
        anchors.margins: root.inset
        spacing: 0

        Repeater {
            model: root.options

            delegate: Button {
                id: option

                required property int index
                required property var modelData

                readonly property bool selected: index === root.currentIndex

                height: row.height
                leftPadding: Theme.space4
                rightPadding: Theme.space4
                topPadding: 0
                bottomPadding: 0
                hoverEnabled: true
                Accessible.name: modelData
                onClicked: {
                    root.currentIndex = index;
                    root.activated(index);
                }

                background: Rectangle {
                    radius: height / 2
                    color: option.selected ? Theme.accent : option.hovered ? Theme.accentSubtle : "transparent"

                    Rectangle {
                        anchors.fill: parent
                        anchors.margins: -2
                        visible: option.visualFocus
                        radius: parent.radius + 2
                        color: "transparent"
                        border.width: 2
                        border.color: Theme.focusRing
                    }
                }

                contentItem: Text {
                    text: option.modelData
                    color: option.selected ? Theme.inkOnAccent : Theme.textSecondary
                    font.family: Theme.uiFamily
                    font.pixelSize: Theme.sizeSmall
                    font.bold: true
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                }
            }
        }
    }
}
