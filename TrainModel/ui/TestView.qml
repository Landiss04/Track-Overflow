// Test harness page. Every input the Train Model would receive from the
// Track Model or the Train Controller is supplied here instead, so the
// module can be run and graded on its own.
import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "../../ui"

Item {
    id: root

    // Sizes one input row slot: the tallest row, an editor with its label.
    SignalRow {
        id: rowProbe
        visible: false
        name: "probe"
        kind: "float"
        // A valid value, so no validation message adds to the height.
        value: 0
        unit: "mph"
        editable: true
    }

    RowLayout {
        anchors.fill: parent
        spacing: theme.space_5

        ColumnLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.preferredWidth: 1
            Layout.margins: theme.space_5
            Layout.rightMargin: 0
            spacing: theme.space_5

            Callout {
                Layout.fillWidth: true
                heading: qsTr("Test harness \u2014 module driven from this page")
                body: qsTr("Sending the inputs hands them to the Train Model "
                    + "and advances one tick. Each later tick reuses the last "
                    + "sent inputs. A boarding count boards once, at rest at "
                    + "a station with a door open, and waits in its row "
                    + "until then. Doors follow their commands at any "
                    + "speed. "
                    + "Select emergency_brake_command and send to override "
                    + "a passenger brake latch. Failures are set in the Train "
                    + "Model window. Controls show live model state; pending "
                    + "edits are marked until sent.")
            }

            Card {
                Layout.fillWidth: true
                Layout.fillHeight: true
                fillBody: true
                title: qsTr("Inputs")

                TableHeader { Layout.fillWidth: true }

                // Scrolls in place and wraps around: after the last input
                // comes the first again. Only the rows that fit are shown.
                PathView {
                    id: inputList

                    readonly property real slot: rowProbe.implicitHeight
                        + theme.space_3
                    // Scroll travel not yet turned into a whole row, in
                    // rows.
                    property real wheelRemainder: 0

                    // The control in a row that last held keyboard focus.
                    property Item keyboardItem: null

                    // Scroll just far enough to show a row. Keyboard focus
                    // can reach a row off the path (Tab), and a row out of
                    // sight must not take typing.
                    function reveal(row) {
                        const offset = (row - currentIndex + count) % count;
                        if (offset < pathItemCount)
                            return;
                        // Past the bottom, as Tab goes: in as the last row.
                        // Before the top, as Shift+Tab goes: as the first.
                        const below = offset - pathItemCount + 1;
                        const above = count - offset;
                        currentIndex = below <= above
                            ? (row - pathItemCount + 1 + count) % count : row;
                    }

                    objectName: "inputList"
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    clip: true
                    model: harness.inputDefinitions
                    pathItemCount: Math.max(
                        1, Math.min(count, Math.floor(height / slot)))
                    // Every row stays alive off the path, so scrolling
                    // never drops an edit in progress.
                    cacheItemCount: Math.max(0, count - pathItemCount)
                    // The current row is the top row.
                    preferredHighlightBegin: 0
                    preferredHighlightEnd: 0
                    highlightRangeMode: PathView.StrictlyEnforceRange
                    highlightMoveDuration: 120
                    snapMode: PathView.SnapOneItem

                    path: Path {
                        startX: inputList.width / 2
                        startY: inputList.slot / 2

                        PathLine {
                            x: inputList.width / 2
                            y: inputList.slot / 2
                                + inputList.pathItemCount * inputList.slot
                        }
                    }

                    Connections {
                        target: inputList.Window.window
                        function onActiveFocusItemChanged() {
                            const item = inputList.Window.activeFocusItem;
                            if (!item)
                                return;
                            // An item view gives its current row focus
                            // whenever the current row changes, as it does
                            // on every scroll. Give it back to the control
                            // that had it, so scrolling never takes focus
                            // from an edit or from Tab.
                            if (item.objectName === "inputSlot") {
                                const back = inputList.keyboardItem;
                                if (back && back.visible)
                                    back.forceActiveFocus();
                                return;
                            }
                            inputList.keyboardItem = item;
                            for (let p = item.parent; p; p = p.parent) {
                                if (p.objectName === "inputSlot") {
                                    inputList.reveal(p.index);
                                    return;
                                }
                            }
                        }
                    }

                    delegate: Item {
                        id: slotItem

                        required property var modelData
                        required property int index

                        objectName: "inputSlot"
                        width: inputList.width
                        height: inputList.slot

                        SignalRow {
                            property bool pending:
                                !!harness.pendingInputs[slotItem.modelData.name]

                            anchors.left: parent.left
                            anchors.right: parent.right
                            anchors.verticalCenter: parent.verticalCenter
                            objectName: "input-" + slotItem.modelData.name
                            kind: slotItem.modelData.kind
                            value: harness.displayInputValues[
                                slotItem.modelData.name]
                            unit: slotItem.modelData.unit
                            editable: true
                            name: slotItem.modelData.name
                                + (pending ? " (pending)" : "")
                            onEdited: function (newValue) {
                                harness.setDisplayInput(
                                    slotItem.modelData.name, newValue);
                            }
                        }
                    }

                    WheelHandler {
                        // A wheel handler takes only mouse wheels unless
                        // told otherwise; touchpads scroll this list too.
                        acceptedDevices: PointerDevice.Mouse
                            | PointerDevice.TouchPad
                        onWheel: function (event) {
                            // One row per wheel notch, or per row height
                            // of touchpad travel. Smaller steps add up
                            // first.
                            const pad = event.device.type
                                === PointerDevice.TouchPad;
                            inputList.wheelRemainder += pad && event.pixelDelta.y
                                ? event.pixelDelta.y / inputList.slot
                                : event.angleDelta.y / 120;
                            while (inputList.wheelRemainder <= -1) {
                                inputList.wheelRemainder += 1;
                                inputList.incrementCurrentIndex();
                            }
                            while (inputList.wheelRemainder >= 1) {
                                inputList.wheelRemainder -= 1;
                                inputList.decrementCurrentIndex();
                            }
                        }
                    }
                }
            }
        }

        // The output and run-control cards can be taller than the window,
        // so this column scrolls on its own.
        ScrollView {
            id: rightColumn

            objectName: "rightColumn"
            // Scroll a control that takes keyboard focus into sight, so
            // Tab never lands on a button below the fold.
            function reveal(item) {
                const flick = contentItem;
                const r = item.mapToItem(rightContent, 0, 0,
                    item.width, item.height);
                const margin = theme.space_3;
                if (r.y < flick.contentY)
                    flick.contentY = Math.max(0, r.y - margin);
                else if (r.y + r.height > flick.contentY + flick.height)
                    flick.contentY = Math.min(
                        flick.contentHeight - flick.height,
                        r.y + r.height - flick.height + margin);
            }

            // An item to scroll into sight once the column has grown to
            // hold it: a message just shown is not laid out yet.
            property Item pendingReveal: null

            Connections {
                target: rightColumn.contentItem
                function onContentHeightChanged() {
                    if (rightColumn.pendingReveal) {
                        rightColumn.reveal(rightColumn.pendingReveal);
                        rightColumn.pendingReveal = null;
                    }
                }
            }

            Connections {
                target: root.Window.window
                function onActiveFocusItemChanged() {
                    let item = root.Window.activeFocusItem;
                    for (let p = item; p; p = p.parent) {
                        if (p === rightContent) {
                            rightColumn.reveal(item);
                            return;
                        }
                    }
                }
            }

            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.preferredWidth: 1
            Layout.topMargin: theme.space_5
            Layout.bottomMargin: theme.space_5
            Layout.rightMargin: theme.space_5
            clip: true
            contentWidth: availableWidth
            // Always shown, so the controls below the fold are known to be
            // there.
            ScrollBar.vertical.policy: ScrollBar.AlwaysOn

            ColumnLayout {
                id: rightContent

                width: rightColumn.availableWidth
                spacing: theme.space_5

                Card {
                    Layout.fillWidth: true
                    title: qsTr("Outputs")

                    TableHeader { Layout.fillWidth: true }

                    // Stable rows bound to a value map: rebuilding every row on
                    // each tick cannot keep up with 10x.
                    Repeater {
                        model: harness.outputDefinitions

                        delegate: SignalRow {
                            required property var modelData

                            Layout.fillWidth: true
                            objectName: "output-" + modelData.name
                            name: modelData.name
                            kind: modelData.kind
                            value: harness.outputValues[modelData.name]
                            unit: modelData.unit
                        }
                    }

                    HelperText {
                        Layout.fillWidth: true
                        text: qsTr("Read back from the module. Values refresh "
                            + "whenever the module state changes.")
                    }
                }

                Card {
                    Layout.fillWidth: true
                    title: qsTr("Run control")
                    Text {
                        Layout.fillWidth: true
                        text: qsTr("Clock")
                        color: theme.text_secondary
                        font.family: theme.ui_family
                        font.pixelSize: theme.size_small
                        font.weight: theme.weight_regular
                    }

                    SegmentedToggle {
                        Layout.fillWidth: true
                        options: [qsTr("Run"), qsTr("Hold")]
                        currentIndex: harness.running ? 0 : 1
                        onActivated: function (index) {
                            harness.setRunning(index === 0);
                        }
                    }

                    Text {
                        Layout.fillWidth: true
                        Layout.topMargin: theme.space_2
                        text: qsTr("Speed")
                        color: theme.text_secondary
                        font.family: theme.ui_family
                        font.pixelSize: theme.size_small
                        font.weight: theme.weight_regular
                    }

                    // One segment per speed the shared clock accepts. Speed
                    // changes how often ticks happen, never dt.
                    SegmentedToggle {
                        objectName: "speedToggle"
                        Layout.fillWidth: true
                        options: harness.speeds.map(function (speed) {
                            return qsTr("%1x").arg(speed);
                        })
                        currentIndex: harness.speeds.indexOf(harness.speed)
                        onActivated: function (index) {
                            harness.setSpeed(harness.speeds[index]);
                        }
                    }

                    AppButton {
                        Layout.fillWidth: true
                        Layout.topMargin: theme.space_2
                        variant: "primary"
                        text: qsTr("Send inputs to train model")
                        onClicked: harness.sendInputs()
                    }

                    HelperText {
                        id: inputErrorText

                        objectName: "inputError"
                        Layout.fillWidth: true
                        visible: harness.inputError !== ""
                        // A refused send scrolls its reason into sight.
                        onVisibleChanged: if (visible)
                            rightColumn.pendingReveal = inputErrorText
                        text: qsTr("Inputs not sent: ") + harness.inputError
                        color: theme.danger
                    }

                    RowLayout {
                        Layout.fillWidth: true
                        spacing: theme.space_3

                        AppButton {
                            Layout.fillWidth: true
                            variant: "secondary"
                            text: qsTr("Advance one tick")
                            onClicked: harness.advanceTick()
                        }

                        AppButton {
                            Layout.fillWidth: true
                            variant: "secondary"
                            text: qsTr("Reset module")
                            onClicked: harness.resetModule()
                        }
                    }

                    KeyValueRow {
                        objectName: "track"
                        Layout.fillWidth: true
                        Layout.topMargin: theme.space_2
                        label: qsTr("Track")
                        value: harness.trackName
                    }

                    // The stand-in Train Controller lowers the entered
                    // power to hold the speed at or below this cap.
                    KeyValueRow {
                        objectName: "speedLimiter"
                        Layout.fillWidth: true
                        label: qsTr("Speed limiter")
                        value: qsTr("%1 mph cap").arg(
                                harness.speedCap.toFixed(1))
                            + (harness.limiting ? qsTr(" · limiting") : "")
                    }

                    // The stand-in Train Controller holds the train at a
                    // station for the 45 s dwell (D007) once a door opens.
                    KeyValueRow {
                        objectName: "dwell"
                        Layout.fillWidth: true
                        label: qsTr("Station dwell")
                        value: harness.dwellLeft > 0
                            ? qsTr("%1 s left").arg(
                                Math.ceil(harness.dwellLeft - 1e-9))
                            : "—"
                    }

                    KeyValueRow {
                        Layout.fillWidth: true
                        label: qsTr("Tick")
                        value: String(harness.tick)
                    }

                    KeyValueRow {
                        Layout.fillWidth: true
                        label: qsTr("dt")
                        value: Number(harness.dt).toFixed(3) + " s"
                    }

                    KeyValueRow {
                        Layout.fillWidth: true
                        label: qsTr("Elapsed")
                        value: harness.elapsed
                    }

                    // Checked every 30 clock ticks: ticks the shared clock
                    // spent that the Train Model did not take.
                    KeyValueRow {
                        objectName: "clockDrift"
                        Layout.fillWidth: true
                        label: qsTr("Clock drift")
                        value: (harness.driftTicks === 1 ? qsTr("1 tick")
                                : qsTr("%1 ticks").arg(harness.driftTicks))
                            + qsTr(" (%1 s)").arg(
                                (harness.driftTicks * harness.dt).toFixed(1))
                        rule: false
                    }

                    HelperText {
                        objectName: "driftWarning"
                        Layout.fillWidth: true
                        visible: harness.driftTicks > 0
                        text: qsTr("The Train Model is behind the shared "
                            + "clock. Reset the module to realign them.")
                        color: theme.warning
                    }
                }
            }
        }
    }
}
