import QtQuick

// Field label in the Label token (Style Guide §3): 12 px, bold, uppercase,
// letter-spaced, muted. Uppercase is applied here so views pass plain copy.
Text {
    id: root

    property string label: ""

    text: root.label.toUpperCase()
    font.family: theme.ui_family
    font.pixelSize: theme.font_label
    font.weight: Font.Bold
    font.letterSpacing: theme.label_tracking_em * theme.font_label
    color: theme.text_muted
}
