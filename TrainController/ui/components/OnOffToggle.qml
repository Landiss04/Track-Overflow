// Two-state OFF / ON switch sized for the cab. A selected ON carries the
// accent fill, or --danger for a braking control; a selected OFF is a plain
// raised tile, so colour always means "engaged". Both keep their text label
// (style guide 2 and 8: colour is never the only signal).
import QtQuick
import QtQuick.Layouts

Rectangle {
    id: root

    property bool checked: false
    property string offLabel: "OFF"
    property string onLabel: "ON"
    property bool dangerWhenOn: false
    signal toggled(bool on)

    implicitHeight: theme.control_h_lg
    radius: theme.radius_md
    color: theme.bg_sunken
    border.color: theme.border_strong
    border.width: 1
    opacity: enabled ? 1.0 : 0.42

    RowLayout {
        anchors.fill: parent
        anchors.margins: theme.space_1
        spacing: theme.space_1

        Repeater {
            model: [false, true]

            delegate: Rectangle {
                id: half

                required property bool modelData

                readonly property bool selected: modelData === root.checked
                readonly property bool danger: modelData && root.dangerWhenOn
                readonly property bool colored: selected && modelData

                Layout.fillWidth: true
                Layout.fillHeight: true
                radius: theme.radius_md - theme.space_1 / 2
                color: colored ? (danger ? theme.danger : theme.accent)
                    : selected ? theme.bg_raised
                    : area.containsMouse ? theme.accent_subtle : "transparent"
                border.width: selected && !modelData ? 1 : 0
                border.color: theme.border_strong

                Text {
                    anchors.centerIn: parent
                    text: half.modelData ? root.onLabel : root.offLabel
                    color: !half.selected ? theme.text_muted
                        : !half.colored ? theme.text_primary
                        : half.danger ? theme.text_inverse : theme.on_accent
                    font.family: theme.ui_family
                    font.pixelSize: theme.size_h3
                    font.weight: theme.weight_bold
                    font.letterSpacing: theme.safety_letter_spacing
                }

                MouseArea {
                    id: area

                    anchors.fill: parent
                    enabled: root.enabled
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: {
                        if (!half.selected)
                            root.toggled(half.modelData);
                    }
                }
            }
        }
    }
}
