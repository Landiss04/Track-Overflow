// Module window header, style guide 6.7. Module name at H3, the current
// mode badge, the Train Occupancy window launcher, the operating-mode
// toggle, and the simulation clock in mono at 13 px muted.
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
    // Simulation speed badge text, e.g. "10× speed"; hidden if empty.
    property string speedLabel: ""
    property bool speedElevated: false
    // Simulation clock state. The shared clock starts paused.
    property bool paused: true
    property bool occupancyOpen: false

    signal modeActivated(int index)
    signal occupancyClicked()
    // Requests for the shared simulation clock's pause() / resume().
    signal pauseRequested()
    signal resumeRequested()

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

        ColumnLayout {
            spacing: theme.space_1

            FieldLabel { text: qsTr("SIMULATION CLOCK") }

            RowLayout {
                Layout.preferredHeight: theme.control_h_md
                spacing: theme.space_2

                StatusBadge {
                    label: root.speedLabel
                    variant: root.speedElevated ? "warning" : "idle"
                    visible: root.speedLabel !== ""
                }

                MonoText {
                    text: root.clock
                    color: theme.text_muted
                }

                // Always shown, and both controls are sized to their wider
                // label, so the header does not shift when toggled.
                StatusBadge {
                    Layout.preferredWidth: Math.max(
                        pausedBadgeSize.implicitWidth,
                        runningBadgeSize.implicitWidth)
                    label: root.paused ? qsTr("Paused") : qsTr("Running")
                    variant: root.paused ? "warning" : "ok"
                }

                AppButton {
                    Layout.preferredWidth: Math.max(
                        runButtonSize.implicitWidth,
                        pauseButtonSize.implicitWidth)
                    variant: "secondary"
                    size: "small"
                    text: root.paused ? qsTr("Run") : qsTr("Pause")
                    Accessible.name: root.paused
                        ? qsTr("Run the simulation")
                        : qsTr("Pause the simulation")
                    onClicked: root.paused ? root.resumeRequested()
                        : root.pauseRequested()
                }
            }
        }
    }

    // Unshown copies that measure each label for the fixed widths above.
    StatusBadge { id: pausedBadgeSize; visible: false; label: qsTr("Paused") }
    StatusBadge { id: runningBadgeSize; visible: false; label: qsTr("Running") }
    AppButton {
        id: runButtonSize
        visible: false
        size: "small"
        text: qsTr("Run")
    }
    AppButton {
        id: pauseButtonSize
        visible: false
        size: "small"
        text: qsTr("Pause")
    }
}
