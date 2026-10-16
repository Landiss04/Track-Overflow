// Track Model operator view, after knowledge/track_model_ui_wireframe.html.
// Everything shown is in display units, converted by track_model/state.py.
// Murphy's failure injection and loading a track from JSON are the actions
// on this page.
import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Dialogs
import QtQuick.Layouts
import "../../ui"

Item {
    id: root

    property int view: 0  // 0 = blocks, 1 = switches & lights

    // Loading replaces the line named in the file (or adds it) and
    // restarts the module, so trains and commands are cleared.
    FileDialog {
        id: loadDialog
        title: qsTr("Load track from JSON")
        nameFilters: [qsTr("Track layout (*.json)")]
        onAccepted: trackModel.loadLayout(selectedFile)
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        ModuleHeader {
            Layout.fillWidth: true
            moduleName: qsTr("Track Model")
            // The shared header's fault badge reads "E-brake", which is
            // wrong here, so track failures are counted beside the line.
            line: trackModel.failureCount > 0
                ? qsTr("%1 · %2 FAILED").arg(trackModel.line)
                    .arg(trackModel.failureCount)
                : trackModel.line
            mode: trackModel.running ? qsTr("RUNNING") : qsTr("PAUSED")
            clock: trackModel.elapsed
            navigationEntries: [qsTr("Blocks"), qsTr("Switches & Lights")]
            currentNavigationIndex: root.view
            onNavigationActivated: function (index) { root.view = index; }
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.margins: theme.space_5
            spacing: theme.space_5

            // ---- main table -------------------------------------------
            Panel {
                Layout.fillWidth: true
                Layout.fillHeight: true
                title: root.view === 0
                    ? qsTr("Block index — %1").arg(trackModel.line)
                    : qsTr("Switches, lights & heaters — %1").arg(
                        trackModel.line)

                RowLayout {
                    Layout.fillWidth: true
                    spacing: theme.space_4

                    FormField {
                        Layout.preferredWidth: 300
                        label: qsTr("Line")

                        SegmentedToggle {
                            Layout.fillWidth: true
                            options: trackModel.lines
                            currentIndex: trackModel.lines.indexOf(
                                trackModel.line)
                            onActivated: function (index) {
                                trackModel.setLine(trackModel.lines[index]);
                            }
                        }
                    }

                    ValueField {
                        Layout.fillWidth: true
                        visible: root.view === 0
                        label: qsTr("Find block or station")
                        kind: "string"
                        onCommitted: function (value) {
                            trackModel.setFilter(String(value));
                        }
                    }

                    AppButton {
                        Layout.alignment: Qt.AlignBottom
                        variant: "secondary"
                        text: qsTr("Load track…")
                        onClicked: loadDialog.open()
                    }
                }

                Callout {
                    Layout.fillWidth: true
                    visible: trackModel.loadMessage !== ""
                    variant: "warning"
                    heading: qsTr("Track not loaded")
                    body: trackModel.loadMessage
                }

                ScrollView {
                    id: tableScroll
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    clip: true
                    // The block table needs about 1146; narrower than
                    // that it scrolls sideways instead of overlapping.
                    contentWidth: Math.max(availableWidth,
                        root.view === 0 ? 1150 : 0)

                    ColumnLayout {
                        width: parent.width
                        spacing: theme.space_5

                        DataTable {
                            Layout.fillWidth: true
                            visible: root.view === 0
                            stickyFlickable: tableScroll.contentItem
                            columns: [
                                // Widths fit the header text; the table
                                // scrolls sideways before it squeezes.
                                { key: "name", label: qsTr("Block"),
                                  mono: true, width: 76 },
                                { key: "direction", label: qsTr("Dir"),
                                  mono: true, width: 110 },
                                { key: "length", label: qsTr("Len ft"),
                                  numeric: true, width: 80 },
                                { key: "grade", label: qsTr("Grade °"),
                                  numeric: true, width: 90 },
                                { key: "limit", label: qsTr("Limit mph"),
                                  numeric: true, width: 100 },
                                { key: "cmdSpeed", label: qsTr("Cmd mph"),
                                  numeric: true, width: 100 },
                                { key: "authority", label: qsTr("Auth"),
                                  numeric: true, width: 64 },
                                { key: "station", label: qsTr("Station"),
                                  width: 100 },
                                { key: "beacon", label: qsTr("Beacon"),
                                  width: 100 },
                                { key: "heat", label: qsTr("Heat"),
                                  mono: true, width: 56 },
                                { key: "occupied", label: qsTr("Occupied"),
                                  mono: true, width: 96 },
                                { key: "signal", label: qsTr("Signal"),
                                  mono: true, width: 84 },
                                { key: "failure", label: qsTr("Failure"),
                                  mono: true, width: 130 }
                            ]
                            rows: trackModel.blockRows
                            onRowActivated: function (index, row) {
                                trackModel.selectBlock(row.id);
                            }
                        }

                        DataTable {
                            Layout.fillWidth: true
                            visible: root.view === 1
                            columns: [
                                { key: "id", label: qsTr("Switch at"),
                                  mono: true, width: 130 },
                                { key: "normal", label: qsTr("Normal →"),
                                  mono: true, width: 130 },
                                { key: "reverse",
                                  label: qsTr("Reverse →"),
                                  mono: true, width: 130 },
                                { key: "position", label: qsTr("Position"),
                                  mono: true, width: 100 },
                                { key: "source", label: qsTr("Layout text"),
                                  width: 160 }
                            ]
                            rows: trackModel.switchRows
                            onRowActivated: function (index, row) {
                                trackModel.selectBlock(row.id);
                            }
                        }

                        DataTable {
                            Layout.fillWidth: true
                            visible: root.view === 1
                            columns: [
                                { key: "id", label: qsTr("Signal on"),
                                  mono: true, width: 130 },
                                { key: "aspect", label: qsTr("Showing"),
                                  mono: true, width: 130 }
                            ]
                            rows: trackModel.signalRows
                            onRowActivated: function (index, row) {
                                trackModel.selectBlock(row.id);
                            }
                        }

                        // Heaters run per section and warm its track.
                        DataTable {
                            Layout.fillWidth: true
                            visible: root.view === 1
                            columns: [
                                { key: "section", label: qsTr("Section"),
                                  mono: true, width: 130 },
                                { key: "heater", label: qsTr("Heater"),
                                  mono: true, width: 130 },
                                { key: "temp", label: qsTr("Track temp"),
                                  numeric: true, width: 130 }
                            ]
                            rows: trackModel.sectionRows
                        }
                    }
                }
            }

            // ---- side column ------------------------------------------
            ScrollView {
                Layout.preferredWidth: 400
                Layout.fillHeight: true
                clip: true
                contentWidth: availableWidth

                ColumnLayout {
                    width: parent.width
                    spacing: theme.space_5

                    Panel {
                        Layout.fillWidth: true
                        title: trackModel.selectedBlock === ""
                            ? qsTr("Selected block")
                            : qsTr("Selected — %1").arg(
                                trackModel.selectedBlock)

                        EmptyState {
                            Layout.fillWidth: true
                            visible: trackModel.selectedBlock === ""
                            heading: qsTr("No block selected")
                            body: qsTr("Pick a row in the table.")
                        }

                        // The light's colour, up front; the "Signal" row
                        // below repeats it as text.
                        RowLayout {
                            Layout.fillWidth: true
                            visible: trackModel.selectedBlock !== ""
                            spacing: theme.space_3

                            Text {
                                Layout.fillWidth: true
                                text: qsTr("Signal light")
                                color: theme.text_secondary
                                font.family: theme.ui_family
                                font.pixelSize: theme.size_small
                            }

                            StatusBadge {
                                readonly property string aspect:
                                    trackModel.selectedSignal
                                variant: aspect === "RED" ? "fault"
                                    : aspect === "YELLOW" ? "warning"
                                    : aspect === "" ? "idle" : "ok"
                                label: aspect === ""
                                    ? qsTr("No light")
                                    : aspect.replace("_", " ")
                            }
                        }

                        Repeater {
                            model: trackModel.selectedDetails

                            delegate: KeyValueRow {
                                required property var modelData
                                Layout.fillWidth: true
                                label: modelData.label
                                value: modelData.value
                            }
                        }

                        FormField {
                            Layout.fillWidth: true
                            visible: trackModel.selectedBlock !== ""
                            label: qsTr("Failure (Murphy)")

                            SegmentedToggle {
                                Layout.fillWidth: true
                                options: [qsTr("None"), qsTr("Rail"),
                                          qsTr("Circuit"), qsTr("Power")]
                                currentIndex: trackModel.selectedFailureIndex
                                onActivated: function (index) {
                                    trackModel.setSelectedFailure(
                                        trackModel.failureModes[index]);
                                }
                            }
                        }
                    }

                    Panel {
                        Layout.fillWidth: true
                        title: qsTr("Conditions")

                        ValueField {
                            Layout.fillWidth: true
                            label: qsTr("Ambient temperature (°F)")
                            kind: "float"
                            modelValue: trackModel.ambientF
                            onCommitted: function (value) {
                                trackModel.setAmbientF(value);
                            }
                        }
                    }

                    Panel {
                        Layout.fillWidth: true
                        title: qsTr("Trains on track")

                        DataTable {
                            Layout.fillWidth: true
                            columns: [
                                { key: "id", label: qsTr("Train"),
                                  mono: true, width: 70 },
                                { key: "block", label: qsTr("Block"),
                                  mono: true, width: 120 },
                                { key: "offset", label: qsTr("Off ft"),
                                  numeric: true, width: 60 },
                                { key: "speed", label: qsTr("mph"),
                                  numeric: true, width: 60 }
                            ]
                            rows: trackModel.trainRows
                            onRowActivated: function (index, row) {
                                trackModel.selectBlock(row.block);
                            }
                        }
                    }

                    Panel {
                        Layout.fillWidth: true
                        title: qsTr("Waiting at stations")

                        DataTable {
                            Layout.fillWidth: true
                            columns: [
                                { key: "station", label: qsTr("Station"),
                                  width: 200 },
                                { key: "waiting", label: qsTr("Waiting"),
                                  numeric: true, width: 80 }
                            ]
                            rows: trackModel.stationRows
                        }
                    }
                }
            }
        }
    }
}
