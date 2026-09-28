// Status badge, style guide 6.3. Pill, 12 px uppercase bold, 1 px border in
// the semantic colour, 7 px dot, background the matching -bg token. The text
// label is required: a bare coloured dot is not an acceptable indicator.
import QtQuick
import QtQuick.Layouts

Rectangle {
    id: root

    // ok | warning | fault | info | idle
    property string variant: "idle"
    property string label: ""

    readonly property color tone: variant === "ok" ? theme.success
        : variant === "warning" ? theme.warning
        : variant === "fault" ? theme.danger
        : variant === "info" ? theme.info
        : theme.text_muted
    readonly property color fill: variant === "ok" ? theme.success_bg
        : variant === "warning" ? theme.warning_bg
        : variant === "fault" ? theme.danger_bg
        : variant === "info" ? theme.info_bg
        : theme.bg_sunken

    implicitWidth: row.implicitWidth + 2 * theme.space_3
    implicitHeight: theme.control_h_sm
    radius: height / 2
    color: fill
    border.color: tone
    border.width: 1

    RowLayout {
        id: row
        anchors.centerIn: parent
        spacing: theme.space_2

        Rectangle {
            implicitWidth: 7
            implicitHeight: 7
            radius: 3.5
            color: root.tone
        }

        Text {
            text: root.label.toUpperCase()
            color: root.tone
            font.family: theme.ui_family
            font.pixelSize: theme.size_label
            font.weight: theme.weight_bold
            font.letterSpacing: theme.label_letter_spacing
        }
    }
}
