// CTC Office application window. UI only: there is no backend yet, so
// every panel shows its empty state and actions emit signals nobody
// handles. Window-level UI state (mode, occupancy window) lives here.
import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import QtQuick.Window
import "components"
import "panels"
import "views"

ApplicationWindow {
    id: window

    readonly property int referenceWidth: 1440
    readonly property int referenceHeight: 900
    readonly property real canvasScale: Math.min(
        width / referenceWidth, height / referenceHeight)
    readonly property bool systemSized: visibility === Window.FullScreen
        || visibility === Window.Maximized
    property bool applyingAspect: false
    property string aspectDriver: "width"
    property int settledWidth: referenceWidth
    property int settledHeight: referenceHeight

    // 0 = Automatic, 1 = Manual, 2 = Maintenance.
    property int modeIndex: 0
    // closed | open | docked
    property string occupancyState: "closed"
    property string selectedTrainId: ""
    property bool testHarnessOpen: false
    // Modal scrim: --text-primary at 40 % alpha. The shared theme has no
    // scrim token, so it is derived here rather than hard-coded.
    readonly property color scrimBase: theme.text_primary
    readonly property color scrimColor: Qt.rgba(
        scrimBase.r, scrimBase.g, scrimBase.b, 0.4)
    readonly property bool modalOpen: occupancyState === "open"
        || testHarnessOpen

    visible: true
    width: referenceWidth
    height: referenceHeight
    // Half the reference canvas: 720 x 450, which keeps the 16:10 aspect
    // ratio. The OS enforces this, so the window cannot be dragged smaller.
    minimumWidth: referenceWidth / 2
    minimumHeight: referenceHeight / 2
    title: qsTr("CTC Office")
    color: theme.bg_app

    function scheduleAspectLock() {
        if (applyingAspect || systemSized)
            return;
        const widthChange = Math.abs(width - settledWidth) / 8;
        const heightChange = Math.abs(height - settledHeight) / 5;
        if (widthChange > heightChange)
            aspectDriver = "width";
        else if (heightChange > widthChange)
            aspectDriver = "height";
        aspectLockTimer.restart();
    }

    function applyAspectLock() {
        if (systemSized)
            return;
        const units = aspectDriver === "width"
            ? Math.max(minimumWidth / 8, Math.round(width / 8))
            : Math.max(minimumHeight / 5, Math.round(height / 5));
        const targetWidth = units * 8;
        const targetHeight = units * 5;
        if (width === targetWidth && height === targetHeight)
            return;
        applyingAspect = true;
        width = targetWidth;
        height = targetHeight;
        settledWidth = targetWidth;
        settledHeight = targetHeight;
        applyingAspect = false;
    }

    onWidthChanged: scheduleAspectLock()
    onHeightChanged: scheduleAspectLock()
    onVisibilityChanged: scheduleAspectLock()

    Timer {
        id: aspectLockTimer

        // Let the native window manager finish a drag before correcting
        // the aspect ratio, avoiding geometry feedback while a title bar
        // moves.
        interval: 1
        repeat: false
        onTriggered: window.applyAspectLock()
    }

    Item {
        id: designCanvas

        width: window.referenceWidth
        height: window.referenceHeight
        x: (window.width - width * window.canvasScale) / 2
        y: (window.height - height * window.canvasScale) / 2
        transform: Scale {
            origin.x: 0
            origin.y: 0
            xScale: window.canvasScale
            yScale: window.canvasScale
        }

        ColumnLayout {
            anchors.fill: parent
            spacing: 0

            CtcHeader {
                Layout.fillWidth: true
                moduleName: qsTr("CTC Office — Dispatcher Console")
                modes: [qsTr("Automatic"), qsTr("Manual"),
                    qsTr("Maintenance")]
                modeIndex: window.modeIndex
                occupancyOpen: window.occupancyState !== "closed"
                onModeActivated: function (index) {
                    window.modeIndex = index;
                }
                onOccupancyClicked: window.occupancyState = "open"
                onTestHarnessClicked: window.testHarnessOpen = true
            }

            RowLayout {
                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.margins: theme.space_3
                spacing: theme.space_3

                TrackViewPanel {
                    id: trackView
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
                        selectedTrainId: window.selectedTrainId
                        onClearSelectionRequested: window.selectedTrainId = ""
                    }

                    ManualView {
                        selectedTrainId: window.selectedTrainId
                        onClearSelectionRequested: window.selectedTrainId = ""
                    }

                    MaintenanceView {}
                }
            }
        }

        OccupancyDock {
            x: trackView.x + theme.space_7
            anchors.bottom: parent.bottom
            anchors.bottomMargin: theme.space_7
            width: 360
            visible: window.occupancyState === "docked"
            onExpandRequested: window.occupancyState = "open"
            onCloseRequested: window.occupancyState = "closed"
        }

        // Modal scrim: swallows clicks behind whichever modal is open.
        // The header sits under it, so only one modal can open at a time.
        Rectangle {
            anchors.fill: parent
            color: window.scrimColor
            visible: window.modalOpen

            MouseArea {
                anchors.fill: parent
                acceptedButtons: Qt.AllButtons
                onClicked: {
                    window.testHarnessOpen = false;
                    if (window.occupancyState === "open")
                        window.occupancyState = "closed";
                }
                onWheel: function (wheel) { wheel.accepted = true; }
            }
        }

        OccupancyWindow {
            width: 912
            height: 516
            anchors.centerIn: parent
            visible: window.occupancyState === "open"
            onMinimizeRequested: window.occupancyState = "docked"
            onCloseRequested: window.occupancyState = "closed"
            onTrainSelected: function (trainId) {
                window.selectedTrainId = trainId;
                window.occupancyState = "docked";
            }
        }

        TestHarnessWindow {
            width: 1040
            height: 640
            anchors.centerIn: parent
            visible: window.testHarnessOpen
            onCloseRequested: window.testHarnessOpen = false
        }
    }
}
