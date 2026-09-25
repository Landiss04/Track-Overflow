import QtQuick
import QtQuick.Layouts

// Module window header (Style Guide §6.7): raised bar with a bottom rule,
// module name at H3 weight, optional subtitle, train selector in the mono
// face, and the simulation clock in mono Small/muted. `hamburger` renders
// the page-3b menu glyph as a simple stroked outline (no icon library).
Item {
    id: root

    property string title: ""
    property string subtitle: ""
    property bool hamburger: false
    property string trainSelector: ""
    property string clock: ""

    signal menuClicked

    implicitWidth: 0
    implicitHeight: theme.top_bar_height

    Rectangle {
        anchors.fill: parent
        color: theme.bg_raised
    }

    Rectangle {
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        height: 1
        color: theme.border
    }

    RowLayout {
        anchors.fill: parent
        anchors.leftMargin: theme.space_5
        anchors.rightMargin: theme.space_5
        spacing: theme.space_3

        // Hamburger — three stroked bars, stubbed per the mockup.
        Item {
            Layout.preferredWidth: theme.control_h_sm
            Layout.preferredHeight: theme.control_h_sm
            visible: root.hamburger

            Canvas {
                anchors.centerIn: parent
                width: theme.icon_size + 4
                height: theme.icon_size + 4
                onPaint: {
                    var ctx = getContext("2d")
                    ctx.clearRect(0, 0, width, height)
                    ctx.strokeStyle = theme.text_secondary
                    ctx.lineWidth = theme.stroke_width
                    for (var i = 0; i < 3; i++) {
                        var y = 4 + i * (theme.icon_size - 4) / 2
                        ctx.beginPath()
                        ctx.moveTo(2, y)
                        ctx.lineTo(width - 2, y)
                        ctx.stroke()
                    }
                }
            }

            MouseArea {
                anchors.fill: parent
                cursorShape: Qt.PointingHandCursor
                onClicked: root.menuClicked()
            }
        }

        Column {
            Layout.fillWidth: true
            spacing: 0

            Text {
                text: root.title
                font.family: theme.ui_family
                font.pixelSize: theme.font_h3
                font.weight: Font.Bold
                color: theme.text_primary
            }

            Text {
                visible: root.subtitle.length > 0
                text: root.subtitle
                font.family: theme.ui_family
                font.pixelSize: theme.font_small
                color: theme.text_muted
            }
        }

        // Train selector — mono ID chip (Style Guide §3: train IDs in mono).
        Rectangle {
            Layout.preferredHeight: 30
            Layout.leftMargin: theme.space_4
            visible: root.trainSelector.length > 0
            width: selectorText.implicitWidth + 2 * theme.space_3
            color: theme.bg_raised
            border.width: 1
            border.color: theme.border_strong
            radius: theme.radius_md

            Text {
                id: selectorText
                anchors.centerIn: parent
                text: root.trainSelector
                font.family: theme.mono_family
                font.pixelSize: theme.font_label
                color: theme.text_secondary
            }
        }

        // Simulation clock — mono, 13 px, muted (§6.7).
        Text {
            visible: root.clock.length > 0
            text: root.clock
            font.family: theme.mono_family
            font.pixelSize: theme.font_small
            color: theme.text_muted
        }
    }
}
