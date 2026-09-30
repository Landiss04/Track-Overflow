import QtQuick
import QtQuick.Layouts

// Callout / banner. Kind picks the semantic pair from Theme; the heading is
// always present so the state never rests on colour alone (§2, §8).
Rectangle {
    id: root

    property string kind: "info"   // ok | warning | fault | info | idle
    property string heading: ""
    property string body: ""
    property alias trailing: trailingRow.data

    readonly property color ink: Theme.semanticInk(kind)

    implicitHeight: layout.implicitHeight + 2 * Theme.space4
    radius: Theme.radiusLg
    color: Theme.semanticBg(kind)
    border.width: 1
    border.color: ink

    RowLayout {
        id: layout
        anchors.fill: parent
        anchors.margins: Theme.space4
        spacing: Theme.space4

        ColumnLayout {
            Layout.fillWidth: true
            spacing: Theme.space1

            Text {
                text: root.heading
                color: root.ink
                font.family: Theme.uiFamily
                font.pixelSize: Theme.sizeSmall
                font.bold: true
                font.letterSpacing: Theme.sizeSmall * Theme.labelTracking
                Layout.fillWidth: true
                wrapMode: Text.WordWrap
            }

            Text {
                text: root.body
                visible: root.body !== ""
                color: Theme.textSecondary
                font.family: Theme.uiFamily
                font.pixelSize: Theme.sizeSmall
                lineHeight: 1.5
                lineHeightMode: Text.ProportionalHeight
                Layout.fillWidth: true
                wrapMode: Text.WordWrap
            }
        }

        RowLayout {
            id: trailingRow
            spacing: Theme.space2
        }
    }
}
