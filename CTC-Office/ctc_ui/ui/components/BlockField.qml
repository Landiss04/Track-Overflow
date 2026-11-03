// A block picker the dispatcher can type into: type the block number, or
// open the list and pick one. A line has up to 150 blocks, too many to
// scroll through.
//
// Like PickField it shows only what the dispatcher chose: `value` is ""
// until the text names a block in `model`, and a new model (another
// line) clears it. Drawn to match SelectField (style guide 6.2).
import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Controls.impl
import QtQuick.Layouts
import "../../../../ui"

ColumnLayout {
    id: root

    property string label: ""
    // The line's block IDs, as strings.
    property var model: []
    // The block the text names, or "" while it names none.
    readonly property string value: root.model.indexOf(root.typed) >= 0
        ? root.typed : ""
    readonly property string typed: control.editText.trim()
    // Text that names no block on the line.
    readonly property bool invalid: root.typed !== "" && root.value === ""

    // Forget the block (e.g. after the action it was for).
    function clear() {
        control.currentIndex = -1;
        control.editText = "";
    }

    spacing: theme.space_1
    opacity: enabled ? 1.0 : 0.42

    FieldLabel {
        Layout.fillWidth: true
        text: root.label.toUpperCase()
        visible: root.label !== ""
    }

    ComboBox {
        id: control
        Layout.fillWidth: true
        implicitHeight: theme.control_h_md
        editable: true
        model: root.model
        currentIndex: -1
        // A ComboBox fills itself with its first option whenever its
        // model is replaced; a new line starts empty instead.
        onModelChanged: Qt.callLater(root.clear)
        leftPadding: theme.space_3
        rightPadding: theme.space_3 + indicator.width + theme.space_2
        font.family: theme.mono_family
        font.pixelSize: theme.size_small
        validator: RegularExpressionValidator { regularExpression: /[0-9]{0,4}/ }
        inputMethodHints: Qt.ImhDigitsOnly
        Accessible.name: root.label
        // The ComboBox keeps editText in step with this field's text.
        contentItem: TextField {
            leftPadding: 0
            rightPadding: 0
            topPadding: 0
            bottomPadding: 0
            text: control.editText
            font: control.font
            color: theme.text_primary
            selectionColor: theme.accent
            selectedTextColor: theme.on_accent
            verticalAlignment: Text.AlignVCenter
            validator: control.validator
            inputMethodHints: control.inputMethodHints
            selectByMouse: true
            // Says the field takes typing, while it is empty.
            placeholderText: qsTr("Type or pick")
            placeholderTextColor: theme.text_muted
            background: null
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
            border.color: root.invalid ? theme.danger
                : control.activeFocus ? theme.accent : theme.border_strong
            Rectangle {
                anchors.fill: parent
                anchors.margins: -4
                radius: theme.radius_md + 4
                visible: control.activeFocus
                color: "transparent"
                border.width: 2
                border.color: theme.focus_ring
            }
        }

        delegate: ItemDelegate {
            id: option
            required property var modelData
            required property int index
            readonly property bool selected: option.modelData === root.value
            readonly property bool pointed: index === control.highlightedIndex

            width: ListView.view.width
            implicitHeight: theme.control_h_md
            leftPadding: theme.space_3
            rightPadding: theme.space_3
            hoverEnabled: control.hoverEnabled
            highlighted: pointed

            contentItem: Text {
                text: option.modelData
                textFormat: Text.PlainText
                color: option.selected ? theme.on_accent : theme.text_primary
                font: control.font
                verticalAlignment: Text.AlignVCenter
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
            // Open on the typed block, not at the top of the list.
            onOpened: options.positionViewAtIndex(
                Math.max(0, root.model.indexOf(root.value)), ListView.Center)

            contentItem: ListView {
                id: options
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
    }

    HelperText {
        Layout.fillWidth: true
        visible: root.invalid
        text: qsTr("No block %1 on this line.").arg(root.typed)
        color: theme.danger
    }
}
