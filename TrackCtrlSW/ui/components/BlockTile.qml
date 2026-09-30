// One track circuit in the block grid.
//
// Occupancy is carried by fill, closure by a hatch, and both repeat the
// state as a word: style guide 4.5 forbids colour as the only channel,
// and a dispatcher reading a grid of grey squares in a hurry is exactly
// the case that rule exists for.
import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

Rectangle {
    id: root

    property string label: ""
    property string feature: ""
    property string train: ""
    property string station: ""
    property int speedLimit: 0
    property bool occupied: false
    property bool closed: false
    property bool compact: false
    signal activated()

    readonly property string caption: occupied ? root.train
        : closed ? qsTr("CLOSED")
        : root.feature !== "" ? root.feature : qsTr("CLEAR")

    implicitHeight: compact ? theme.control_h_sm : 52
    color: occupied ? theme.block_occupied
        : closed ? theme.bg_sunken : theme.bg_app
    border.color: occupied ? theme.block_occupied : theme.border
    border.width: 1
    radius: theme.radius_sm

    // Closed blocks are hatched so they read differently from clear
    // ones without relying on the fill alone.
    Canvas {
        anchors.fill: parent
        anchors.margins: 1
        visible: root.closed && !root.occupied
        onPaint: {
            const context = getContext("2d");
            context.reset();
            context.strokeStyle = theme.block_closed;
            context.lineWidth = 2;
            for (let offset = -height; offset < width; offset += 7) {
                context.moveTo(offset, height);
                context.lineTo(offset + height, 0);
            }
            context.stroke();
        }
    }

    ColumnLayout {
        anchors.centerIn: parent
        spacing: 2

        MonoText {
            Layout.alignment: Qt.AlignHCenter
            text: root.label
            color: root.occupied ? theme.text_inverse : theme.text_primary
            font.pixelSize: root.compact ? theme.size_label : theme.size_small
            font.weight: theme.weight_bold
        }

        Text {
            Layout.alignment: Qt.AlignHCenter
            visible: !root.compact
            text: root.caption
            color: root.occupied ? theme.text_inverse : theme.text_muted
            font.family: root.occupied ? theme.mono_family : theme.ui_family
            font.pixelSize: 9
            font.letterSpacing: 0.4
        }
    }

    MouseArea {
        anchors.fill: parent
        cursorShape: Qt.PointingHandCursor
        hoverEnabled: true
        onClicked: root.activated()
    }

    // Hover surfaces the detail a tile is too small to show at rest.
    ToolTip.visible: hoverHandler.hovered
    ToolTip.text: root.label
        + (root.station !== "" ? " — " + root.station : "")
        + "\n" + root.caption
        + "\n" + root.speedLimit + " mph limit"
        + "\n" + qsTr("Click to close or reopen")

    HoverHandler { id: hoverHandler }
}
