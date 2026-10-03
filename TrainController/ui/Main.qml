// Train Controller application window. ScaledWindow gives every module the
// same 1440 x 900 canvas and resize behaviour (documents/SCALING_GUIDE.md).
import QtQuick
import QtQuick.Layouts
import "components"
import "../../ui"

ScaledWindow {
    id: window

    readonly property var snapshot: controller.snapshot
    readonly property var userOptions: ["Driver", "Engineer"]
    readonly property var modeOptions: ["Automatic", "Manual"]

    title: qsTr("Train Controller")

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        // Style guide 6.7: name and instance, mode badge, a persistent
        // E-brake fault badge while the emergency brake is on, and clock.
        ModuleHeader {
            Layout.fillWidth: true
            moduleName: qsTr("Train Controller")
            instance: window.snapshot.train_id
            mode: window.snapshot.mode
            line: window.snapshot.line
            clock: window.snapshot.clock
            faulted: window.snapshot.emergency_brake
        }

        // Console selectors. ModuleHeader has no slot for controls, so they
        // sit in a strip directly beneath it.
        Rectangle {
            Layout.fillWidth: true
            implicitHeight: strip.implicitHeight + 2 * theme.space_2
            color: theme.bg_surface

            Rectangle {
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.bottom: parent.bottom
                height: 1
                color: theme.border
            }

            RowLayout {
                id: strip

                anchors.fill: parent
                anchors.leftMargin: theme.space_5
                anchors.rightMargin: theme.space_5
                anchors.topMargin: theme.space_2
                anchors.bottomMargin: theme.space_2
                spacing: theme.space_5

                SelectField {
                    Layout.preferredWidth: 200
                    Layout.maximumWidth: 200
                    label: "Train"
                    model: window.snapshot.train_ids
                }

                Item { Layout.fillWidth: true }

                FormField {
                    Layout.fillWidth: false
                    label: "User"

                    SegmentedToggle {
                        options: window.userOptions
                        currentIndex: window.userOptions.indexOf(window.snapshot.user_role)
                        onActivated: function (index) {
                            controller.set_user(window.userOptions[index]);
                        }
                    }
                }

                FormField {
                    Layout.fillWidth: false
                    label: "Mode"

                    SegmentedToggle {
                        options: window.modeOptions
                        currentIndex: window.modeOptions.indexOf(window.snapshot.mode)
                        onActivated: function (index) {
                            controller.set_mode(window.modeOptions[index]);
                        }
                    }
                }
            }
        }

        CabView {
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.margins: theme.space_3
        }
    }

    EngineerGainsPopup {
        anchors.fill: parent
        visible: window.snapshot.user_role === "Engineer"
        snapshot: window.snapshot
        onCloseRequested: controller.set_user("Driver")
    }
}
