// Select, style guide 6.2. --bg-sunken fill, 1 px --border-strong,
// --accent border plus focus ring when focused. IDs use the mono face.
import QtQuick
import QtQuick.Controls.Basic

ComboBox {
    id: control

    property bool mono: false
    property string placeholder: qsTr("Select…")

    implicitHeight: theme.control_h_md
    leftPadding: theme.space_3
    rightPadding: theme.space_3 + indicatorGlyph.implicitWidth
    font.family: mono ? theme.mono_family : theme.ui_family
    font.pixelSize: theme.size_body
    opacity: enabled ? 1.0 : 0.42

    contentItem: Text {
        text: control.currentIndex < 0 ? control.placeholder
            : control.displayText
        color: control.currentIndex < 0 ? theme.text_muted
            : theme.text_primary
        font: control.font
        verticalAlignment: Text.AlignVCenter
        elide: Text.ElideRight
    }

    indicator: Text {
        id: indicatorGlyph
        x: control.width - width - theme.space_3
        anchors.verticalCenter: parent.verticalCenter
        text: "▾"
        color: theme.text_muted
        font.family: theme.ui_family
        font.pixelSize: theme.size_small
    }

    background: Rectangle {
        radius: theme.radius_md
        color: theme.bg_sunken
        border.width: 1
        border.color: control.activeFocus ? theme.accent : theme.border_strong

        Rectangle {
            anchors.fill: parent
            anchors.margins: -2
            visible: control.visualFocus
            color: "transparent"
            radius: theme.radius_md + 2
            border.width: 2
            border.color: theme.focus_ring
        }
    }
}
