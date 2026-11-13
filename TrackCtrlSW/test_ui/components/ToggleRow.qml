// A labelled boolean input: name in the mono face on the left, the
// switch on the right.
import QtQuick
import QtQuick.Layouts
import "../../ui/components"

RowLayout {
    id: root

    property string label: ""
    property string hint: ""
    property alias checked: toggle.checked
    property alias onText: toggle.onText
    property alias offText: toggle.offText
    signal toggled(bool value)

    spacing: theme.space_3

    ColumnLayout {
        spacing: 1
        Layout.fillWidth: true

        MonoText {
            text: root.label
            color: theme.text_primary
            font.weight: theme.weight_bold
        }

        Text {
            Layout.fillWidth: true
            visible: root.hint !== ""
            wrapMode: Text.WordWrap
            text: root.hint
            color: theme.text_muted
            font.family: theme.ui_family
            font.pixelSize: theme.size_label
        }
    }

    ToggleSwitch {
        id: toggle
        enabled: root.enabled
        onToggled: function (value) { root.toggled(value); }
    }
}
