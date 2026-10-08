import QtQuick
import QtQuick.Controls.Basic

import "../../../ui" as Shared

// Style Guide §6.6. Header uses the Label token with a --border-strong rule;
// rows are 13 px with --space-3 cell padding and a --border bottom rule.
// Because --bg-raised equals --bg-surface in the light theme, row hover applies
// an --accent-subtle tint rather than a lighter fill.
//
// columns: [{ title, width, fill, align }]
// rows:    [[cell, ...], ...] where a cell is one of
//          { text, mono, align, tone }
//          { badge, badgeText, text }
//          { button, enabled }
Item {
    id: root

    property var columns: []
    property var rows: []
    property int selectedRow: -1
    property bool selectable: true

    signal actionTriggered(int row, int column)

    readonly property int cellPadding: theme.space_3
    readonly property int rowHeight: 36
    readonly property int headerHeight: 32

    readonly property real flexWidth: {
        var fixed = 0;
        var flex = 0;
        for (var i = 0; i < columns.length; ++i) {
            if (columns[i].fill === true)
                flex += 1;
            else
                fixed += columns[i].width;
        }
        if (flex === 0)
            return 0;
        var gaps = Math.max(0, columns.length - 1) * theme.space_3;
        var avail = list.width - 2 * cellPadding - gaps - fixed;
        return Math.max(88, avail / flex);
    }

    function columnWidth(index) {
        var column = columns[index];
        return column.fill === true ? flexWidth : column.width;
    }

    function cellInk(cell) {
        if (cell.tone === "muted")
            return theme.text_muted;
        if (cell.tone === "secondary")
            return theme.text_secondary;
        return theme.text_primary;
    }

    function cellAlignment(index, cell) {
        var align = cell.align !== undefined ? cell.align : columns[index].align;
        if (align === "right")
            return Text.AlignRight;
        if (align === "center")
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
                        color: theme.text_muted
                        font.family: theme.ui_family
                        font.pixelSize: theme.size_label
                        font.bold: true
                        font.letterSpacing: theme.label_letter_spacing
                        verticalAlignment: Text.AlignVCenter
                        horizontalAlignment: root.columns[index].align === "right" ? Text.AlignRight : Text.AlignLeft
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
            model: root.rows

            ScrollBar.vertical: ScrollBar {
                policy: ScrollBar.AsNeeded
            }

            delegate: Item {
                id: rowItem

                required property int index
                required property var modelData

                width: list.width
                height: root.rowHeight

                Rectangle {
                    anchors.fill: parent
                    color: root.selectedRow === rowItem.index ? theme.accent_subtle : hoverArea.containsMouse ? theme.accent_subtle : "transparent"
                }

                MouseArea {
                    id: hoverArea
                    anchors.fill: parent
                    hoverEnabled: true
                    acceptedButtons: Qt.LeftButton
                    onClicked: if (root.selectable)
                        root.selectedRow = rowItem.index
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

                            readonly property var cell: rowItem.modelData[index] !== undefined ? rowItem.modelData[index] : ({})

                            width: root.columnWidth(index)
                            height: root.rowHeight

                            Text {
                                anchors.fill: parent
                                visible: cellItem.cell.badge === undefined && cellItem.cell.button === undefined
                                text: cellItem.cell.text !== undefined && cellItem.cell.text !== "" ? cellItem.cell.text : "\u2014"
                                color: root.cellInk(cellItem.cell)
                                font.family: cellItem.cell.mono === true ? theme.mono_family : theme.ui_family
                                font.pixelSize: theme.size_small
                                verticalAlignment: Text.AlignVCenter
                                horizontalAlignment: root.cellAlignment(index, cellItem.cell)
                                elide: Text.ElideRight
                            }

                            Row {
                                anchors.verticalCenter: parent.verticalCenter
                                visible: cellItem.cell.badge !== undefined
                                spacing: theme.space_2

                                Shared.StatusBadge {
                                    variant: cellItem.cell.badge !== undefined ? cellItem.cell.badge : "idle"
                                    label: cellItem.cell.badgeText !== undefined ? cellItem.cell.badgeText : ""
                                    anchors.verticalCenter: parent.verticalCenter
                                }

                                Text {
                                    visible: cellItem.cell.text !== undefined && cellItem.cell.text !== ""
                                    text: cellItem.cell.text !== undefined ? cellItem.cell.text : ""
                                    color: theme.text_secondary
                                    font.family: cellItem.cell.mono === true ? theme.mono_family : theme.ui_family
                                    font.pixelSize: theme.size_small
                                    anchors.verticalCenter: parent.verticalCenter
                                }
                            }

                            Shared.AppButton {
                                anchors.verticalCenter: parent.verticalCenter
                                anchors.right: parent.right
                                visible: cellItem.cell.button !== undefined
                                enabled: cellItem.cell.enabled !== false
                                size: "small"
                                text: cellItem.cell.button !== undefined ? cellItem.cell.button : ""
                                onClicked: root.actionTriggered(rowItem.index, cellItem.index)
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
}
