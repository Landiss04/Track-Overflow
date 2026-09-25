import QtQuick

// Status badge (Style Guide §6.3): pill, 7 px dot, 12 px uppercase bold
// label, semantic border + matching -bg fill. Text is always present; the
// dot never carries meaning alone.
Item {
    id: badge

    property string text: ""
    property string variant: "idle"   // ok | warning | fault | info | idle

    readonly property color fg:
        variant === "ok" ? theme.success :
        variant === "warning" ? theme.warning :
        variant === "fault" ? theme.danger :
        variant === "info" ? theme.info :
        theme.text_muted
    readonly property color bg:
        variant === "ok" ? theme.success_bg :
        variant === "warning" ? theme.warning_bg :
        variant === "fault" ? theme.danger_bg :
        variant === "info" ? theme.info_bg :
        Qt.transparent

    implicitWidth: theme.space_2 + dot.width + theme.space_2 +
                   label.implicitWidth + theme.space_2
    implicitHeight: Math.max(theme.control_h_sm,
                             label.implicitHeight + 2 * theme.space_1)

    Rectangle {
        anchors.fill: parent
        radius: theme.radius_pill
        color: badge.bg
        border.width: 1
        border.color: badge.fg
    }

    Rectangle {
        id: dot
        anchors.left: parent.left
        anchors.leftMargin: theme.space_2
        anchors.verticalCenter: parent.verticalCenter
        width: theme.badge_dot_size
        height: theme.badge_dot_size
        radius: width / 2
        color: badge.fg
    }

    Text {
        id: label
        anchors.left: dot.right
        anchors.leftMargin: theme.space_2
        anchors.right: parent.right
        anchors.rightMargin: theme.space_2
        anchors.verticalCenter: parent.verticalCenter
        text: badge.text
        font.family: theme.ui_family
        font.pixelSize: theme.badge_text_size
        font.weight: Font.Bold
        font.letterSpacing: theme.label_tracking_em * theme.badge_text_size
        color: badge.fg
    }
}
