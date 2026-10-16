// Module window header, style guide 6.7. Module name at H3, the current
// mode badge, the Train Occupancy window launcher, the operating-mode
// toggle, and the simulation clock in mono at 13 px muted with its
// Run / Pause and 1× / 10× speed controls.
import QtQuick
import QtQuick.Layouts
import "../../../../ui"

Rectangle {
    id: root

    property string moduleName: ""
    property string operatorName: ""
    property var modes: []
    property int modeIndex: 0
    property string clock: "--:--:--"
    // Simulation clock state. The shared clock starts paused at 1×.
    property bool paused: true
    property int speed: 1
    property bool occupancyOpen: false

    signal modeActivated(int index)
    signal occupancyClicked()
    // Requests for the shared simulation clock's pause() / resume() /
    // setSpeed().
    signal pauseRequested()
    signal resumeRequested()
    signal speedRequested(int speed)

    readonly property string modeName: modes.length > modeIndex
        ? modes[modeIndex] : ""

    implicitHeight: theme.control_h_lg + 2 * theme.space_3
    color: theme.bg_raised

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
        spacing: theme.space_5

        ColumnLayout {
            spacing: 0

            RowLayout {
                spacing: theme.space_3

                Text {
                    text: root.moduleName
                    color: theme.text_primary
                    font.family: theme.ui_family
                    font.pixelSize: theme.size_h3
                    font.weight: theme.weight_bold
                }

                StatusBadge {
                    label: root.modeName
                    // Automatic is normal operation; manual control is
                    // informational; maintenance is a caution state.
                    variant: root.modeIndex === 0 ? "ok"
                        : root.modeIndex === 1 ? "info" : "warning"
                    visible: root.modeName !== ""
                }
            }

            HelperText {
                text: qsTr("Operator: %1").arg(
                    root.operatorName === "" ? "—" : root.operatorName)
                color: theme.text_muted
            }
        }

        Item { Layout.fillWidth: true }

        ColumnLayout {
            spacing: theme.space_1

            FieldLabel { text: qsTr("WINDOWS") }

            RowLayout {
                spacing: theme.space_2

                AppButton {
                    variant: "secondary"
                    text: qsTr("Train occupancy")
                    Accessible.description: root.occupancyOpen
                        ? qsTr("Window is open") : qsTr("Window is closed")
                    onClicked: root.occupancyClicked()
                }
            }
        }

        ColumnLayout {
            spacing: theme.space_1

            FieldLabel { text: qsTr("OPERATING MODE") }

            SegmentedToggle {
                options: root.modes
                currentIndex: root.modeIndex
                onActivated: function (index) { root.modeActivated(index); }
            }
        }

        Rectangle {
            implicitWidth: 1
            implicitHeight: theme.control_h_lg
            color: theme.border
        }

        ClockControls {
            time: root.clock
            paused: root.paused
            speed: root.speed
            onPauseRequested: root.pauseRequested()
            onResumeRequested: root.resumeRequested()
            onSpeedRequested: function (speed) { root.speedRequested(speed); }
        }
    }
}
