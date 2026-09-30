// Track view. The track map is intentionally a placeholder: line
// geometry still needs configuring, so no track information is drawn.
import QtQuick
import QtQuick.Layouts
import "../components"
import "../../../../ui"

Panel {
    id: root

    property int lineFilterIndex: 0
    // Whether a track map renderer is mounted in `mapCanvas`. Zoom and fit
    // stay disabled until then.
    property bool mapAvailable: false

    signal lineFilterActivated(int index)
    signal zoomOutRequested()
    signal zoomInRequested()
    signal fitRequested()

    title: qsTr("Track view")

    headerItems: [
        SegmentedToggle {
            options: [qsTr("Both lines"), qsTr("Red"), qsTr("Green")]
            currentIndex: root.lineFilterIndex
            onActivated: function (index) { root.lineFilterActivated(index); }
        },
        AppButton {
            size: "small"
            text: "−"
            enabled: root.mapAvailable
            Accessible.name: qsTr("Zoom out")
            onClicked: root.zoomOutRequested()
        },
        AppButton {
            size: "small"
            text: "+"
            enabled: root.mapAvailable
            Accessible.name: qsTr("Zoom in")
            onClicked: root.zoomInRequested()
        },
        AppButton {
            size: "small"
            text: qsTr("Fit")
            enabled: root.mapAvailable
            onClicked: root.fitRequested()
        }
    ]

    // Track map renderer mounts here. The map legend (lines, stations,
    // crossings, occupied / failed / closed blocks) belongs directly
    // below this canvas once the renderer exists.
    Item {
        id: mapCanvas

        Layout.fillWidth: true
        Layout.fillHeight: true

        EmptyState {
            anchors.centerIn: parent
            visible: !root.mapAvailable
            heading: qsTr("Track map not configured")
            body: qsTr("The track layout will render here once line "
                + "geometry is configured.")
        }
    }
}
