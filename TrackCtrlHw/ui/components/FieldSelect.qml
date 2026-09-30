import QtQuick
import QtQuick.Controls.Basic

// Style Guide §6.2. Every input carries a visible Label-token label above it;
// placeholder text is not a label. Numeric values use the mono face.
Column {
    id: root

    property string label: ""
    property var options: []
    property int currentIndex: 0
    property bool mono: false
    property int fieldWidth: 140

    signal activated(int index)

    spacing: Theme.space1

    Text {
        text: root.label.toUpperCase()
        color: Theme.textMuted
        font.family: Theme.uiFamily
        font.pixelSize: Theme.sizeLabel
        font.bold: true
        font.letterSpacing: Theme.sizeLabel * Theme.labelTracking
    }

    ComboBox {
        id: box

        width: root.fieldWidth
        height: Theme.controlHMd
        model: root.options
        currentIndex: root.currentIndex
        onActivated: index => {
            root.currentIndex = index;
            root.activated(index);
        }

        background: Rectangle {
            radius: Theme.radiusMd
            color: Theme.bgSunken
            border.width: 1
            border.color: box.activeFocus ? Theme.accent : Theme.borderStrong

            Rectangle {
                anchors.fill: parent
                anchors.margins: -3
                visible: box.visualFocus
                radius: parent.radius + 3
                color: "transparent"
                border.width: 2
                border.color: Theme.focusRing
            }
        }

        contentItem: Text {
            leftPadding: Theme.space3
            rightPadding: Theme.space3
            text: box.displayText
            color: Theme.textPrimary
            font.family: root.mono ? Theme.monoFamily : Theme.uiFamily
            font.pixelSize: Theme.sizeBody
            verticalAlignment: Text.AlignVCenter
            elide: Text.ElideRight
        }

        indicator: Text {
            x: box.width - width - Theme.space3
            y: (box.height - height) / 2
            text: "\u25BE"
            color: Theme.textMuted
            font.family: Theme.uiFamily
            font.pixelSize: Theme.sizeBody
        }

        popup: Popup {
            y: box.height + Theme.space1
            width: box.width
            implicitHeight: Math.min(contentItem.implicitHeight + 2 * Theme.space1, 260)
            padding: Theme.space1

            background: Rectangle {
                radius: Theme.radiusMd
                color: Theme.bgSurface
                border.width: 1
                border.color: Theme.border
            }

            contentItem: ListView {
                clip: true
                implicitHeight: contentHeight
                model: box.delegateModel
                currentIndex: box.highlightedIndex
                boundsBehavior: Flickable.StopAtBounds
                ScrollBar.vertical: ScrollBar {}
            }
        }

        delegate: ItemDelegate {
            required property int index
            required property var modelData

            width: box.width - 2 * Theme.space1
            height: Theme.controlHMd
            highlighted: box.highlightedIndex === index

            background: Rectangle {
                radius: Theme.radiusSm
                color: parent.highlighted ? Theme.accentSubtle : "transparent"
            }

            contentItem: Text {
                leftPadding: Theme.space3
                text: modelData
                color: Theme.textPrimary
                font.family: root.mono ? Theme.monoFamily : Theme.uiFamily
                font.pixelSize: Theme.sizeBody
                verticalAlignment: Text.AlignVCenter
            }
        }
    }
}
