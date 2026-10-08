import QtQuick
import QtQuick.Layouts

// Callout / banner. Kind picks the semantic pair from the shared theme; the
// heading is always present so the state never rests on colour alone (§2, §8).
Rectangle {
    id: root

    property string kind: "info"   // ok | warning | fault | info | idle
    property string heading: ""
    property string body: ""
    // One line: heading then body, the body elided to fit.
    property bool compact: false
    property alias trailing: trailingRow.data

    readonly property color ink: kind === "ok" ? theme.success
        : kind === "warning" ? theme.warning
        : kind === "fault" ? theme.danger
        : kind === "info" ? theme.info
        : theme.text_muted
    readonly property color fill: kind === "ok" ? theme.success_bg
        : kind === "warning" ? theme.warning_bg
        : kind === "fault" ? theme.danger_bg
        : kind === "info" ? theme.info_bg
        : theme.bg_sunken

    implicitHeight: layout.implicitHeight
        + 2 * (compact ? theme.space_3 : theme.space_4)
    radius: theme.radius_lg
    color: fill
    border.width: 1
    border.color: ink

    RowLayout {
        id: layout
        anchors.fill: parent
        anchors.leftMargin: theme.space_4
        anchors.rightMargin: theme.space_4
        anchors.topMargin: root.compact ? theme.space_3 : theme.space_4
        anchors.bottomMargin: root.compact ? theme.space_3 : theme.space_4
        spacing: theme.space_4

        GridLayout {
            Layout.fillWidth: true
            columns: root.compact ? 2 : 1
            columnSpacing: theme.space_3
            rowSpacing: theme.space_1

            Text {
                text: root.heading
                textFormat: Text.PlainText
                color: root.ink
                font.family: theme.ui_family
                font.pixelSize: theme.size_small
                font.weight: theme.weight_bold
                font.letterSpacing: theme.label_letter_spacing
                Layout.fillWidth: !root.compact
                wrapMode: root.compact ? Text.NoWrap : Text.WordWrap
            }

            Text {
                text: root.body
                textFormat: Text.PlainText
                visible: root.body !== ""
                color: theme.text_secondary
                font.family: theme.ui_family
                font.pixelSize: theme.size_small
                lineHeight: root.compact ? 1.0 : 1.5
                lineHeightMode: Text.ProportionalHeight
                Layout.fillWidth: true
                wrapMode: root.compact ? Text.NoWrap : Text.WordWrap
                elide: root.compact ? Text.ElideRight : Text.ElideNone
            }
        }

        RowLayout {
            id: trailingRow
            spacing: theme.space_2
        }
    }
}
