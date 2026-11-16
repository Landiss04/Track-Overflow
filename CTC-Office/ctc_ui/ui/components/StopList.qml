// A train's stops, in the order it makes them: the stop it is heading
// for first (accent tint), then the ones queued after it. Each card
// shows the stop, its requested arrival and its state, with ▲ ▼ to move
// it and × to remove it. Dragging a card by its handle moves it too.
// The list scrolls past `visibleCards` cards. It asks; the panel acts
// (removeRequested, moveRequested) and the list follows the module.
import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "../../../../ui"

ColumnLayout {
    id: root

    property string trainId: ""
    // The CtcHost's stopQueues rows for the train.
    property var stops: []
    property int visibleCards: 4

    signal removeRequested(int index)
    signal moveRequested(int from, int to)

    readonly property int cardHeight: theme.control_h_lg
    readonly property int pitch: root.cardHeight + theme.space_2

    function badge(state) {
        return state === "heading" ? { variant: "info", label: qsTr("Heading") }
            : state === "at stop" ? { variant: "ok", label: qsTr("At stop") }
            : state === "returning" ? { variant: "info", label: qsTr("To yard") }
            : state === "yard" ? { variant: "idle", label: qsTr("In yard") }
            : { variant: "idle", label: qsTr("Queued") };
    }

    spacing: theme.space_2

    RowLayout {
        Layout.fillWidth: true
        spacing: theme.space_2

        FieldLabel {
            text: root.trainId !== ""
                ? qsTr("STOPS — %1").arg(root.trainId) : qsTr("STOPS")
        }
        Item { Layout.fillWidth: true }
        HelperText {
            visible: root.stops.length > 1
            color: theme.text_muted
            text: qsTr("Drag ⠿ or use ▲ ▼ to reorder")
        }
    }

    Rectangle {
        objectName: "stop-empty"
        Layout.fillWidth: true
        visible: root.stops.length === 0
        implicitHeight: root.cardHeight
        radius: theme.radius_md
        color: theme.bg_sunken
        border.color: theme.border
        border.width: 1

        HelperText {
            anchors.fill: parent
            anchors.leftMargin: theme.space_3
            anchors.rightMargin: theme.space_3
            verticalAlignment: Text.AlignVCenter
            elide: Text.ElideRight
            wrapMode: Text.NoWrap
            color: theme.text_muted
            text: root.trainId === ""
                ? qsTr("Select a train to see its stops.")
                : qsTr("No stops yet. Dispatch %1 to give it its first.")
                    .arg(root.trainId)
        }
    }

    ListView {
        id: list
        objectName: "stop-list"
        // Set while a card is dragged, so the list does not scroll too.
        property bool dragging: false

        Layout.fillWidth: true
        Layout.preferredHeight: Math.max(0,
            Math.min(count, root.visibleCards) * root.pitch - theme.space_2)
        visible: count > 0
        clip: true
        spacing: theme.space_2
        model: root.stops
        interactive: !dragging && contentHeight > height
        boundsBehavior: Flickable.StopAtBounds
        ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }

        delegate: Item {
            id: slot

            required property var modelData
            required property int index
            readonly property var shown: root.badge(slot.modelData.state)

            width: ListView.view.width
            height: root.cardHeight
            z: handle.drag.active ? 2 : 0

            // The cards are rebuilt when the train's stops change, as
            // when it moves on mid-drag: a card that goes while pressed
            // never gets its release, so the list scrolls again.
            Component.onDestruction: {
                if (list && handle && handle.pressed)
                    list.dragging = false;
            }

            Rectangle {
                id: card
                objectName: "stop-card-" + slot.index
                width: slot.width
                height: slot.height
                radius: theme.radius_md
                color: slot.index === 0 ? theme.accent_subtle : theme.bg_surface
                border.width: 1
                border.color: handle.drag.active ? theme.accent
                    : handle.containsMouse ? theme.border_strong : theme.border

                RowLayout {
                    anchors.fill: parent
                    anchors.leftMargin: theme.space_1
                    anchors.rightMargin: theme.space_2
                    spacing: theme.space_2

                    // Drag handle.
                    Item {
                        objectName: "stop-handle-" + slot.index
                        Layout.preferredWidth: theme.control_h_sm
                        Layout.fillHeight: true

                        Text {
                            anchors.centerIn: parent
                            text: "⠿"
                            color: theme.text_muted
                            font.family: theme.ui_family
                            font.pixelSize: theme.size_h3
                        }

                        MouseArea {
                            id: handle
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: drag.active ? Qt.ClosedHandCursor
                                : Qt.OpenHandCursor
                            enabled: list.count > 1
                            drag.target: card
                            drag.axis: Drag.YAxis
                            drag.threshold: 4
                            drag.minimumY: -slot.index * root.pitch
                            drag.maximumY: (list.count - 1 - slot.index)
                                * root.pitch
                            onPressed: list.dragging = true
                            onReleased: {
                                const to = Math.max(0, Math.min(
                                    list.count - 1,
                                    slot.index + Math.round(card.y
                                        / root.pitch)));
                                card.y = 0;
                                list.dragging = false;
                                if (to !== slot.index)
                                    root.moveRequested(slot.index, to);
                            }
                            onCanceled: {
                                card.y = 0;
                                list.dragging = false;
                            }
                        }
                    }

                    MonoText {
                        Layout.preferredWidth: 18
                        text: String(slot.index + 1)
                        color: theme.text_muted
                        font.pixelSize: theme.size_small
                        horizontalAlignment: Text.AlignRight
                    }

                    Text {
                        Layout.fillWidth: true
                        Layout.minimumWidth: 60
                        text: slot.modelData.name
                        textFormat: Text.PlainText
                        elide: Text.ElideRight
                        color: theme.text_primary
                        font.family: theme.ui_family
                        font.pixelSize: theme.size_body
                        font.weight: slot.index === 0 ? theme.weight_bold
                            : theme.weight_regular
                    }

                    MonoText {
                        text: slot.modelData.station
                            ? qsTr("block %1").arg(slot.modelData.block)
                            : ""
                        visible: text !== ""
                        color: theme.text_muted
                        font.pixelSize: theme.size_small
                    }

                    MonoText {
                        Layout.preferredWidth: 72
                        horizontalAlignment: Text.AlignRight
                        text: qsTr("arr %1").arg(slot.modelData.arrival)
                        color: slot.modelData.arrival === "—"
                            ? theme.text_muted : theme.text_secondary
                        font.pixelSize: theme.size_small
                    }

                    StatusBadge {
                        Layout.preferredWidth: 92
                        variant: slot.shown.variant
                        label: slot.shown.label
                    }

                    AppButton {
                        objectName: "stop-up-" + slot.index
                        Layout.preferredWidth: theme.control_h_sm
                        variant: "ghost"
                        size: "small"
                        leftPadding: 0
                        rightPadding: 0
                        text: "▲"
                        tooltip: qsTr("Move up")
                        Accessible.name: qsTr("Move stop %1 up")
                            .arg(slot.index + 1)
                        enabled: slot.index > 0
                        onClicked: root.moveRequested(slot.index,
                                                      slot.index - 1)
                    }

                    AppButton {
                        objectName: "stop-down-" + slot.index
                        Layout.preferredWidth: theme.control_h_sm
                        variant: "ghost"
                        size: "small"
                        leftPadding: 0
                        rightPadding: 0
                        text: "▼"
                        tooltip: qsTr("Move down")
                        Accessible.name: qsTr("Move stop %1 down")
                            .arg(slot.index + 1)
                        enabled: slot.index < list.count - 1
                        onClicked: root.moveRequested(slot.index,
                                                      slot.index + 1)
                    }

                    AppButton {
                        objectName: "stop-remove-" + slot.index
                        Layout.preferredWidth: theme.control_h_sm
                        variant: "ghost"
                        size: "small"
                        leftPadding: 0
                        rightPadding: 0
                        text: "×"
                        tooltip: list.count > 1 ? qsTr("Remove stop")
                            : qsTr("A train's only stop cannot be removed")
                        Accessible.name: qsTr("Remove stop %1")
                            .arg(slot.index + 1)
                        // The only stop stays: an order is not withdrawn.
                        enabled: list.count > 1
                        onClicked: root.removeRequested(slot.index)
                    }
                }
            }
        }
    }
}
