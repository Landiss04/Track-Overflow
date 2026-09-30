// Program tab: file explorer, PLC editor, docked terminal, live watch.
//
// The layout follows the IDE the programmer already knows, because the
// task is the one they already know how to do. What is different from
// an IDE is the run model, and that difference is stated on the strip
// above the editor rather than left to be discovered: RUN executes on
// a duplicate of the wayside's state, and only COMMIT reaches track.
import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import QtQuick.Dialogs
import "components"

Item {
    id: root

    signal openViewTab()

    readonly property var sandbox: wayside.sandbox
    readonly property var errorLines: wayside.diagnostics
        .filter(function (item) { return item.severity === "error"; })
        .map(function (item) { return item.line; })
    readonly property int errorCount: wayside.diagnostics
        .filter(function (item) { return item.severity === "error"; }).length
    readonly property int warningCount: wayside.diagnostics
        .filter(function (item) { return item.severity === "warning"; }).length

    RowLayout {
        anchors.fill: parent
        anchors.margins: theme.space_3
        spacing: theme.space_3

        // --- explorer --------------------------------------------------
        // The side columns are pinned rather than merely preferred:
        // wrapping help text reports a very wide implicit width, which
        // would otherwise squeeze the editor out of the row.
        Panel {
            Layout.preferredWidth: 248
            Layout.minimumWidth: 248
            Layout.maximumWidth: 248
            Layout.fillHeight: true
            title: qsTr("File explorer")
            status: wayside.files.length + qsTr(" FILES")

            ColumnLayout {
                anchors.fill: parent
                spacing: 0

                Text {
                    Layout.fillWidth: true
                    Layout.margins: theme.space_3
                    Layout.bottomMargin: theme.space_1
                    text: wayside.selectedLine.toUpperCase() + " / "
                        + wayside.selectedController
                    color: theme.text_muted
                    font.family: theme.ui_family
                    font.pixelSize: theme.size_label
                    font.letterSpacing: theme.label_letter_spacing
                    elide: Text.ElideRight
                }

                ListView {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    clip: true
                    model: wayside.files
                    boundsBehavior: Flickable.StopAtBounds

                    delegate: Rectangle {
                        required property var modelData

                        width: ListView.view.width
                        implicitHeight: theme.control_h_md
                        color: modelData.current
                            ? theme.accent_subtle : "transparent"

                        Rectangle {
                            anchors.left: parent.left
                            anchors.top: parent.top
                            anchors.bottom: parent.bottom
                            implicitWidth: 3
                            color: theme.accent
                            visible: parent.modelData.current
                        }

                        RowLayout {
                            anchors.fill: parent
                            anchors.leftMargin: theme.space_3
                            anchors.rightMargin: theme.space_3
                            spacing: theme.space_2

                            MonoText {
                                text: parent.parent.modelData.name
                                color: theme.text_primary
                                elide: Text.ElideMiddle
                                Layout.fillWidth: true
                            }

                            Text {
                                text: parent.parent.modelData.detail
                                color: theme.text_muted
                                font.family: theme.ui_family
                                font.pixelSize: 10
                                font.letterSpacing: 0.4
                            }
                        }

                        MouseArea {
                            anchors.fill: parent
                            cursorShape: Qt.PointingHandCursor
                            onClicked: wayside.openFile(
                                parent.modelData.iteration)
                        }
                    }
                }

                Rectangle {
                    Layout.fillWidth: true
                    implicitHeight: 1
                    color: theme.border
                }

                Text {
                    Layout.fillWidth: true
                    Layout.margins: theme.space_3
                    text: qsTr("The live buffer sits above the five most "
                        + "recent committed iterations. Opening an "
                        + "iteration shows it read-only.")
                    color: theme.text_muted
                    font.family: theme.ui_family
                    font.pixelSize: theme.size_label
                    wrapMode: Text.WordWrap
                }

                RowLayout {
                    Layout.fillWidth: true
                    Layout.margins: theme.space_3
                    Layout.topMargin: 0
                    spacing: theme.space_2

                    AppButton {
                        Layout.fillWidth: true
                        text: qsTr("Load .plc file")
                        size: "small"
                        onClicked: fileDialog.open()
                    }

                    AppButton {
                        text: qsTr("New")
                        size: "small"
                        tooltip: qsTr("Start from this controller's layout")
                        onClicked: wayside.newFile()
                    }
                }
            }
        }

        // --- editor + terminal -----------------------------------------
        ColumnLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.minimumWidth: 420
            spacing: theme.space_3

            Panel {
                Layout.fillWidth: true
                Layout.fillHeight: true
                title: wayside.bufferFile
                status: root.errorCount > 0
                    ? root.errorCount + qsTr(" ERRORS")
                    : qsTr("BOOLEAN ONLY · ")
                        + (root.sandbox.booleans !== undefined
                            ? root.sandbox.booleans + qsTr(" BOOLEANS") : qsTr("NOT RUN"))

                ColumnLayout {
                    anchors.fill: parent
                    spacing: 0

                    // Toolbar.
                    Rectangle {
                        Layout.fillWidth: true
                        implicitHeight: theme.control_h_lg
                        color: theme.bg_surface

                        Rectangle {
                            anchors.left: parent.left
                            anchors.right: parent.right
                            anchors.bottom: parent.bottom
                            implicitHeight: 1
                            color: theme.border
                        }

                        RowLayout {
                            anchors.fill: parent
                            anchors.leftMargin: theme.space_3
                            anchors.rightMargin: theme.space_3
                            spacing: theme.space_2

                            AppButton {
                                text: qsTr("Run")
                                variant: "primary"
                                size: "small"
                                enabled: !wayside.bufferReadOnly
                                tooltip: wayside.bufferReadOnly
                                    ? qsTr("This is a committed iteration. "
                                        + "Open the live buffer to run.")
                                    : qsTr("Compile and scan against a "
                                        + "duplicate of this wayside's state")
                                onClicked: wayside.run()
                            }

                            AppButton {
                                text: qsTr("Commit iteration")
                                variant: "success"
                                size: "small"
                                enabled: wayside.canCommit
                                tooltip: wayside.canCommit
                                    ? qsTr("Replace the program executing on "
                                        + wayside.selectedController)
                                    : qsTr("Run this exact buffer first")
                                onClicked: wayside.commit()
                            }

                            Rectangle {
                                implicitWidth: 1
                                implicitHeight: theme.space_4
                                color: theme.border
                            }

                            StatusBadge {
                                label: wayside.bufferReadOnly
                                    ? qsTr("History")
                                    : wayside.bufferDirty
                                        ? qsTr("Edited") : qsTr("Committed")
                                variant: wayside.bufferReadOnly ? "info"
                                    : wayside.bufferDirty ? "warning" : "ok"
                            }

                            StatusBadge {
                                label: qsTr("Verified")
                                variant: "info"
                                visible: wayside.canCommit
                            }

                            Item { Layout.fillWidth: true }

                            MonoText {
                                text: qsTr("iteration #") + wayside.controller.iteration
                                color: theme.text_muted
                            }
                        }
                    }

                    // The run model, stated where the buttons are.
                    Rectangle {
                        Layout.fillWidth: true
                        implicitHeight: theme.control_h_md
                        color: wayside.canCommit
                            ? theme.success_bg : theme.bg_sunken

                        Rectangle {
                            anchors.left: parent.left
                            anchors.right: parent.right
                            anchors.bottom: parent.bottom
                            implicitHeight: 1
                            color: theme.border
                        }

                        Text {
                            anchors.fill: parent
                            anchors.leftMargin: theme.space_3
                            anchors.rightMargin: theme.space_3
                            verticalAlignment: Text.AlignVCenter
                            text: wayside.canCommit
                                ? qsTr("This buffer ran clean on duplicate "
                                    + "state. COMMIT will put it on "
                                    + wayside.selectedController + ".")
                                : qsTr("RUN executes on a duplicate of the "
                                    + "wayside's state and changes nothing on "
                                    + "the track. Only COMMIT does.")
                            color: wayside.canCommit
                                ? theme.success : theme.text_secondary
                            font.family: theme.ui_family
                            font.pixelSize: theme.size_label
                            elide: Text.ElideRight
                        }
                    }

                    CodeEditor {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        text: wayside.buffer
                        readOnly: wayside.bufferReadOnly
                        errorLines: root.errorLines
                        onEdited: function (value) { wayside.setBuffer(value); }
                    }
                }
            }

            // --- terminal ----------------------------------------------
            Panel {
                Layout.fillWidth: true
                Layout.preferredHeight: 224
                title: qsTr("Terminal — ") + wayside.selectedController
                    + qsTr(" outputs")
                status: root.errorCount + root.warningCount > 0
                    ? root.errorCount + qsTr("E ") + root.warningCount + qsTr("W")
                    : qsTr("0 ERRORS")

                ColumnLayout {
                    anchors.fill: parent
                    spacing: 0

                    RowLayout {
                        Layout.fillWidth: true
                        Layout.margins: theme.space_2
                        Layout.bottomMargin: 0
                        spacing: theme.space_1

                        Repeater {
                            model: [qsTr("Output log"), qsTr("Parser")]

                            delegate: Rectangle {
                                required property int index
                                required property string modelData

                                readonly property bool selected:
                                    index === terminalTabs.currentIndex

                                implicitWidth: paneLabel.implicitWidth
                                    + 2 * theme.space_3
                                implicitHeight: theme.control_h_sm
                                radius: theme.radius_sm
                                color: selected ? theme.bg_sunken : "transparent"
                                border.color: selected ? theme.border : "transparent"
                                border.width: selected ? 1 : 0

                                Text {
                                    id: paneLabel
                                    anchors.centerIn: parent
                                    text: modelData
                                    color: parent.selected
                                        ? theme.text_primary : theme.text_muted
                                    font.family: theme.ui_family
                                    font.pixelSize: theme.size_label
                                    font.weight: theme.weight_bold
                                }

                                MouseArea {
                                    anchors.fill: parent
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: terminalTabs.currentIndex = index
                                }
                            }
                        }

                        Item { Layout.fillWidth: true }
                    }

                    StackLayout {
                        id: terminalTabs
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        currentIndex: 0

                        // Output log: every scan line, newest at the end.
                        ListView {
                            clip: true
                            model: wayside.terminal
                            boundsBehavior: Flickable.StopAtBounds
                            // Follow the tail the way a console does.
                            onCountChanged: positionViewAtEnd()

                            delegate: MonoText {
                                required property string modelData

                                x: theme.space_3
                                width: ListView.view.width - 2 * theme.space_3
                                text: modelData
                                color: modelData.indexOf("VITAL") !== -1
                                    ? theme.warning
                                    : modelData.indexOf("ERROR") !== -1
                                        ? theme.danger : theme.text_secondary
                                font.pixelSize: theme.size_label
                                elide: Text.ElideRight
                            }
                        }

                        // Parser: the compiler's own messages.
                        ListView {
                            clip: true
                            model: wayside.diagnostics
                            boundsBehavior: Flickable.StopAtBounds

                            delegate: RowLayout {
                                required property var modelData

                                x: theme.space_3
                                width: ListView.view.width - 2 * theme.space_3
                                spacing: theme.space_2

                                StatusBadge {
                                    label: parent.modelData.severity
                                    variant: parent.modelData.severity === "error"
                                        ? "fault" : "warning"
                                }

                                MonoText {
                                    text: parent.modelData.line > 0
                                        ? qsTr("line ") + parent.modelData.line : ""
                                    color: theme.text_muted
                                    font.pixelSize: theme.size_label
                                }

                                Text {
                                    text: parent.modelData.message
                                    color: theme.text_primary
                                    font.family: theme.ui_family
                                    font.pixelSize: theme.size_small
                                    elide: Text.ElideRight
                                    Layout.fillWidth: true
                                }
                            }

                            // An empty parser pane is a result, not a blank.
                            Text {
                                anchors.centerIn: parent
                                visible: wayside.diagnostics.length === 0
                                text: qsTr("No compiler messages. Run the "
                                    + "buffer to check it.")
                                color: theme.text_muted
                                font.family: theme.ui_family
                                font.pixelSize: theme.size_small
                            }
                        }
                    }
                }
            }
        }

        // --- watch -----------------------------------------------------
        ColumnLayout {
            Layout.preferredWidth: 344
            Layout.minimumWidth: 344
            Layout.maximumWidth: 344
            Layout.fillHeight: true
            spacing: theme.space_3

            Rectangle {
                Layout.fillWidth: true
                implicitHeight: runningNote.implicitHeight + 2 * theme.space_3
                color: theme.bg_sunken
                border.color: theme.border
                border.width: 1
                radius: theme.radius_md

                Text {
                    id: runningNote
                    anchors.fill: parent
                    anchors.margins: theme.space_3
                    text: qsTr("Running iteration #") + wayside.controller.iteration
                        + qsTr(" — ") + wayside.controller.file
                        + qsTr(". The wayside executes the committed program, "
                            + "not the editor buffer.")
                    color: theme.text_secondary
                    font.family: theme.ui_family
                    font.pixelSize: theme.size_label
                    wrapMode: Text.WordWrap
                }
            }

            Panel {
                Layout.fillWidth: true
                Layout.fillHeight: true
                title: qsTr("Watch — inputs")
                status: wayside.blocks.filter(function (block) {
                    return block.occupied; }).length + qsTr(" OCCUPIED")

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: theme.space_3
                    spacing: theme.space_3

                    GridLayout {
                        Layout.fillWidth: true
                        columns: 6
                        columnSpacing: theme.space_1
                        rowSpacing: theme.space_1

                        Repeater {
                            model: wayside.blocks

                            delegate: BlockTile {
                                required property var modelData

                                Layout.fillWidth: true
                                compact: true
                                label: modelData.label
                                feature: modelData.feature
                                train: modelData.train
                                occupied: modelData.occupied
                                closed: modelData.closed
                                station: modelData.station
                                speedLimit: modelData.speed_limit
                                onActivated: wayside.setBlockClosed(
                                    modelData.id, !modelData.closed)
                            }
                        }
                    }

                    Text {
                        Layout.fillWidth: true
                        text: qsTr("Filled = occupied, hatched = closed, from "
                            + "the Track Model. Click a block to close or "
                            + "reopen it.")
                        color: theme.text_muted
                        font.family: theme.ui_family
                        font.pixelSize: theme.size_label
                        wrapMode: Text.WordWrap
                    }

                    Rectangle {
                        Layout.fillWidth: true
                        implicitHeight: 1
                        color: theme.border
                    }

                    Repeater {
                        model: wayside.inputSignals

                        delegate: SignalRow {
                            required property var modelData

                            Layout.fillWidth: true
                            label: modelData.label
                            value: modelData.value
                        }
                    }

                    Rectangle {
                        Layout.fillWidth: true
                        implicitHeight: 1
                        color: theme.border
                    }

                    Text {
                        Layout.fillWidth: true
                        text: qsTr("WATCH — OUTPUTS")
                        color: theme.text_secondary
                        font.family: theme.ui_family
                        font.pixelSize: theme.size_label
                        font.weight: theme.weight_bold
                        font.letterSpacing: theme.label_letter_spacing
                    }

                    Repeater {
                        model: wayside.outputs

                        delegate: SignalRow {
                            required property var modelData

                            Layout.fillWidth: true
                            label: modelData.label
                            value: modelData.value
                            kind: modelData.kind
                        }
                    }

                    // Vital overrides are the difference between what the
                    // program asked for and what the track is doing, so
                    // they sit with the outputs rather than in the log.
                    Rectangle {
                        Layout.fillWidth: true
                        Layout.preferredHeight: overrideColumn.implicitHeight
                            + 2 * theme.space_2
                        visible: wayside.overrides.length > 0
                        color: theme.warning_bg
                        border.color: theme.warning
                        border.width: 1
                        radius: theme.radius_sm

                        ColumnLayout {
                            id: overrideColumn
                            anchors.left: parent.left
                            anchors.right: parent.right
                            anchors.top: parent.top
                            anchors.margins: theme.space_2
                            spacing: 2

                            Text {
                                text: qsTr("VITAL OVERRIDES · ")
                                    + wayside.overrides.length
                                color: theme.warning
                                font.family: theme.ui_family
                                font.pixelSize: theme.size_label
                                font.weight: theme.weight_bold
                                font.letterSpacing: theme.label_letter_spacing
                            }

                            Repeater {
                                model: wayside.overrides

                                delegate: Text {
                                    required property var modelData

                                    Layout.fillWidth: true
                                    text: modelData.signal + ": "
                                        + modelData.message
                                    color: theme.warning
                                    font.family: theme.ui_family
                                    font.pixelSize: theme.size_label
                                    wrapMode: Text.WordWrap
                                }
                            }
                        }
                    }

                    Item { Layout.fillHeight: true }

                    AppButton {
                        Layout.fillWidth: true
                        text: qsTr("Set switch manually")
                        enabled: wayside.maintenance
                        tooltip: wayside.maintenance
                            ? qsTr("Hand-set a switch on this controller")
                            : qsTr("Available in maintenance mode only")
                        onClicked: switchDialog.open()
                    }

                    Text {
                        Layout.fillWidth: true
                        text: qsTr("Manual override is available in "
                            + "maintenance mode only.")
                        color: theme.text_muted
                        font.family: theme.ui_family
                        font.pixelSize: theme.size_label
                        wrapMode: Text.WordWrap
                    }
                }
            }
        }
    }

    SwitchDialog {
        id: switchDialog
        parent: Overlay.overlay
        switches: wayside.switches
        onApplied: function (switchId, reverse) {
            wayside.setSwitch(switchId, reverse);
        }
        onReleased: function (switchId) { wayside.releaseSwitch(switchId); }
    }

    FileDialog {
        id: fileDialog
        title: qsTr("Load a PLC program")
        nameFilters: [qsTr("PLC programs (*.plc)"), qsTr("All files (*)")]
        // Python reads the file: the view only says which one.
        onAccepted: wayside.loadProgramFromUrl(selectedFile)
    }
}
