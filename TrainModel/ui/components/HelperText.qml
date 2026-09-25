import QtQuick

// Helper / secondary detail in the Small token (Style Guide §3).
Text {
    font.family: theme.ui_family
    font.pixelSize: theme.font_small
    color: theme.text_secondary
    wrapMode: Text.WordWrap
}
