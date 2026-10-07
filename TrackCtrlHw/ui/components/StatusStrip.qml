import QtQuick
import QtQuick.Layouts

import "../../../ui" as Shared

// One-line status strip: a Label-token caption over a mono value, with
// trailing controls. Two strips share a row where a full panel would cost
// more height than the content needs.
Rectangle {
    id: root

    property string label: ""
    property string value: ""
    property string detail: ""
    default property alias controls: controlRow.data

    implicitHeight: Math.max(text.implicitHeight, controlRow.implicitHeight)
        + 2 * theme.space_3
    radius: theme.radius_lg
    color: theme.bg_surface
    border.width: 1
    border.color: theme.border

    RowLayout {
        anchors.fill: parent
        anchors.leftMargin: theme.space_4
        anchors.rightMargin: theme.space_3
        spacing: theme.space_3

        ColumnLayout {
            id: text
            Layout.fillWidth: true
            spacing: 2

            Shared.FieldLabel {
                Layout.fillWidth: true
                text: root.label.toUpperCase()
                elide: Text.ElideRight
            }

            Shared.MonoText {
                Layout.fillWidth: true
                text: root.value
                font.weight: theme.weight_bold
                elide: Text.ElideMiddle
            }

            Shared.HelperText {
                Layout.fillWidth: true
                visible: root.detail !== ""
                text: root.detail
                wrapMode: Text.NoWrap
                elide: Text.ElideRight
            }
        }

        RowLayout {
            id: controlRow
            spacing: theme.space_2
        }
    }
}
