// Searchable train selector, for rosters too long to scroll through.
//
// Local because the shared library has no searchable select: the
// shared SelectField is a plain ComboBox. Styled from the same tokens
// as SelectField (guide 6.2), so the closed field looks the same.
//
// Type a number, an ID or a line ("114", "r-3", "green") to narrow
// the list; the line chips narrow it further. Up and Down move, Enter
// picks, Escape closes. The list is reparented onto the window's
// scaled canvas while it is open, so it scales with the window like
// the gains dialog (a Popup would float at 1:1) and lies over every
// panel whatever bar the picker sits in.
import QtQuick
import QtQuick.Layouts
import QtQuick.Window
import "../../../ui"

FocusScope {
    id: root

    property string label: ""
    // The roster, as ConsoleBackend.trains gives it: {id, line, label}.
    property var trains: []
    property string currentId: ""
    // The search text, also settable by the self-check.
    property alias query: input.text
    signal picked(string trainId)

    // Open while focus is in the search box or the list; closes on a
    // pick, on Escape, or when focus moves anywhere else.
    property bool open: false
    readonly property var lines: ["All", "GREEN LINE", "RED LINE"]
    property int lineIndex: 0
    property int highlighted: 0
    // How many rows show before the list scrolls.
    readonly property int visibleRows: 8

    readonly property var matches: {
        const words = input.text.trim().toLowerCase().split(/\s+/)
            .filter(function (w) { return w !== ""; });
        const line = lineIndex > 0 ? lines[lineIndex] : "";
        return trains.filter(function (t) {
            if (line !== "" && t.line !== line)
                return false;
            const hay = (t.id + " " + t.line).toLowerCase();
            return words.every(function (w) { return hay.indexOf(w) >= 0; });
        });
    }
    readonly property string currentLabel: {
        for (let i = 0; i < trains.length; ++i)
            if (trains[i].id === currentId)
                return trains[i].label;
        return trains.length > 0 ? "" : qsTr("No trains available");
    }

    function choose(index) {
        if (index < 0 || index >= matches.length)
            return;
        root.picked(matches[index].id);
        open = false;
    }

    function owns(item) {
        for (let it = item; it; it = it.parent)
            if (it === root || it === list)
                return true;
        return false;
    }

    Connections {
        target: root.Window.window
        function onActiveFocusItemChanged() {
            if (root.open && !root.owns(root.Window.window.activeFocusItem))
                root.open = false;
        }
    }

    onMatchesChanged: highlighted = Math.min(highlighted,
                                             Math.max(0, matches.length - 1))
    // Closing clears the search; opening starts on the current train.
    onOpenChanged: {
        if (!open) {
            input.text = "";
            lineIndex = 0;
            return;
        }
        const below = root.mapToItem(list.parent, 0,
                                     root.height + theme.space_1);
        list.x = below.x;
        list.y = below.y;
        highlighted = 0;
        for (let i = 0; i < matches.length; ++i)
            if (matches[i].id === currentId)
                highlighted = i;
    }

    implicitWidth: 280
    implicitHeight: column.implicitHeight
    opacity: enabled ? 1.0 : 0.42

    ColumnLayout {
        id: column
        anchors.left: parent.left
        anchors.right: parent.right
        spacing: theme.space_1

        FieldLabel {
            Layout.fillWidth: true
            text: root.label.toUpperCase()
        }

        Rectangle {
            id: field
            Layout.fillWidth: true
            implicitHeight: theme.control_h_md
            radius: theme.radius_md
            color: theme.bg_sunken
            border.color: input.activeFocus ? theme.accent : theme.border_strong

            Rectangle {
                anchors.fill: parent
                anchors.margins: -4
                radius: theme.radius_md + 4
                visible: input.activeFocus
                color: "transparent"
                border.width: 2
                border.color: theme.focus_ring
            }

            TextInput {
                id: input
                anchors.fill: parent
                anchors.leftMargin: theme.space_3
                anchors.rightMargin: theme.space_3
                verticalAlignment: TextInput.AlignVCenter
                color: theme.text_primary
                font.family: theme.mono_family
                font.pixelSize: theme.size_small
                clip: true
                enabled: root.enabled && root.trains.length > 0
                activeFocusOnTab: true
                Accessible.name: root.label
                Keys.onDownPressed: root.highlighted = Math.min(
                    root.highlighted + 1, root.matches.length - 1)
                Keys.onUpPressed: root.highlighted = Math.max(
                    root.highlighted - 1, 0)
                Keys.onReturnPressed: root.choose(root.highlighted)
                Keys.onEnterPressed: root.choose(root.highlighted)
                Keys.onEscapePressed: root.open = false
                onActiveFocusChanged: if (activeFocus) root.open = true
                // Typing reopens a closed list; clearing the search on
                // close must not.
                onTextChanged: {
                    root.highlighted = 0;
                    if (activeFocus && text !== "")
                        root.open = true;
                }
            }

            // Closed, the field reads the current train; open, it is the
            // search box, with a hint until something is typed.
            Text {
                anchors.fill: input
                verticalAlignment: Text.AlignVCenter
                visible: input.text === ""
                text: root.open ? qsTr("Search number or line…")
                                : root.currentLabel
                color: root.open ? theme.text_muted : theme.text_primary
                font: input.font
                elide: Text.ElideRight
            }

            MouseArea {
                anchors.fill: parent
                visible: !root.open
                enabled: input.enabled
                cursorShape: Qt.IBeamCursor
                onClicked: {
                    input.forceActiveFocus();
                    root.open = true;
                }
            }
        }
    }

    // The list, under the field, on the window's canvas.
    Rectangle {
        id: list
        parent: root.Window.window && root.Window.window.canvas
            ? root.Window.window.canvas : root
        z: 1000
        visible: root.open
        width: root.width
        height: listColumn.implicitHeight + 2 * theme.space_2
        radius: theme.radius_md
        color: theme.bg_surface
        border.color: theme.border_strong
        border.width: 1

        ColumnLayout {
            id: listColumn
            anchors.fill: parent
            anchors.margins: theme.space_2
            spacing: theme.space_1

            SegmentedToggle {
                Layout.fillWidth: true
                options: [qsTr("All"), qsTr("Green"), qsTr("Red")]
                currentIndex: root.lineIndex
                onActivated: function (index) {
                    root.lineIndex = index;
                    root.highlighted = 0;
                    // Back to the search box, so typing carries on.
                    input.forceActiveFocus();
                }
            }

            HelperText {
                Layout.fillWidth: true
                text: qsTr("%1 of %2 trains").arg(root.matches.length)
                    .arg(root.trains.length)
            }

            ListView {
                id: rows
                Layout.fillWidth: true
                implicitHeight: Math.min(root.matches.length,
                                         root.visibleRows) * theme.control_h_md
                clip: true
                model: root.matches
                currentIndex: root.highlighted
                onCurrentIndexChanged: positionViewAtIndex(currentIndex,
                                                           ListView.Contain)
                boundsBehavior: Flickable.StopAtBounds

                delegate: Rectangle {
                    id: row
                    required property int index
                    required property var modelData
                    readonly property bool selected:
                        modelData.id === root.currentId

                    width: ListView.view.width
                    height: theme.control_h_md
                    radius: theme.radius_sm
                    color: index === root.highlighted ? theme.accent_subtle
                                                      : "transparent"

                    RowLayout {
                        anchors.fill: parent
                        anchors.leftMargin: theme.space_2
                        anchors.rightMargin: theme.space_2
                        spacing: theme.space_2

                        MonoText {
                            text: row.modelData.id
                            font.weight: theme.weight_bold
                        }

                        Text {
                            Layout.fillWidth: true
                            text: row.modelData.line
                            color: theme.text_secondary
                            font.family: theme.ui_family
                            font.pixelSize: theme.size_small
                            elide: Text.ElideRight
                        }

                        StatusBadge {
                            visible: row.selected
                            variant: "info"
                            label: qsTr("Selected")
                        }
                    }

                    MouseArea {
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onEntered: root.highlighted = row.index
                        onClicked: root.choose(row.index)
                    }
                }
            }

            HelperText {
                Layout.fillWidth: true
                visible: root.matches.length === 0
                text: qsTr("No train matches.")
            }
        }
    }
}
