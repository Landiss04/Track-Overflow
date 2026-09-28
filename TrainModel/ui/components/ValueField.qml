// Input, style guide 6.2. --bg-sunken fill, 1 px --border-strong, mono face
// for numeric entry, --danger border plus a message when invalid.
import QtQuick
import QtQuick.Controls.Basic

TextField {
    id: control

    // int | float | string
    property string kind: "string"
    property bool valid: true
    signal committed(var value)

    implicitHeight: theme.control_h_md
    leftPadding: theme.space_3
    rightPadding: theme.space_3
    color: theme.text_primary
    font.family: theme.mono_family
    font.pixelSize: theme.size_small
    selectByMouse: true
    validator: kind === "int"
        ? intValidator : kind === "float" ? doubleValidator : null

    IntValidator { id: intValidator }
    DoubleValidator { id: doubleValidator; notation: DoubleValidator.StandardNotation }

    background: Rectangle {
        radius: theme.radius_md
        color: theme.bg_sunken
        border.width: control.activeFocus || !control.valid ? 2 : 1
        border.color: !control.valid ? theme.danger
            : control.activeFocus ? theme.accent : theme.border_strong
    }

    onEditingFinished: {
        control.valid = control.acceptableInput || control.kind === "string";
        if (control.valid) {
            control.committed(control.text);
        }
    }
}
