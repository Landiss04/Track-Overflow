// Module application window with the shared scaling behavior. Every module
// uses this so all windows resize identically; see documents/SCALING_GUIDE.md.
//
// The content is laid out once on a fixed reference canvas (1440 x 900,
// 16:10) and the whole canvas is scaled uniformly with the window. Any
// window shape that is not 16:10 (maximized, snapped, fullscreen, non-
// Windows platforms) is letterboxed around the centered canvas.
//
// On Windows, the host must also call ui.aspect_lock.install_window_scaling
// after loading the QML. That keeps the window at 16:10 during a drag and
// holds it at the minimum instead of letting it snap. Never resize the
// window from QML (onWidthChanged, timers): see the scaling guide.
//
// Usage:
//     ScaledWindow {
//         title: qsTr("CTC Office")
//         ColumnLayout { anchors.fill: parent ... }   // fills the canvas
//     }
import QtQuick
import QtQuick.Controls.Basic

ApplicationWindow {
    id: window

    readonly property int referenceWidth: 1440
    readonly property int referenceHeight: 900
    readonly property real canvasScale: Math.min(
        width / referenceWidth, height / referenceHeight)
    // The fixed-size canvas, for items that must anchor to it explicitly.
    readonly property alias canvas: designCanvas
    // Children declared inside a ScaledWindow are placed on the canvas.
    default property alias content: designCanvas.data

    visible: true
    width: referenceWidth
    height: referenceHeight
    // Half the reference canvas, 720 x 450, which keeps 16:10.
    minimumWidth: referenceWidth / 2
    minimumHeight: referenceHeight / 2
    color: theme.bg_app

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
    }
}
