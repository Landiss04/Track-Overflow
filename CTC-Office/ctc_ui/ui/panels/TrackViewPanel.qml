// Track view: the Red and Green line map (TrackMap.qml), drawn from the
// course layout files. Static for now; per-block state comes later.
pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import "../../../../ui"

Panel {
    id: root

    property int lineFilterIndex: 0
    // A TrackMapModel from ctc_ui/track_map.py; the placeholder shows
    // while it is null.
    property var trackMap: null
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

    Item {
        id: mapCanvas

        Layout.fillWidth: true
        Layout.fillHeight: true

        TrackMap {
            anchors.fill: parent
            model: root.trackMap
            lineFilter: root.lineFilterIndex
        }

        EmptyState {
            anchors.centerIn: parent
            visible: root.trackMap === null
            heading: qsTr("Track map not configured")
            body: qsTr("The track layout will render here once line "
                + "geometry is configured.")
        }
    }

    // Legend. Lines differ by pattern and label, not color.
    Flow {
        Layout.fillWidth: true
        visible: root.trackMap !== null
        spacing: theme.space_4

        component LegendItem: Row {
            property alias text: legendLabel.text
            default property alias swatch: swatchSlot.data
            spacing: theme.space_2

            Item {
                id: swatchSlot
                width: 24
                height: legendLabel.height
            }

            HelperText {
                id: legendLabel
                wrapMode: Text.NoWrap
            }
        }

        component LineSwatch: Row {
            id: swatch

            property bool dashed: false
            property color tone: theme.text_secondary
            anchors.verticalCenter: parent.verticalCenter
            spacing: dashed ? 3 : 0

            Repeater {
                model: swatch.dashed ? 4 : 1
                delegate: Rectangle {
                    width: swatch.dashed ? 3 : 24
                    height: 4
                    color: swatch.tone
                }
            }
        }

        LegendItem {
            text: qsTr("Green line")
            LineSwatch { tone: theme.text_secondary }
        }
        LegendItem {
            text: qsTr("Red line")
            LineSwatch { tone: theme.text_primary; dashed: true }
        }
        LegendItem {
            text: qsTr("Station")
            Rectangle {
                anchors.centerIn: parent
                width: 10
                height: 10
                color: theme.bg_surface
                border.color: theme.text_secondary
                border.width: 1.5
            }
        }
        LegendItem {
            text: qsTr("Railway crossing")
            Rectangle {
                anchors.centerIn: parent
                width: 14
                height: 14
                color: theme.bg_surface
                border.color: theme.text_secondary
                border.width: 1.5

                Text {
                    anchors.centerIn: parent
                    text: "×"
                    color: theme.text_secondary
                    font.pixelSize: theme.size_small
                }
            }
        }
        LegendItem {
            text: qsTr("Yard")
            Rectangle {
                anchors.centerIn: parent
                width: 20
                height: 12
                color: theme.bg_sunken
                border.color: theme.text_primary
                border.width: 1.5
            }
        }
    }
}
