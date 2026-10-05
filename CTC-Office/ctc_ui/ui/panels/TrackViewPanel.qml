// Track view: the Red and Green line map (TrackMap.qml), drawn from the
// course layout files, with each block's live state.
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
    // Live state from the CTC host; see TrackMap.qml.
    property var blockStates: ({})
    property var crossingStates: ({})
    // CtcHost.mapTrains: { train, line, block, fraction } per train.
    property var mapTrains: []
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
            blockStates: root.blockStates
            crossingStates: root.crossingStates
            trains: root.trackMap
                ? root.trackMap.placeTrains(root.mapTrains) : []
        }

        EmptyState {
            anchors.centerIn: parent
            visible: root.trackMap === null
            heading: qsTr("Track map not configured")
            body: qsTr("The track layout will render here once line "
                + "geometry is configured.")
        }
    }

    // Legend. Lines differ by pattern and label as well as color.
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
            // Block states are drawn heavy and round-ended on the map.
            property bool heavy: false
            property color tone: theme.line_green
            anchors.verticalCenter: parent.verticalCenter
            spacing: dashed ? 3 : 0

            Repeater {
                model: swatch.dashed ? 4 : 1
                delegate: Rectangle {
                    width: swatch.dashed ? 3 : 24
                    height: swatch.heavy ? 8 : 4
                    radius: swatch.heavy ? 4 : 0
                    color: swatch.tone
                }
            }
        }

        LegendItem {
            text: qsTr("Green line")
            LineSwatch { tone: theme.line_green }
        }
        LegendItem {
            text: qsTr("Red line")
            LineSwatch { tone: theme.line_red; dashed: true }
        }
        LegendItem {
            text: qsTr("Train (occupied block)")
            Rectangle {
                anchors.centerIn: parent
                width: 22
                height: 10
                radius: 4
                color: theme.info
            }
        }
        LegendItem {
            text: qsTr("Closed")
            LineSwatch { tone: theme.warning; heavy: true }
        }
        LegendItem {
            text: qsTr("Failure")
            LineSwatch { tone: theme.danger; heavy: true }
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
