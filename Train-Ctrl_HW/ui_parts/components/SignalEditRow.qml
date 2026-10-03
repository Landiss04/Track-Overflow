// One row of the Train Model interface table, style guide 6.6: name,
// type, value, unit, with a 1 px --border bottom rule. IDs and
// numbers are mono and the value column is right-aligned.
//
// The shared SignalRow is the same idea, but its editor is a labelled
// ValueField, so every editable row repeats its own name above the
// field and stands twice as tall. A bench with fifteen signals does
// not fit that way, so this composes the same shared editors with the
// label left off, and the name column carries it once.
//
// An Item rather than a RowLayout, so the rule can sit on the row's
// last pixel instead of adding a pixel to every row.
import QtQuick
import QtQuick.Layouts
import "../../../ui"

Item {
    id: root

    property string name: ""
    // int | float | string | bool | enum
    property string kind: "string"
    property var value: undefined
    property string unit: ""
    property bool editable: false
    // enum only: the values that may be chosen.
    property var options: []
    // Typed but not yet sent, so the name is marked.
    property bool pending: false
    property bool rule: true
    // Every row is the same height whatever editor it carries, so the
    // value column keeps one rhythm down the table.
    // Taller than the editor inside it, so consecutive fields have
    // air between them instead of stacking into one grey block.
    property real rowHeight: theme.control_h_md + theme.space_2 + 2
    // Read-only tables read better with the unit against its value
    // and the pair under the Value heading, rather than the value
    // flush right and the unit in a column of its own.
    property bool inlineUnit: false
    // Narrow columns drop the type, which the name already implies.
    property bool showKind: true
    property real valueWidth: 190
    property real unitWidth: 56
    property real valueSize: theme.size_small
    // Read-only tables pack their columns to the left instead of
    // stretching the name across the panel.
    property bool stretchName: true

    readonly property string shown: value === undefined || value === null
        || value === "" ? "\u2014"
        : kind === "bool" ? (value ? "TRUE" : "FALSE")
        : String(value)

    signal edited(var newValue)

    implicitHeight: root.rowHeight
    implicitWidth: row.implicitWidth

    RowLayout {
        id: row
        anchors.fill: parent
        spacing: theme.space_3

        MonoText {
            Layout.fillWidth: root.stretchName
            Layout.preferredWidth: root.stretchName ? 0 : 260
            text: (root.pending ? "\u2022 " : "") + root.name
            color: root.pending ? theme.accent : theme.text_primary
            font.pixelSize: root.valueSize
            elide: Text.ElideRight
        }

        MonoText {
            Layout.preferredWidth: root.showKind ? 52 : 0
            visible: root.showKind
            text: root.kind
            color: theme.text_muted
            font.pixelSize: theme.size_small
        }

        Item {
            Layout.preferredWidth: root.valueWidth
            Layout.preferredHeight: theme.control_h_md
            Layout.alignment: Qt.AlignVCenter

            MonoText {
                anchors.fill: parent
                visible: !root.editable
                text: root.inlineUnit && root.unit !== ""
                    ? root.shown + "  " + root.unit : root.shown
                font.pixelSize: root.valueSize
                verticalAlignment: Text.AlignVCenter
                // Numeric columns right-align (style guide 6.6) unless
                // the unit rides along, which reads as one value and
                // sits under the heading.
                horizontalAlignment: root.inlineUnit ? Text.AlignLeft
                                                     : Text.AlignRight
            }

            // A select carries a label slot even when its label is
            // empty, which would make one row taller than the rest.
            // Anchoring it to the bottom puts that empty slot above
            // the row, where it draws nothing, and leaves the control
            // itself the same height as every other editor.
            Loader {
                id: editor
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.bottom: parent.bottom
                visible: root.editable
                active: root.editable
                sourceComponent: root.kind === "bool" ? boolEditor
                    : root.kind === "enum" ? enumEditor : textEditor
            }
        }

        MonoText {
            Layout.preferredWidth: root.inlineUnit ? 0 : root.unitWidth
            visible: !root.inlineUnit
            text: root.unit
            color: theme.text_muted
            font.pixelSize: theme.size_small
        }

        // Read-only tables leave their slack at the right, so the
        // value and unit sit beside the name instead of across the
        // panel from it.
        Item { id: tail; Layout.fillWidth: !root.stretchName }
    }

    Rectangle {
        anchors.left: parent.left
        anchors.right: parent.right
        // The rule covers the columns, not the slack beside them, so
        // it lines up with the header's rule above.
        anchors.rightMargin: root.stretchName ? 0 : tail.width
        anchors.bottom: parent.bottom
        implicitHeight: 1
        visible: root.rule
        color: theme.border
    }

    Component {
        id: boolEditor

        SegmentedToggle {
            implicitHeight: theme.control_h_md
            options: [qsTr("True"), qsTr("False")]
            currentIndex: root.value ? 0 : 1
            onActivated: function (index) { root.edited(index === 0); }
        }
    }

    Component {
        id: enumEditor

        SelectField {
            model: root.options
            currentIndex: Math.max(0, root.options.indexOf(root.value))
            onCommitted: function (value) { root.edited(value); }
        }
    }

    Component {
        id: textEditor

        ValueField {
            kind: root.kind
            text: root.value === undefined || root.value === null
                ? "" : String(root.value)
            onCommitted: function (value) { root.edited(value); }
        }
    }
}
