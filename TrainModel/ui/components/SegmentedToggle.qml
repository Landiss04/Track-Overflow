import QtQuick

// Two-segment toggle group (Style Guide §5: toggle groups use radius-pill).
// `options` is a two-item array; `selected` is the active option string.
// Only the selected segment is accented — the text label always states the
// state, per the "color is never the only signal" rule (§2).
Item {
    id: root

    property var options: ["TRUE", "FALSE"]
    property string selected: ""
    property bool enabled_: true      // underscored: `enabled` is reserved by Item

    signal changed(string option)

    implicitWidth: theme.toggle_group_width
    implicitHeight: theme.control_h_sm

    Rectangle {
        anchors.fill: parent
        color: theme.bg_raised
        border.width: 1
        border.color: theme.border_strong
        radius: theme.radius_pill
        opacity: root.enabled_ ? 1.0 : theme.disabled_opacity
    }

    Row {
        anchors.fill: parent
        anchors.leftMargin: 1
        anchors.rightMargin: 1
        spacing: 0

        Repeater {
            model: root.options
            delegate: Item {
                width: parent.width / 2
                height: parent.height - 2
                y: 1

                Rectangle {
                    anchors.fill: parent
                    visible: modelData === root.selected
                    color: theme.accent
                    radius: theme.radius_pill
                }

                Text {
                    anchors.centerIn: parent
                    text: modelData
                    font.family: theme.ui_family
                    font.pixelSize: theme.font_small
                    font.weight: Font.Bold
                    color: modelData === root.selected
                           ? theme.on_accent : theme.text_secondary
                }

                // Focus ring (2 px, 2 px offset), keyboard focus only.
                Rectangle {
                    visible: segPress.activeFocus
                    anchors.fill: parent
                    anchors.margins: -theme.focus_ring_offset
                    color: "transparent"
                    border.width: theme.focus_ring_width
                    border.color: theme.focus_ring
                    radius: theme.radius_pill
                }

                MouseArea {
                    id: segPress
                    anchors.fill: parent
                    enabled: root.enabled_
                    cursorShape: Qt.PointingHandCursor
                    onClicked: {
                        if (modelData !== root.selected)
                            root.changed(modelData)
                    }
                    Keys.onReturnPressed: {
                        if (modelData !== root.selected)
                            root.changed(modelData)
                    }
                }
            }
        }
    }

}
