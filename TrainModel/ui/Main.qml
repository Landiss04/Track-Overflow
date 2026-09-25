// Train Model application window.
import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import QtQuick.Window
import "components"

ApplicationWindow {
    id: window

    readonly property var snapshot: trainModel.snapshot
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

    visible: true
    width: referenceWidth
    height: referenceHeight
    minimumWidth: 720
    minimumHeight: 450
    title: qsTr("Train Model")
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

        // Let the native window manager finish a drag before correcting the
        // aspect ratio, avoiding geometry feedback while a title bar moves.
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

            ModuleHeader {
                Layout.fillWidth: true
                moduleName: qsTr("Train Model")
                instance: window.snapshot.train_id
                mode: window.snapshot.mode
                line: window.snapshot.line
                clock: window.snapshot.clock
                faulted: window.snapshot.emergency_brake
                navigationEntries: [qsTr("Overview"), qsTr("Test harness")]
                currentNavigationIndex: views.currentIndex
                onNavigationActivated: function (index) { views.currentIndex = index; }
            }

            // This fills the fixed reference canvas; the canvas transform
            // scales the complete design uniformly with the window.
            RowLayout {
                Layout.fillWidth: true
                Layout.fillHeight: true
                spacing: 0

                StackLayout {
                    id: views
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    currentIndex: 0

                    MainView {}
                    TestView {}
                }
            }
        }
    }
}
