// A labelled numeric input that is sent when editing finishes.
//
// The field shows the value the controller reports, but never while the
// tester is typing in it: a snapshot arriving once a second must not
// overwrite half-typed text.
import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "../../ui/components"

RowLayout {
    id: root

    property string label: ""
    property string unit: ""
    property string hint: ""
    // What the controller currently reports, as text.
    property string reported: ""
    property real minimum: 0
    property real maximum: 9999
    property int decimals: 0
    signal committed(real value)

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

    TextField {
        id: field

        implicitWidth: 84
        implicitHeight: theme.control_h_md
        horizontalAlignment: TextInput.AlignRight
        selectByMouse: true
        enabled: root.enabled
        opacity: enabled ? 1.0 : 0.42
        color: theme.text_primary
        font.family: theme.mono_family
        font.pixelSize: theme.size_small
        validator: DoubleValidator {
            bottom: root.minimum
            top: root.maximum
            decimals: root.decimals
            notation: DoubleValidator.StandardNotation
        }

        background: Rectangle {
            radius: theme.radius_md
            color: theme.bg_surface
            border.width: field.activeFocus ? 2 : 1
            border.color: field.activeFocus ? theme.focus_ring
                : theme.border_strong
        }

        Binding {
            target: field
            property: "text"
            value: root.reported
            when: !field.activeFocus
        }

        onEditingFinished: {
            if (text === "" || !acceptableInput) return;
            root.committed(parseFloat(text));
        }
    }

    Text {
        text: root.unit
        color: theme.text_muted
        font.family: theme.mono_family
        font.pixelSize: theme.size_label
        Layout.preferredWidth: 46
    }
}
