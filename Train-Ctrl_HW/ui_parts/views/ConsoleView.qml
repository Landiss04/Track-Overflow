// The driving console: the four numbers that matter at a glance, then
// the four working columns.
import QtQuick
import QtQuick.Layouts
import "../../../ui"
import "../components"
import "../panels"

Item {
    id: root

    readonly property var s: controller.snapshot

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        NumbersDrawer {
            id: numbers
            objectName: "numbersDrawer"   // opened by main.py --check
            Layout.fillWidth: true
        }

        ColumnLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.margins: theme.space_4
            spacing: theme.space_4

            // Readable from a driving position. The numbers drawer
            // shows the same four values and more, so it stands in for
            // this row rather than pushing the panels down.
            RowLayout {
                Layout.fillWidth: true
                spacing: theme.space_4
                visible: !numbers.expanded

                HeroReadout {
                    Layout.fillWidth: true
                    label: qsTr("Your speed")
                    value: Math.round(root.s.actual_mph)
                    unit: "mph"
                }

                HeroReadout {
                    Layout.fillWidth: true
                    label: qsTr("Speed limit")
                    value: Math.round(root.s.limit_mph)
                    unit: "mph"
                }

                HeroReadout {
                    Layout.fillWidth: true
                    label: qsTr("Cabin temperature")
                    value: Math.round(root.s.cabin_temp_f)
                    unit: "\u00b0F"
                }

                // Authority is a block ID, not a distance, so this
                // names the block to stop at rather than counting feet.
                HeroReadout {
                    Layout.fillWidth: true
                    label: qsTr("Stop at")
                    value: root.s.stop_block
                    valueColor: theme.signal_red
                    unit: qsTr("block ID")
                }
            }

            // Four equal columns. Nothing in one panel can change the
            // width of another, so the console never shifts under the
            // operator's hand.
            RowLayout {
                Layout.fillWidth: true
                Layout.fillHeight: true
                spacing: theme.space_4

                SpeedPanel {
                    Layout.fillWidth: true
                    Layout.preferredWidth: 1
                    Layout.fillHeight: true
                }

                StopPanel {
                    Layout.fillWidth: true
                    Layout.preferredWidth: 1
                    Layout.fillHeight: true
                }

                CabinPanel {
                    Layout.fillWidth: true
                    Layout.preferredWidth: 1
                    Layout.fillHeight: true
                }

                ColumnLayout {
                    Layout.fillWidth: true
                    Layout.preferredWidth: 1
                    Layout.fillHeight: true
                    spacing: theme.space_4

                    AnnouncementPanel {
                        Layout.fillWidth: true
                    }

                    SignalPanel {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                    }
                }
            }
        }
    }
}
