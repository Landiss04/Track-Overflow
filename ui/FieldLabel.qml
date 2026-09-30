// Label token, style guide 3. Uppercase, 12 px, bold, muted.
import QtQuick

Text {
    color: theme.text_muted
    font.family: theme.ui_family
    font.pixelSize: theme.size_label
    font.weight: theme.weight_bold
    font.letterSpacing: theme.label_letter_spacing
    text: ""
    textFormat: Text.PlainText
}
