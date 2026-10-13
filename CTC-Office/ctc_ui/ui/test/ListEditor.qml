// A list-valued test UI row as a small table: one line of fields per
// entry, edited in place, with × to remove an entry and "+ Add" below.
//
// Fields come from ctc_ui/test_harness.py (LIST_FIELDS): line, block,
// switch and crossing pick from the track layout (blocks, switches and
// crossings of the entry's own line); choice picks from fixed options;
// text and number are typed.
pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import "../../../../ui"

ColumnLayout {
    id: root

    // [{ key, label, kind, width, options }]
    property var fields: []
    // [{ <key>: value, ... }]
    property var entries: []
    property var lineNames: []
    // { block|switch|crossing: { <line>: [{ value, text }] } }
    property var layoutOptions: ({})
    // What one entry is called on the Add button, e.g. "block".
    property string noun: qsTr("entry")

    signal addRequested()
    signal removeRequested(int index)
    signal fieldEdited(int index, string key, var value)

    readonly property int removeWidth: theme.control_h_md

    function optionsFor(field, entry) {
        if (field.kind === "line")
            return root.lineNames.map(function (name) {
                return { value: name, text: name };
            });
        if (field.kind === "block" || field.kind === "switch"
                || field.kind === "crossing")
            return (root.layoutOptions[field.kind] || {})[entry.line] || [];
        if (field.kind === "choice")
            return field.options;
        return [];
    }

    function indexOfValue(options, value) {
        for (let i = 0; i < options.length; ++i) {
            if (options[i].value === value)
                return i;
        }
        return -1;
    }

    spacing: theme.space_2

    // Column headings, once for the whole table.
    RowLayout {
        Layout.fillWidth: true
        visible: root.entries.length > 0
        spacing: theme.space_2

        Repeater {
            model: root.fields

            delegate: FieldLabel {
                required property var modelData
                Layout.preferredWidth: modelData.width
                text: modelData.label.toUpperCase()
                elide: Text.ElideRight
            }
        }

        Item { Layout.fillWidth: true }
    }

    Repeater {
        model: root.entries

        delegate: RowLayout {
            id: entryRow

            required property int index
            required property var modelData

            Layout.fillWidth: true
            spacing: theme.space_2

            Repeater {
                model: root.fields

                delegate: Item {
                    id: cell

                    required property var modelData
                    readonly property bool typed: modelData.kind === "text"
                        || modelData.kind === "number"
                    readonly property var options: typed ? []
                        : root.optionsFor(modelData, entryRow.modelData)

                    Layout.preferredWidth: modelData.width
                    implicitHeight: theme.control_h_md

                    SelectField {
                        anchors.fill: parent
                        visible: !cell.typed
                        textRole: "text"
                        valueRole: "value"
                        model: cell.options
                        currentIndex: root.indexOfValue(
                            cell.options,
                            entryRow.modelData[cell.modelData.key])
                        onCommitted: function (value) {
                            root.fieldEdited(entryRow.index,
                                             cell.modelData.key, value);
                        }
                    }

                    ValueField {
                        anchors.fill: parent
                        visible: cell.typed
                        kind: cell.modelData.kind === "number"
                            ? "float" : "string"
                        text: String(entryRow.modelData[cell.modelData.key]
                            ?? "")
                        onCommitted: function (value) {
                            root.fieldEdited(entryRow.index,
                                             cell.modelData.key, value);
                        }
                    }
                }
            }

            AppButton {
                Layout.preferredWidth: root.removeWidth
                variant: "ghost"
                size: "small"
                text: "×"
                Accessible.name: qsTr("Remove entry %1")
                    .arg(entryRow.index + 1)
                onClicked: root.removeRequested(entryRow.index)
            }

            Item { Layout.fillWidth: true }
        }
    }

    RowLayout {
        Layout.fillWidth: true
        spacing: theme.space_3

        AppButton {
            variant: "secondary"
            size: "small"
            text: qsTr("+ Add %1").arg(root.noun)
            onClicked: root.addRequested()
        }

        HelperText {
            Layout.fillWidth: true
            visible: root.entries.length === 0
            text: qsTr("None")
            color: theme.text_muted
        }
    }
}
