import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "../../../ui" as Shared

ColumnLayout {
    id: root
    property bool following: true
    property bool inspecting: false
    spacing: theme.space_2

    RowLayout {
        Layout.fillWidth: true
        Shared.HelperText {
            Layout.fillWidth: true
            text: "Last " + backend.events.count
                + " events · complete record in CSV"
        }
        Shared.AppButton {
            text: root.following ? "Read history" : "Follow latest"
            size: "small"
            Accessible.name: root.following
                ? "Stop following new events" : "Follow latest events"
            onClicked: {
                root.following = !root.following
                if (root.following)
                    events.positionViewAtEnd()
                if (root.following)
                    root.inspecting = false
            }
        }
    }
    ListView {
        id: events
        objectName: "eventList"
        Layout.fillWidth: true
        Layout.fillHeight: true
        model: backend.events
        clip: true
        spacing: theme.space_1
        activeFocusOnTab: true
        keyNavigationEnabled: true
        highlightMoveDuration: 0
        Accessible.name: "Harness events; arrows select an event"
        onMovementStarted: root.following = false
        Keys.onUpPressed: {
            root.following = false
            root.inspecting = true
            decrementCurrentIndex()
        }
        Keys.onDownPressed: {
            root.following = false
            root.inspecting = true
            incrementCurrentIndex()
        }
        ScrollBar.vertical: ScrollBar {}
        delegate: ItemDelegate {
            id: entry
            required property int index
            required property string time
            required property string tick
            required property string source
            required property string eventName
            required property string detail
            required property bool fault
            width: ListView.view.width
            implicitHeight: contentItem.implicitHeight + 2 * theme.space_2
            padding: theme.space_2
            focusPolicy: Qt.NoFocus
            hoverEnabled: true
            Accessible.name: time + ", tick " + tick + ", " + source
                + ", " + eventName + ", " + detail
            onClicked: {
                root.following = false
                root.inspecting = true
                events.currentIndex = index
                events.forceActiveFocus()
            }
            background: Rectangle {
                color: entry.index === events.currentIndex || entry.hovered
                    ? theme.accent_subtle
                    : entry.fault ? theme.danger_bg : theme.bg_surface
                border.width: entry.index === events.currentIndex
                    && events.activeFocus ? 2 : 1
                border.color: entry.index === events.currentIndex
                    && events.activeFocus ? theme.focus_ring : theme.border
                radius: theme.radius_md
            }
            contentItem: ColumnLayout {
                spacing: theme.space_1
                RowLayout {
                    Layout.fillWidth: true
                    spacing: theme.space_3
                    Shared.MonoText {
                        Layout.preferredWidth: 76
                        text: entry.time
                    }
                    Shared.MonoText {
                        Layout.preferredWidth: 75
                        text: "tick " + entry.tick
                        horizontalAlignment: Text.AlignRight
                    }
                    Shared.HelperText {
                        Layout.preferredWidth: 180
                        text: entry.source
                        wrapMode: Text.NoWrap
                        elide: Text.ElideRight
                    }
                    Shared.MonoText {
                        Layout.fillWidth: true
                        text: (entry.fault ? "FAULT · " : "") + entry.eventName
                        color: entry.fault ? theme.danger : theme.text_primary
                        elide: Text.ElideRight
                    }
                }
                Shared.HelperText {
                    Layout.fillWidth: true
                    text: entry.detail
                    wrapMode: Text.NoWrap
                    elide: Text.ElideRight
                }
            }
        }
        Shared.EmptyState {
            anchors.centerIn: parent
            visible: backend.events.count === 0
            heading: "Waiting for events"
            body: "Startup and run events appear here."
        }
        Rectangle {
            anchors.fill: parent
            color: "transparent"
            visible: events.activeFocus
            border.width: 2
            border.color: theme.focus_ring
        }
        Connections {
            target: backend.events
            function onCountChanged() {
                if (root.following)
                    events.positionViewAtEnd()
            }
        }
    }
    ScrollView {
        Layout.fillWidth: true
        Layout.preferredHeight: theme.control_h_lg
        visible: root.inspecting && events.currentIndex >= 0
        TextArea {
            readOnly: true
            selectByMouse: true
            text: {
                // Re-evaluate a retained selection after batch eviction.
                const count = backend.events.count
                const row = backend.events.row(events.currentIndex)
                return (row.eventName || "") + ": " + (row.detail || "—")
            }
            textFormat: TextEdit.PlainText
            wrapMode: TextEdit.WrapAnywhere
            font.family: theme.mono_family
            font.pixelSize: theme.size_small
            color: theme.text_primary
            selectedTextColor: theme.on_accent
            selectionColor: theme.accent
            Accessible.name: "Selected event detail"
            background: Rectangle {
                color: theme.bg_sunken
                border.color: parent.activeFocus
                    ? theme.focus_ring : theme.border
                border.width: parent.activeFocus ? 2 : 1
            }
        }
    }
}
