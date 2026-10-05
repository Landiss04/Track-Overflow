// Callout, style guide 4.3 / 4.4. A 3 px bar in the variant colour on the
// matching subtle background: --accent on --accent-subtle for info,
// --warning on --warning-bg for warning. The heading is always present so
// colour is never the only signal.
import QtQuick
import QtQuick.Layouts

Rectangle {
    id: root

    // info | warning
    property string variant: "info"
    property string heading: ""
    property string body: ""

    readonly property color tone: variant === "warning"
        ? theme.warning : theme.accent

    color: variant === "warning" ? theme.warning_bg : theme.accent_subtle
    radius: theme.radius_md
    implicitHeight: column.implicitHeight + 2 * theme.space_3

    Rectangle {
        anchors.left: parent.left
        anchors.top: parent.top
        anchors.bottom: parent.bottom
        width: theme.space_1 - 1
        color: root.tone
    }

    ColumnLayout {
        id: column
        anchors.fill: parent
        anchors.topMargin: theme.space_3
        anchors.bottomMargin: theme.space_3
        anchors.leftMargin: theme.space_4
        anchors.rightMargin: theme.space_4
        spacing: theme.space_1

        Text {
            Layout.fillWidth: true
            text: root.heading.toUpperCase()
            textFormat: Text.PlainText
            color: root.tone
            font.family: theme.ui_family
            font.pixelSize: theme.size_small
            font.weight: theme.weight_bold
            font.letterSpacing: theme.label_letter_spacing
            wrapMode: Text.WordWrap
        }

        HelperText {
            Layout.fillWidth: true
            text: root.body
            visible: root.body !== ""
        }
    }
}
