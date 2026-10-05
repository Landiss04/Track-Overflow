// One row of a signal table, style guide 6.6. Name and value columns are
// mono; an empty value renders as an em dash, never a blank cell.
import QtQuick
import QtQuick.Layouts

RowLayout {
    id: root

    property string name: ""
    // bool, int, uint (a count: whole number, 0 and up), float, string or enum.
    property string kind: "string"
    property var value: undefined
    property string unit: ""
    // Allowed values when kind is "enum"; ignored for every other kind.
    property var options: []
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
            width: parent.width
            horizontalAlignment: root.kind === "int" || root.kind === "uint"
                || root.kind === "float"
                ? Text.AlignRight : Text.AlignLeft
        }

        Loader {
            id: editor
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.verticalCenter: parent.verticalCenter
            visible: root.editable
            active: root.editable
            sourceComponent: root.kind === "bool" ? boolEditor
                : root.kind === "enum" ? enumEditor
                : root.kind === "uint" ? countEditor : textEditor
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
        id: enumEditor

        SelectField {
            label: root.name
            labelVisible: false
            model: root.options
            currentIndex: Math.max(0, root.options.indexOf(root.value))
            onCommitted: function (newValue) { root.edited(newValue); }
        }
    }

    Component {
        id: textEditor

        ValueField {
            label: root.name
            labelVisible: false
            kind: root.kind
            modelValue: root.value === undefined ? null : root.value
            onCommitted: function (newValue) { root.edited(newValue); }
        }
    }

    // Counts: whole numbers, 0 and up.
    Component {
        id: countEditor

        PositiveIntField {
            label: root.name
            labelVisible: false
            modelValue: root.value === undefined ? null : root.value
            onCommitted: function (newValue) { root.edited(newValue); }
        }
    }
}
