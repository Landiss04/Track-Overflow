// Labeled native select, style guide 6.2. Emits the value, not display text.
import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Controls.impl
import QtQuick.Layouts

ColumnLayout {
    id: root

    property string label: ""
    // Clear where the surrounding row already names the field; the label
    // is still used as the accessible name.
    property bool labelVisible: true
    property alias model: control.model
    property alias textRole: control.textRole
    property alias valueRole: control.valueRole
    property alias currentIndex: control.currentIndex
    readonly property var currentValue: control.currentValue
    signal committed(var value)

    spacing: theme.space_1
    opacity: enabled ? 1.0 : 0.42

    FieldLabel {
        Layout.fillWidth: true
        text: root.label.toUpperCase()
        visible: root.labelVisible && root.label !== ""
    }

    ComboBox {
        id: control
        objectName: "selectEditor"
        Layout.fillWidth: true
        implicitHeight: theme.control_h_md
        leftPadding: theme.space_3
        rightPadding: theme.space_3 + indicator.width + theme.space_2
        font.family: theme.mono_family
        font.pixelSize: theme.size_small
        Accessible.name: root.label
        palette.text: theme.text_primary
        palette.buttonText: theme.text_primary
        palette.button: theme.bg_sunken
        palette.base: theme.bg_surface
        palette.highlight: theme.accent
        palette.highlightedText: theme.on_accent

        // The Basic style greys its text and fades its arrow to 30 % when
        // disabled, on top of this field's own 42 %. Draw both from tokens so
        // disabled is dimmed exactly once, like every other control.
        contentItem: Text {
            text: control.displayText
            textFormat: Text.PlainText
            color: theme.text_primary
            font: control.font
            verticalAlignment: Text.AlignVCenter
            elide: Text.ElideRight
        }

        indicator: ColorImage {
            x: control.width - width - theme.space_3
            y: (control.height - height) / 2
            color: theme.text_secondary
            source: "qrc:/qt-project.org/imports/QtQuick/Controls/Basic/images/double-arrow.png"
        }

        background: Rectangle {
            radius: theme.radius_md
            color: theme.bg_sunken
            border.color: control.activeFocus ? theme.accent : theme.border_strong
            Rectangle {
                anchors.fill: parent
                anchors.margins: -4
                radius: theme.radius_md + 4
                visible: control.visualFocus
                color: "transparent"
                border.width: 2
                border.color: theme.focus_ring
            }
        }
        // The Basic popup takes its fill from the system palette, which is
        // black when Windows is in dark mode. Draw the list from tokens so it
        // matches the light theme whatever the OS setting. Only the selected
        // option carries the accent; hover and keyboard focus get a tint.
        delegate: ItemDelegate {
            id: option
            required property var model
            required property int index
            readonly property bool selected: index === control.currentIndex
            readonly property bool pointed: index === control.highlightedIndex

            width: ListView.view.width
            implicitHeight: theme.control_h_md
            leftPadding: theme.space_3
            rightPadding: theme.space_3
            hoverEnabled: control.hoverEnabled
            highlighted: pointed

            contentItem: Text {
                text: control.textRole
                    ? option.model[control.textRole] : option.model.modelData
                textFormat: Text.PlainText
                color: option.selected ? theme.on_accent : theme.text_primary
                font: control.font
                verticalAlignment: Text.AlignVCenter
                elide: Text.ElideRight
            }

            background: Rectangle {
                color: option.selected ? theme.accent
                    : option.pointed ? theme.accent_subtle : theme.bg_surface
            }
        }

        popup: Popup {
            y: control.height + theme.space_1
            width: control.width
            height: Math.min(contentItem.implicitHeight + 2 * padding,
                control.Window.height - topMargin - bottomMargin)
            topMargin: theme.space_2
            bottomMargin: theme.space_2
            padding: theme.space_1

            contentItem: ListView {
                clip: true
                implicitHeight: contentHeight
                model: control.delegateModel
                currentIndex: control.highlightedIndex
                highlightMoveDuration: 0
                ScrollIndicator.vertical: ScrollIndicator {}
            }

            background: Rectangle {
                color: theme.bg_surface
                radius: theme.radius_md
                border.color: theme.border_strong
            }
        }

        onActivated: root.committed(currentValue)
    }
}
