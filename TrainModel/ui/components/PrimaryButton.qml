import QtQuick

// Filled action button (Style Guide §6.1). `variant` picks the fill family:
// "primary" (accent) or "danger" (emergency brake, per §7 safety-critical
// controls). 700-weight label, radius-md, mandatory hover/active/disabled
// states; the focus ring is never removed. `large` applies the §7 size
// (44 px tall, min 200 px wide) with uppercase tracking for emergency use.
Item {
    id: root

    property string text: ""
    property string variant: "primary"   // primary | danger
    property bool large: false
    property bool enabled_: true         // underscored: `enabled` is reserved by Item

    signal clicked

    readonly property color fill:
        variant === "danger" ? theme.danger : theme.accent
    readonly property color fillHover:
        variant === "danger" ? theme.danger_hover : theme.accent_hover
    readonly property color fillActive:
        variant === "danger" ? theme.danger_active : theme.accent_active

    readonly property int heightPx: large ? theme.control_h_lg : theme.control_h_md
    implicitWidth: Math.max(large ? 200 : 0,
                            label.implicitWidth + 2 * (large ? 24 : 16))
    implicitHeight: heightPx

    Rectangle {
        id: well
        anchors.fill: parent
        radius: theme.radius_md
        color: pressArea.pressed ? root.fillActive :
               pressArea.containsMouse ? root.fillHover :
               root.fill
        opacity: root.enabled_ ? 1.0 : theme.disabled_opacity
    }

    Text {
        id: label
        anchors.centerIn: parent
        text: root.text
        elide: Text.ElideRight
        font.family: theme.ui_family
        font.pixelSize: large ? theme.font_h3 : theme.font_body
        font.weight: Font.Bold
        font.letterSpacing: large ? 0.05 * theme.font_h3 : 0
        color: theme.text_inverse
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
