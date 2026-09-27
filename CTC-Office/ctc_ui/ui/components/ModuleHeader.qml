// Module window header, style guide 6.7. Module name at H3, the current
// mode badge, the Train Occupancy window launcher, the operating-mode
// toggle, and the simulation clock in mono at 13 px muted.
import QtQuick
import QtQuick.Layouts

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
    property bool occupancyOpen: false

    signal modeActivated(int index)
    signal occupancyClicked()
    signal testHarnessClicked()

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

                AppButton {
                    variant: "secondary"
                    text: qsTr("Test harness")
                    onClicked: root.testHarnessClicked()
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
            }
        }
    }
}
