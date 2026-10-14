// Track Controller application window: tab bar, header, view switcher.
import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Dialogs
import QtQuick.Layouts
import QtQuick.Window
import "components"

ApplicationWindow {
    id: window

    readonly property var controller: wayside.controller

    visible: true
    width: 1440
    height: 926
    minimumWidth: 1100
    minimumHeight: 720
    title: qsTr("Track Controller — ") + wayside.selectedController
    color: theme.bg_app

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        // --- tab bar ---------------------------------------------------
        Rectangle {
            Layout.fillWidth: true
            implicitHeight: theme.control_h_md
            color: theme.bg_sunken

            Rectangle {
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.bottom: parent.bottom
                implicitHeight: 1
                color: theme.border
            }

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: theme.space_4
                spacing: theme.space_1

                Repeater {
                    model: [qsTr("Program"), qsTr("View")]

                    delegate: Rectangle {
                        required property int index
                        required property string modelData

                        readonly property bool selected: index === wayside.activeTab

                        implicitWidth: tabLabel.implicitWidth + 2 * theme.space_4
                        implicitHeight: theme.control_h_md - theme.space_1
                        color: selected ? theme.bg_surface : "transparent"
                        border.color: selected ? theme.border : "transparent"
                        border.width: selected ? 1 : 0
                        radius: theme.radius_sm

                        Text {
                            id: tabLabel
                            anchors.centerIn: parent
                            text: modelData
                            color: parent.selected
                                ? theme.text_primary : theme.text_secondary
                            font.family: theme.ui_family
                            font.pixelSize: theme.size_small
                            font.weight: theme.weight_bold
                        }

                        MouseArea {
                            anchors.fill: parent
                            cursorShape: Qt.PointingHandCursor
                            onClicked: wayside.setActiveTab(index)
                        }
                    }
                }

                Item { Layout.fillWidth: true }
            }
        }

        // --- header ----------------------------------------------------
        Rectangle {
            Layout.fillWidth: true
            implicitHeight: 64
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
                anchors.leftMargin: theme.space_5
                anchors.rightMargin: theme.space_5
                spacing: theme.space_4

                // The title elides rather than pushing the controls: at
                // the minimum window width the selectors and the clock
                // matter more than the module name.
                ColumnLayout {
                    Layout.maximumWidth: 220
                    spacing: 2

                    Text {
                        Layout.fillWidth: true
                        text: qsTr("Track Controller")
                        color: theme.text_primary
                        font.family: theme.ui_family
                        font.pixelSize: theme.size_h3
                        font.weight: theme.weight_bold
                        elide: Text.ElideRight
                    }

                    Text {
                        Layout.fillWidth: true
                        text: wayside.activeTab === 0
                            ? qsTr("PLC program — wayside authoring")
                            : qsTr("View — wayside state")
                        color: theme.text_muted
                        font.family: theme.ui_family
                        font.pixelSize: theme.size_label
                        font.letterSpacing: theme.label_letter_spacing
                        elide: Text.ElideRight
                    }
                }

                Item { Layout.fillWidth: true }

                // Controller picker. One UI stands in for every wayside,
                // so which one is selected is the most consequential
                // thing on the header and stays visible on both tabs.
                RowLayout {
                    spacing: theme.space_2

                    FieldLabel { text: qsTr("Controller") }

                    ComboBox {
                        id: controllerBox
                        implicitWidth: 190
                        model: wayside.controllers.rows.map(function (item) {
                            return item.id + "  ·  " + item.span;
                        })
                        currentIndex: wayside.controllers.rows.findIndex(
                            function (item) { return item.selected; })
                        onActivated: function (index) {
                            wayside.selectController(
                                wayside.controllers.rows[index].id);
                        }
                    }
                }

                RowLayout {
                    spacing: theme.space_2

                    FieldLabel { text: qsTr("Line") }

                    ComboBox {
                        implicitWidth: 140
                        model: wayside.lines.rows.map(function (item) {
                            return item.name;
                        })
                        currentIndex: wayside.lines.rows.findIndex(
                            function (item) { return item.selected; })
                        onActivated: function (index) {
                            wayside.selectLine(wayside.lines.rows[index].name);
                        }
                    }
                }

                // The track configuration is the controller's one piece
                // of fixed setup, so loading it is a deliberate act that
                // asks before it replaces anything.
                AppButton {
                    text: qsTr("Load track…")
                    size: "small"
                    tooltip: qsTr("Load a track layout and divide it among "
                        + "wayside controllers")
                    onClicked: trackFile.open()
                }

                // Maintenance mode belongs to the CTC Office. It is shown
                // here and cannot be changed from this window.
                RowLayout {
                    spacing: theme.space_2

                    FieldLabel { text: qsTr("Mode") }

                    StatusBadge {
                        label: wayside.maintenance
                            ? qsTr("Maintenance · CTC")
                            : qsTr("Automatic")
                        variant: wayside.maintenance ? "warning" : "ok"
                    }
                }

                // A test UI owns the physical inputs while it is
                // connected, so say so: the programmer must not mistake
                // stimulated occupancy for the stand-in simulation.
                StatusBadge {
                    label: qsTr("Test link")
                    variant: "info"
                    visible: wayside.externalControl
                }

                // Read-only. The clock is the harness's and the CTC sets
                // it (D017); this UI only says what state it is in.
                StatusBadge {
                    label: qsTr("Paused")
                    variant: "warning"
                    visible: wayside.clockPaused
                }

                StatusBadge {
                    label: qsTr("10×")
                    variant: "info"
                    visible: wayside.clockSpeed === 10
                }

                MonoText {
                    text: wayside.clock
                    color: theme.text_primary
                    font.pixelSize: theme.size_h3
                    font.weight: theme.weight_bold
                }
            }
        }

        StackLayout {
            id: views
            objectName: "views"
            Layout.fillWidth: true
            Layout.fillHeight: true
            currentIndex: wayside.activeTab

            ProgramView { onOpenViewTab: wayside.setActiveTab(1) }
            StatusView { onOpenProgramTab: wayside.setActiveTab(0) }
        }
    }

    FileDialog {
        id: trackFile
        title: qsTr("Load a track layout")
        nameFilters: [qsTr("Track layouts (*.json)"), qsTr("All files (*)")]
        currentFolder: wayside.layoutFolder
        // Python reads and checks the file; the dialog only says which.
        onAccepted: trackConfig.openFor(selectedFile)
    }

    TrackConfigDialog {
        id: trackConfig
        parent: Overlay.overlay
    }
}
