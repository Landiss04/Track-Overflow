// Labeled native select, style guide 6.2. Emits the value, not display text.
import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

ColumnLayout {
    id: root

    property string label: ""
    property alias model: control.model
    property alias textRole: control.textRole
    property alias valueRole: control.valueRole
    property alias currentIndex: control.currentIndex
    readonly property var currentValue: control.currentValue
    signal committed(var value)

    spacing: theme.space_1
    opacity: enabled ? 1.0 : 0.42

    FieldLabel {
        Layout.fillWidth: true
        text: root.label.toUpperCase()
    }

    ComboBox {
        id: control
        objectName: "selectEditor"
        Layout.fillWidth: true
        implicitHeight: theme.control_h_md
        leftPadding: theme.space_3
        rightPadding: theme.space_3
        font.family: theme.mono_family
        font.pixelSize: theme.size_small
        Accessible.name: root.label
        palette.text: theme.text_primary
        palette.buttonText: theme.text_primary
        palette.button: theme.bg_sunken
        palette.base: theme.bg_surface
        palette.highlight: theme.accent
        palette.highlightedText: theme.on_accent
        background: Rectangle {
            radius: theme.radius_md
            color: theme.bg_sunken
            border.color: control.activeFocus ? theme.accent : theme.border_strong
            Rectangle {
                anchors.fill: parent
                anchors.margins: -4
                radius: theme.radius_md + 4
                visible: control.visualFocus
                color: "transparent"
                border.width: 2
                border.color: theme.focus_ring
            }
        }
        onActivated: root.committed(currentValue)
    }
}
