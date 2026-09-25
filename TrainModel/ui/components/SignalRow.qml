// One row of a signal table, style guide 6.6. Name and value columns are
// mono; an empty value renders as an em dash, never a blank cell.
import QtQuick
import QtQuick.Layouts

RowLayout {
    id: root

    property string name: ""
    property string kind: "string"
    property var value: undefined
    property string unit: ""
    property bool editable: false
    property int kindWidth: 64
    property int valueWidth: 180
    property int unitWidth: 52

    signal edited(var newValue)

    readonly property string displayValue: value === undefined || value === null
        || value === "" ? "\u2014"
        : kind === "bool" ? (value ? "TRUE" : "FALSE")
        : String(value)

    spacing: theme.space_3

    MonoText {
        Layout.fillWidth: true
        text: root.name
        elide: Text.ElideRight
    }

    MonoText {
        Layout.preferredWidth: root.kindWidth
        text: root.kind
        color: theme.text_muted
    }

    Item {
        Layout.preferredWidth: root.valueWidth
        implicitHeight: Math.max(readout.implicitHeight, editor.implicitHeight)

        MonoText {
            id: readout
            anchors.left: parent.left
            anchors.verticalCenter: parent.verticalCenter
            visible: !root.editable
            text: root.displayValue
        }

        Loader {
            id: editor
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.verticalCenter: parent.verticalCenter
            visible: root.editable
            active: root.editable
            sourceComponent: root.kind === "bool" ? boolEditor : textEditor
        }
    }

    MonoText {
        Layout.preferredWidth: root.unitWidth
        text: root.unit === "" ? "" : root.unit
        color: theme.text_muted
    }

    Component {
        id: boolEditor

        SegmentedToggle {
            options: ["True", "False"]
            currentIndex: root.value ? 0 : 1
            onActivated: function (index) { root.edited(index === 0); }
        }
    }

    Component {
        id: textEditor

        ValueField {
            kind: root.kind
            text: root.displayValue
            onCommitted: function (newValue) { root.edited(newValue); }
        }
    }
}
