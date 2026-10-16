import QtQuick
import QtQuick.Controls.Basic

import "../../../ui" as Shared

// Style Guide §6.6. Header uses the Label token with a --border-strong rule;
// rows are 13 px with --space-3 cell padding and a --border bottom rule.
// Because --bg-raised equals --bg-surface in the light theme, row hover applies
// an --accent-subtle tint rather than a lighter fill.
//
// Rows come from a model with a `row` role (track_ctrl_hw.rows_model), so a
// refresh updates cells in place and never resets the scroll position.
//
// columns: [{ title, role, width | fill, align, mono, tone, badgeRole }]
//   role       key of the row value shown in the cell
//   badgeRole  when set, the cell is a status badge whose variant is
//              row[badgeRole] and whose label is row[role]
Item {
    id: root

    property var columns: []
    property alias model: list.model
    property string emptyText: ""

    readonly property int cellPadding: theme.space_3
    readonly property int rowHeight: 36
    readonly property int headerHeight: 32

    readonly property real flexWidth: {
        let fixed = 0;
        let flex = 0;
        for (let i = 0; i < columns.length; ++i) {
            if (columns[i].fill === true)
                flex += 1;
            else
                fixed += columns[i].width;
        }
        if (flex === 0)
            return 0;
        const gaps = Math.max(0, columns.length - 1) * theme.space_3;
        return Math.max(64, (list.width - 2 * cellPadding - gaps - fixed) / flex);
    }

    function columnWidth(index) {
        const column = columns[index];
        return column.fill === true ? flexWidth : column.width;
    }

    function cellText(row, column) {
        const value = row ? row[column.role] : undefined;
        return value === undefined || value === null || value === ""
            ? "\u2014" : String(value);
    }

    function cellInk(column) {
        if (column.tone === "muted")
            return theme.text_muted;
        if (column.tone === "secondary")
            return theme.text_secondary;
        return theme.text_primary;
    }

    function cellAlignment(column) {
        if (column.align === "right")
            return Text.AlignRight;
        if (column.align === "center")
            return Text.AlignHCenter;
        return Text.AlignLeft;
    }

    Column {
        anchors.fill: parent
        spacing: 0

        Item {
            width: parent.width
            height: root.headerHeight

            Row {
                anchors.fill: parent
                anchors.leftMargin: root.cellPadding
                anchors.rightMargin: root.cellPadding
                spacing: theme.space_3

                Repeater {
                    model: root.columns.length

                    delegate: Text {
                        required property int index

                        width: root.columnWidth(index)
                        height: root.headerHeight
                        text: root.columns[index].title.toUpperCase()
                        textFormat: Text.PlainText
                        color: theme.text_muted
                        font.family: theme.ui_family
                        font.pixelSize: theme.size_label
                        font.weight: theme.weight_bold
                        font.letterSpacing: theme.label_letter_spacing
                        verticalAlignment: Text.AlignVCenter
                        horizontalAlignment: root.cellAlignment(root.columns[index])
                        elide: Text.ElideRight
                    }
                }
            }

            Rectangle {
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.bottom: parent.bottom
                height: 1
                color: theme.border_strong
            }
        }

        ListView {
            id: list

            width: parent.width
            height: parent.height - root.headerHeight
            clip: true
            boundsBehavior: Flickable.StopAtBounds

            ScrollBar.vertical: ScrollBar {
                policy: ScrollBar.AsNeeded
            }

            delegate: Item {
                id: rowItem

                required property var row

                width: list.width
                height: root.rowHeight

                Rectangle {
                    anchors.fill: parent
                    color: hoverArea.containsMouse ? theme.accent_subtle : "transparent"
                }

                MouseArea {
                    id: hoverArea
                    anchors.fill: parent
                    hoverEnabled: true
                    acceptedButtons: Qt.NoButton
                }

                Row {
                    anchors.fill: parent
                    anchors.leftMargin: root.cellPadding
                    anchors.rightMargin: root.cellPadding
                    spacing: theme.space_3

                    Repeater {
                        model: root.columns.length

                        delegate: Item {
                            id: cellItem

                            required property int index
                            readonly property var column: root.columns[index]
                            readonly property bool badge: column.badgeRole !== undefined

                            width: root.columnWidth(index)
                            height: root.rowHeight

                            Text {
                                anchors.fill: parent
                                visible: !cellItem.badge
                                text: root.cellText(rowItem.row, cellItem.column)
                                textFormat: Text.PlainText
                                color: root.cellInk(cellItem.column)
                                font.family: cellItem.column.mono === true
                                    ? theme.mono_family : theme.ui_family
                                font.pixelSize: theme.size_small
                                verticalAlignment: Text.AlignVCenter
                                horizontalAlignment: root.cellAlignment(cellItem.column)
                                elide: Text.ElideRight
                            }

                            Shared.StatusBadge {
                                anchors.verticalCenter: parent.verticalCenter
                                visible: cellItem.badge
                                variant: cellItem.badge && rowItem.row
                                    ? rowItem.row[cellItem.column.badgeRole] : "idle"
                                label: root.cellText(rowItem.row, cellItem.column)
                            }
                        }
                    }
                }

                Rectangle {
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.bottom: parent.bottom
                    height: 1
                    color: theme.border
                }
            }
        }
    }

    Text {
        anchors.centerIn: parent
        anchors.verticalCenterOffset: root.headerHeight / 2
        visible: list.count === 0 && root.emptyText !== ""
        width: parent.width - 2 * theme.space_5
        text: root.emptyText
        textFormat: Text.PlainText
        color: theme.text_muted
        font.family: theme.ui_family
        font.pixelSize: theme.size_small
        horizontalAlignment: Text.AlignHCenter
        wrapMode: Text.WordWrap
    }
}
