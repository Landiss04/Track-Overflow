import QtQuick

// Secondary button (Style Guide §6.1): raised fill, primary text, 1 px
// strong border, radius-md, mandatory states. `subLabel` renders the tall
// two-line form used by the failure-mode rows; when set the item grows to
// the sublabeled height and the status line uses the Small token in muted
// text so it cannot be mistaken for a second action.
Item {
    id: root

    property string text: ""
    property string subLabel: ""
    property bool enabled_: true         // underscored: `enabled` is reserved by Item

    signal clicked

    readonly property bool hasSub: root.subLabel.length > 0
    implicitWidth: Math.max(160,
                            mainLabel.implicitWidth + 2 * theme.space_4)
    implicitHeight: hasSub ? theme.sublabeled_button_height : theme.control_h_md

    Rectangle {
        id: well
        anchors.fill: parent
        radius: theme.radius_md
        color: theme.bg_raised
        border.width: 1
        border.color: theme.border_strong
        opacity: root.enabled_ ? 1.0 : theme.disabled_opacity
    }

    Column {
        id: labels
        anchors.centerIn: parent
        spacing: theme.space_1
        width: Math.min(parent.width - 2 * theme.space_3,
                        mainLabel.implicitWidth)

        Text {
            id: mainLabel
            width: parent.width
            horizontalAlignment: Text.AlignHCenter
            text: root.text
            elide: Text.ElideRight
            font.family: theme.ui_family
            font.pixelSize: theme.font_body
            font.weight: Font.Bold
            color: theme.text_primary
        }

        Text {
            width: parent.width
            visible: root.hasSub
            text: root.subLabel
            elide: Text.ElideRight
            font.family: theme.ui_family
            font.pixelSize: theme.font_small
            color: theme.text_muted
        }
    }

    // Focus ring (2 px, 2 px offset), keyboard focus only.
    Rectangle {
        visible: pressArea.activeFocus
        anchors.fill: parent
        anchors.margins: -theme.focus_ring_offset
        color: "transparent"
        border.width: theme.focus_ring_width
        border.color: theme.focus_ring
        radius: theme.radius_md
    }

    MouseArea {
        id: pressArea
        anchors.fill: parent
        hoverEnabled: true
        enabled: root.enabled_
        cursorShape: Qt.PointingHandCursor
        onClicked: root.clicked()
        Keys.onReturnPressed: root.clicked()
        Keys.onEnterPressed: root.clicked()
    }
}
