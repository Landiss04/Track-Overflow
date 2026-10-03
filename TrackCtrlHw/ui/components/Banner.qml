import QtQuick
import QtQuick.Layouts

// Callout / banner. Kind picks the semantic pair from the shared theme; the
// heading is always present so the state never rests on colour alone (§2, §8).
Rectangle {
    id: root

    property string kind: "info"   // ok | warning | fault | info | idle
    property string heading: ""
    property string body: ""
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

    implicitHeight: layout.implicitHeight + 2 * theme.space_4
    radius: theme.radius_lg
    color: fill
    border.width: 1
    border.color: ink

    RowLayout {
        id: layout
        anchors.fill: parent
        anchors.margins: theme.space_4
        spacing: theme.space_4

        ColumnLayout {
            Layout.fillWidth: true
            spacing: theme.space_1

            Text {
                text: root.heading
                color: root.ink
                font.family: theme.ui_family
                font.pixelSize: theme.size_small
                font.bold: true
                font.letterSpacing: theme.label_letter_spacing
                Layout.fillWidth: true
                wrapMode: Text.WordWrap
            }

            Text {
                text: root.body
                visible: root.body !== ""
                color: theme.text_secondary
                font.family: theme.ui_family
                font.pixelSize: theme.size_small
                lineHeight: 1.5
                lineHeightMode: Text.ProportionalHeight
                Layout.fillWidth: true
                wrapMode: Text.WordWrap
            }
        }

        RowLayout {
            id: trailingRow
            spacing: theme.space_2
        }
    }
}
