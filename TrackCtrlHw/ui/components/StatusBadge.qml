import QtQuick

// Style Guide §6.3. Pill, 12 px uppercase bold, 1 px semantic border, 7 px dot,
// matching -bg fill. The text label is mandatory; a bare dot is not a status.
Rectangle {
    id: root

    property string kind: "idle"   // ok | warning | fault | info | idle
    property string text: ""

    readonly property color ink: Theme.semanticInk(kind)

    implicitHeight: 24
    implicitWidth: row.implicitWidth + 2 * Theme.space3
    radius: height / 2
    color: Theme.semanticBg(kind)
    border.width: 1
    border.color: ink

    Row {
        id: row
        anchors.centerIn: parent
        spacing: Theme.space2

        Rectangle {
            width: 7
            height: 7
            radius: 3.5
            color: root.ink
            anchors.verticalCenter: parent.verticalCenter
        }

        Text {
            text: root.text.toUpperCase()
            color: root.ink
            font.family: Theme.uiFamily
            font.pixelSize: Theme.sizeLabel
            font.bold: true
            font.letterSpacing: Theme.sizeLabel * Theme.labelTracking
            anchors.verticalCenter: parent.verticalCenter
        }
    }
}
