// View tab: line -> controller -> that controller's blocks and outputs.
//
// Three columns that narrow left to right, so the selection path stays
// on screen: which line, which wayside, and what that wayside is
// currently driving onto the track.
import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "components"

Item {
    id: root

    signal openProgramTab()

    readonly property var controller: wayside.controller

    RowLayout {
        anchors.fill: parent
        anchors.margins: theme.space_3
        spacing: theme.space_3

        // --- lines -----------------------------------------------------
        // Pinned widths: the drill-down columns stay put so the third
        // column absorbs every resize, and wrapping help text cannot
        // widen a column past its design size.
        Panel {
            Layout.preferredWidth: 208
            Layout.minimumWidth: 208
            Layout.maximumWidth: 208
            Layout.fillHeight: true
            title: qsTr("Line")

            ColumnLayout {
                anchors.fill: parent
                spacing: 0

                Repeater {
                    model: wayside.lines

                    delegate: Rectangle {
                        required property var modelData

                        Layout.fillWidth: true
                        implicitHeight: theme.control_h_lg
                        color: modelData.selected
                            ? theme.accent_subtle : "transparent"

                        Rectangle {
                            anchors.left: parent.left
                            anchors.top: parent.top
                            anchors.bottom: parent.bottom
                            implicitWidth: 3
                            color: parent.modelData.color
                            visible: parent.modelData.selected
                        }

                        RowLayout {
                            anchors.fill: parent
                            anchors.leftMargin: theme.space_3
                            anchors.rightMargin: theme.space_3
                            spacing: theme.space_2

                            Rectangle {
                                implicitWidth: 10
                                implicitHeight: 10
                                radius: 2
                                color: parent.parent.modelData.color
                            }

                            Text {
                                text: parent.parent.modelData.name
                                color: theme.text_primary
                                font.family: theme.ui_family
                                font.pixelSize: theme.size_small
                                font.weight: parent.parent.modelData.selected
                                    ? theme.weight_bold : theme.weight_regular
                                Layout.fillWidth: true
                            }

                            MonoText {
                                text: parent.parent.modelData.controllers
                                color: theme.text_muted
                            }
                        }

                        MouseArea {
                            anchors.fill: parent
                            cursorShape: Qt.PointingHandCursor
                            onClicked: wayside.selectLine(parent.modelData.name)
                        }
                    }
                }

                Rectangle {
                    Layout.fillWidth: true
                    Layout.topMargin: theme.space_2
                    implicitHeight: 1
                    color: theme.border
                }

                ColumnLayout {
                    Layout.fillWidth: true
                    Layout.margins: theme.space_3
                    spacing: theme.space_2

                    Text {
                        text: wayside.selectedLine.toUpperCase()
                            + qsTr(" TOTALS")
                        color: theme.text_muted
                        font.family: theme.ui_family
                        font.pixelSize: theme.size_label
                        font.letterSpacing: theme.label_letter_spacing
                    }

                    Repeater {
                        model: {
                            const line = wayside.lines.find(function (item) {
                                return item.selected; });
                            if (line === undefined) return [];
                            return [
                                { label: qsTr("Blocks"), value: line.blocks },
                                { label: qsTr("Occupied"), value: line.occupied },
                                { label: qsTr("Closed"), value: line.closed },
                                { label: qsTr("Trains"), value: line.trains },
                                { label: qsTr("Controllers"),
                                  value: line.controllers },
                            ];
                        }

                        delegate: SignalRow {
                            required property var modelData

                            Layout.fillWidth: true
                            label: modelData.label
                            value: String(modelData.value)
                        }
                    }
                }

                Item { Layout.fillHeight: true }
            }
        }

        // --- controllers on that line ----------------------------------
        Panel {
            Layout.preferredWidth: 276
            Layout.minimumWidth: 276
            Layout.maximumWidth: 276
            Layout.fillHeight: true
            title: qsTr("Track controllers")
            status: wayside.controllers.length + qsTr(" ON LINE")

            ColumnLayout {
                anchors.fill: parent
                spacing: 0

                RowLayout {
                    Layout.fillWidth: true
                    Layout.margins: theme.space_3
                    Layout.bottomMargin: theme.space_1
                    spacing: theme.space_2

                    Text {
                        text: qsTr("ID")
                        color: theme.text_muted
                        font.family: theme.ui_family
                        font.pixelSize: theme.size_label
                        font.letterSpacing: theme.label_letter_spacing
                        Layout.preferredWidth: 62
                    }

                    Text {
                        text: qsTr("BLOCKS")
                        color: theme.text_muted
                        font.family: theme.ui_family
                        font.pixelSize: theme.size_label
                        font.letterSpacing: theme.label_letter_spacing
                        Layout.fillWidth: true
                    }

                    Text {
                        text: qsTr("OCC")
                        color: theme.text_muted
                        font.family: theme.ui_family
                        font.pixelSize: theme.size_label
                        font.letterSpacing: theme.label_letter_spacing
                    }
                }

                ListView {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    clip: true
                    model: wayside.controllers
                    boundsBehavior: Flickable.StopAtBounds

                    delegate: Rectangle {
                        required property var modelData

                        width: ListView.view.width
                        implicitHeight: theme.control_h_md
                        color: modelData.selected
                            ? theme.accent_subtle : "transparent"

                        Rectangle {
                            anchors.left: parent.left
                            anchors.top: parent.top
                            anchors.bottom: parent.bottom
                            implicitWidth: 3
                            color: theme.accent
                            visible: parent.modelData.selected
                        }

                        RowLayout {
                            anchors.fill: parent
                            anchors.leftMargin: theme.space_3
                            anchors.rightMargin: theme.space_3
                            spacing: theme.space_2

                            MonoText {
                                text: parent.parent.modelData.id
                                color: theme.text_primary
                                font.weight: parent.parent.modelData.selected
                                    ? theme.weight_bold : theme.weight_regular
                                Layout.preferredWidth: 62
                            }

                            MonoText {
                                text: parent.parent.modelData.span
                                color: theme.text_secondary
                                elide: Text.ElideRight
                                Layout.fillWidth: true
                            }

                            StatusBadge {
                                label: qsTr("MAINT")
                                variant: "warning"
                                visible: parent.parent.modelData.maintenance
                            }

                            MonoText {
                                text: parent.parent.modelData.occupied
                                color: parent.parent.modelData.occupied > 0
                                    ? theme.text_primary : theme.text_muted
                            }
                        }

                        MouseArea {
                            anchors.fill: parent
                            cursorShape: Qt.PointingHandCursor
                            onClicked: wayside.selectController(
                                parent.modelData.id)
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
                    text: qsTr("Selecting a controller shows the blocks it "
                        + "owns and the outputs its committed program is "
                        + "driving.")
                    color: theme.text_muted
                    font.family: theme.ui_family
                    font.pixelSize: theme.size_label
                    wrapMode: Text.WordWrap
                }
            }
        }

        // --- the selected controller -----------------------------------
        ColumnLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.minimumWidth: 480
            spacing: theme.space_3

            Rectangle {
                Layout.fillWidth: true
                implicitHeight: summaryRow.implicitHeight + 2 * theme.space_3
                color: wayside.maintenance ? theme.warning_bg : theme.bg_sunken
                border.color: wayside.maintenance ? theme.warning : theme.border
                border.width: 1
                radius: theme.radius_md

                RowLayout {
                    id: summaryRow
                    anchors.fill: parent
                    anchors.margins: theme.space_3
                    spacing: theme.space_3

                    Text {
                        text: root.controller.id + qsTr(" · ")
                            + root.controller.mode.toUpperCase()
                            + qsTr(" · ITERATION #")
                            + root.controller.iteration
                        color: wayside.maintenance
                            ? theme.warning : theme.text_primary
                        font.family: theme.ui_family
                        font.pixelSize: theme.size_label
                        font.weight: theme.weight_bold
                        font.letterSpacing: theme.label_letter_spacing
                    }

                    Text {
                        Layout.fillWidth: true
                        text: wayside.maintenance
                            ? qsTr("Manual switch control is enabled and this "
                                + "controller is commanding zero authority.")
                            : qsTr("Outputs below are produced by the "
                                + "committed program. Manual control is "
                                + "disabled until the controller is put in "
                                + "maintenance mode.")
                        color: wayside.maintenance
                            ? theme.warning : theme.text_secondary
                        font.family: theme.ui_family
                        font.pixelSize: theme.size_label
                        wrapMode: Text.WordWrap
                    }
                }
            }

            // --- block occupancy ---------------------------------------
            Panel {
                Layout.fillWidth: true
                Layout.preferredHeight: 190
                title: qsTr("Block occupancy — train presence from the "
                    + "Track Model")
                status: root.controller.block_count + qsTr(" BLOCKS · ")
                    + wayside.blocks.filter(function (block) {
                        return block.occupied; }).length + qsTr(" OCCUPIED")

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: theme.space_3
                    spacing: theme.space_2

                    GridLayout {
                        Layout.fillWidth: true
                        columns: 13
                        columnSpacing: theme.space_1
                        rowSpacing: theme.space_1

                        Repeater {
                            model: wayside.blocks

                            delegate: BlockTile {
                                required property var modelData

                                Layout.fillWidth: true
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
                        text: qsTr("Filled = occupied. Hatched = closed for "
                            + "maintenance and removed from every authority "
                            + "this controller issues. Occupancy for these "
                            + "blocks is what it reports back to the CTC.")
                        color: theme.text_muted
                        font.family: theme.ui_family
                        font.pixelSize: theme.size_label
                        wrapMode: Text.WordWrap
                    }

                    Item { Layout.fillHeight: true }
                }
            }

            // --- outputs and the program running -----------------------
            RowLayout {
                Layout.fillWidth: true
                Layout.fillHeight: true
                spacing: theme.space_3

                Panel {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    title: qsTr("Commanded outputs to track")
                    status: qsTr("ITER #") + root.controller.iteration

                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: theme.space_3
                        spacing: theme.space_3

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

                        Rectangle {
                            Layout.fillWidth: true
                            implicitHeight: 1
                            color: theme.border
                        }

                        // What the CTC asked for, beside what the wayside
                        // actually issued: the gap is the whole job.
                        SignalRow {
                            Layout.fillWidth: true
                            label: qsTr("CTC suggested speed")
                            value: root.controller.suggested_speed.toFixed(0)
                                + qsTr(" MPH")
                        }

                        SignalRow {
                            Layout.fillWidth: true
                            label: qsTr("CTC suggested authority")
                            value: root.controller.suggested_authority
                                + qsTr(" blocks")
                        }

                        Rectangle {
                            Layout.fillWidth: true
                            Layout.preferredHeight: overrideList.implicitHeight
                                + 2 * theme.space_2
                            visible: wayside.overrides.length > 0
                            color: theme.warning_bg
                            border.color: theme.warning
                            border.width: 1
                            radius: theme.radius_sm

                            ColumnLayout {
                                id: overrideList
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
                    }
                }

                Panel {
                    Layout.preferredWidth: 312
                    Layout.minimumWidth: 312
                    Layout.maximumWidth: 312
                    Layout.fillHeight: true
                    title: qsTr("Program on this controller")
                    status: "#" + root.controller.iteration

                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: theme.space_3
                        spacing: theme.space_3

                        SignalRow {
                            Layout.fillWidth: true
                            label: qsTr("File")
                            value: root.controller.file
                        }

                        SignalRow {
                            Layout.fillWidth: true
                            label: qsTr("Committed")
                            value: root.controller.committed_at
                        }

                        SignalRow {
                            Layout.fillWidth: true
                            label: qsTr("Span")
                            value: root.controller.span
                        }

                        SignalRow {
                            Layout.fillWidth: true
                            label: qsTr("Mode")
                            value: root.controller.mode
                        }

                        AppButton {
                            Layout.fillWidth: true
                            Layout.topMargin: theme.space_2
                            text: qsTr("Open in Program tab")
                            variant: "primary"
                            onClicked: root.openProgramTab()
                        }

                        AppButton {
                            Layout.fillWidth: true
                            text: wayside.maintenance
                                ? qsTr("Set switch manually")
                                : qsTr("Enter maintenance to set switches")
                            enabled: wayside.maintenance
                            onClicked: viewSwitchDialog.open()
                        }

                        Item { Layout.fillHeight: true }
                    }
                }
            }
        }
    }

    SwitchDialog {
        id: viewSwitchDialog
        parent: Overlay.overlay
        switches: wayside.switches
        onApplied: function (switchId, reverse) {
            wayside.setSwitch(switchId, reverse);
        }
        onReleased: function (switchId) { wayside.releaseSwitch(switchId); }
    }
}
