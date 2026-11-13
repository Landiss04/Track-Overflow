// One kind of output (track circuits, switches, signals or crossings)
// behind a drop-down.
//
// A controller that owns a long run of track drives many devices, and
// listing every one makes the screen a wall of rows. The picker shows
// how many there are and the value of the one selected, as the original
// wireframe drew it ("SWITCH J v  REVERSE").
//
// ``items`` is rebuilt on every refresh. Feeding it straight to the
// ComboBox would reset the choice to the first entry each time, so the
// model is a separate list of names that changes only when the set of
// devices does.
//
// ``compact`` stacks the title, the drop-down and the value for narrow
// panes; otherwise they sit on one line.
import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

GridLayout {
    id: root

    // Rows of { name, label, value, kind }, all of one kind.
    property var items: []
    property string title: ""
    property var names: []
    property bool compact: false

    readonly property var current: items.length > 0
        ? items[Math.min(Math.max(box.currentIndex, 0), items.length - 1)]
        : null

    columns: compact ? 2 : 3
    columnSpacing: theme.space_3
    rowSpacing: theme.space_1
    visible: items.length > 0

    onItemsChanged: {
        const next = items.map(function (item) { return item.label; });
        if (next.join("|") !== names.join("|"))
            names = next;
    }

    Text {
        text: root.title + "  (" + root.items.length + ")"
        color: theme.text_secondary
        font.family: theme.ui_family
        font.pixelSize: theme.size_small
        Layout.preferredWidth: root.compact ? -1 : 120
        Layout.columnSpan: root.compact ? 2 : 1
        Layout.fillWidth: root.compact
    }

    ComboBox {
        id: box
        Layout.fillWidth: true
        implicitHeight: theme.control_h_sm + theme.space_1
        model: root.names
        font.family: theme.mono_family
        font.pixelSize: theme.size_small
    }

    SignalRow {
        Layout.preferredWidth: root.compact ? 128 : 150
        Layout.alignment: Qt.AlignRight
        label: ""
        value: root.current ? root.current.value : ""
        kind: root.current ? root.current.kind : "scalar"
    }
}
