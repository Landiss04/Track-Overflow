// CTC Office application window. The panels read and act on the live
// CTC module through `ctc` (ctc_ui/ctc_host.py). Window-level UI state
// (mode, occupancy window, selected train) lives here.
//
// Sizing and scaling come from the shared ui/ScaledWindow.qml; __main__.py
// installs the matching aspect lock. Do not resize the window from here.
import QtQuick
import QtQuick.Layouts
import "components"
import "panels"
import "views"
import "../../../ui"

ScaledWindow {
    id: window

    // 0 = Automatic, 1 = Manual, 2 = Maintenance.
    property int modeIndex: 0
    // closed | open | docked
    property string occupancyState: "closed"
    property string selectedTrainId: ""
    // The TrackMapModel from __main__.py's `trackMap` context property,
    // named apart from TrackViewPanel.trackMap so the binding cannot
    // resolve to the panel's own property.
    readonly property var trackMapModel: trackMap
    // Modal scrim: --text-primary at 40 % alpha. The shared theme has no
    // scrim token, so it is derived here rather than hard-coded.
    readonly property color scrimBase: theme.text_primary
    readonly property color scrimColor: Qt.rgba(
        scrimBase.r, scrimBase.g, scrimBase.b, 0.4)
    readonly property bool modalOpen: occupancyState === "open"

    title: qsTr("CTC Office")

    // A selected train that is no longer known (not reported, no order)
    // clears the selection.
    Connections {
        target: ctc
        function onStateChanged() {
            if (window.selectedTrainId !== ""
                    && !ctc.trains.some(function (train) {
                        return train.train === window.selectedTrainId;
                    }))
                window.selectedTrainId = "";
        }
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        CtcHeader {
            Layout.fillWidth: true
            moduleName: qsTr("CTC Office — Dispatcher Console")
            // Fixed: the CTC has a single, named operator.
            operatorName: "Stephen Philips"
            modes: [qsTr("Automatic"), qsTr("Manual"),
                qsTr("Maintenance")]
            modeIndex: window.modeIndex
            occupancyOpen: window.occupancyState !== "closed"
            onModeActivated: function (index) {
                window.modeIndex = index;
                // Maintenance mode is the CTC's maintenance_mode output.
                ctc.setMaintenanceMode(index === 2);
            }
            onOccupancyClicked: window.occupancyState = "open"
            // simClock is the shared simulation clock from __main__.py.
            clock: simClock.timeText
            paused: simClock.paused
            speed: simClock.speed
            onPauseRequested: simClock.pause()
            onResumeRequested: simClock.resume()
            onSpeedRequested: function (speed) { simClock.setSpeed(speed); }
        }

        // Notices: a Track Controller update staged while the clock is
        // paused, and orders the CTC cancelled itself (block closed,
        // closing or failed).
        RowLayout {
            Layout.fillWidth: true
            Layout.leftMargin: theme.space_3
            Layout.rightMargin: theme.space_3
            Layout.topMargin: theme.space_3
            visible: ctc.notices.length > 0
            spacing: theme.space_3

            Callout {
                Layout.fillWidth: true
                variant: "warning"
                heading: qsTr("Notice")
                body: ctc.notices.join("\n")
            }

            AppButton {
                Layout.alignment: Qt.AlignVCenter
                variant: "secondary"
                size: "small"
                text: qsTr("Dismiss")
                onClicked: ctc.dismissNotices()
            }
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.margins: theme.space_3
            spacing: theme.space_3

            TrackViewPanel {
                id: trackView
                trackMap: window.trackMapModel
                blockStates: ctc.blockStates
                crossingStates: ctc.crossingStates
                mapTrains: ctc.mapTrains
                Layout.fillWidth: true
                Layout.fillHeight: true
                onLineFilterActivated: function (index) {
                    lineFilterIndex = index;
                }
            }

            StackLayout {
                // Pinned: wrapped text reports its unwrapped width as
                // implicit width and would otherwise crowd out the
                // track view.
                Layout.preferredWidth: 760
                Layout.minimumWidth: 760
                Layout.maximumWidth: 760
                Layout.fillHeight: true
                currentIndex: window.modeIndex

                AutomaticView {
                    host: ctc
                    selectedTrainId: window.selectedTrainId
                    scheduleFile: ctc.scheduleFile
                    scheduleError: ctc.scheduleError
                    departures: ctc.departures
                    onClearSelectionRequested: window.selectedTrainId = ""
                    onScheduleFileSelected: function (fileUrl) {
                        ctc.loadSchedule(fileUrl);
                    }
                }

                ManualView {
                    host: ctc
                    selectedTrainId: window.selectedTrainId
                    onClearSelectionRequested: window.selectedTrainId = ""
                }

                MaintenanceView { host: ctc }
            }
        }
    }

    OccupancyDock {
        x: trackView.x + theme.space_7
        anchors.bottom: parent.bottom
        anchors.bottomMargin: theme.space_7
        width: 360
        summary: ctc.trains.length === 1 ? qsTr("1 train")
            : qsTr("%1 trains").arg(ctc.trains.length)
        visible: window.occupancyState === "docked"
        onExpandRequested: window.occupancyState = "open"
        onCloseRequested: window.occupancyState = "closed"
    }

    // Modal scrim: swallows clicks behind the open occupancy window.
    // The header sits under it, so it cannot be reopened while open.
    Rectangle {
        anchors.fill: parent
        color: window.scrimColor
        visible: window.modalOpen

        MouseArea {
            anchors.fill: parent
            acceptedButtons: Qt.AllButtons
            onClicked: window.occupancyState = "closed"
            onWheel: function (wheel) { wheel.accepted = true; }
        }
    }

    OccupancyWindow {
        width: 912
        height: 516
        anchors.centerIn: parent
        trains: ctc.trains
        visible: window.occupancyState === "open"
        onMinimizeRequested: window.occupancyState = "docked"
        onCloseRequested: window.occupancyState = "closed"
        onTrainSelected: function (trainId) {
            window.selectedTrainId = trainId;
            window.occupancyState = "docked";
        }
    }
}
