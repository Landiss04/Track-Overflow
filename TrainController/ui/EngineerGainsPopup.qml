// Engineer-only Kp/Ki tuning, shown over the cab when USER is Engineer.
// This is an in-canvas overlay rather than a QtQuick.Controls Popup: a Popup
// is reparented to the window overlay, which sits outside the scaled design
// canvas, so it would not scale with the window. There is no shared dialog
// component, so the frame is local; its contents are shared components.
import QtQuick
import QtQuick.Layouts
import "components"
import "../../ui"

Item {
    id: root

    property var snapshot: ({})
    signal closeRequested()

    readonly property var steps: snapshot.gain_steps || []

    function stepIndex() {
        for (let i = 0; i < steps.length; ++i) {
            if (Math.abs(steps[i] - snapshot.gain_step) < 1e-9)
                return i;
        }
        return 0;
    }

    onVisibleChanged: {
        if (visible)
            dialog.forceActiveFocus();
    }

    // Scrim. Swallows every click so the cab behind cannot be operated
    // while the pop-up is open.
    Rectangle {
        anchors.fill: parent
        color: theme.text_primary
        opacity: 0.45
    }

    MouseArea {
        anchors.fill: parent
        hoverEnabled: true
        acceptedButtons: Qt.AllButtons
        onWheel: function (wheel) { wheel.accepted = true; }
    }

    // Style guide 5: dialogs carry a 1 px --border-strong.
    Rectangle {
        id: dialog

        anchors.centerIn: parent
        width: 520
        height: column.implicitHeight + 2 * theme.space_5
        color: theme.bg_surface
        radius: theme.radius_lg
        border.color: theme.border_strong
        border.width: 1
        focus: true

        Keys.onEscapePressed: root.closeRequested()

        ColumnLayout {
            id: column

            anchors.fill: parent
            anchors.margins: theme.space_5
            spacing: theme.space_4

            RowLayout {
                Layout.fillWidth: true

                Text {
                    text: qsTr("Control gains")
                    color: theme.text_primary
                    font.family: theme.ui_family
                    font.pixelSize: theme.size_h3
                    font.weight: theme.weight_bold
                }

                Item { Layout.fillWidth: true }

                StatusBadge {
                    variant: "info"
                    label: "Engineer · " + root.snapshot.train_id
                }
            }

            HelperText {
                Layout.fillWidth: true
                text: "Adjust or type the pending values, then apply them. "
                    + "The train keeps using the In use values until you do."
            }

            FormField {
                Layout.fillWidth: true
                label: "Step size"

                SegmentedToggle {
                    Layout.fillWidth: true
                    options: root.steps.map(function (step) { return step.toFixed(3); })
                    currentIndex: root.stepIndex()
                    onActivated: function (index) {
                        controller.set_gain_step(root.steps[index]);
                    }
                }
            }

            GainStepper {
                Layout.fillWidth: true
                label: "Kp"
                value: root.snapshot.kp
                inUse: root.snapshot.kp_in_use
                onStepped: function (direction) { controller.adjust_kp(direction); }
                onTyped: function (value) { controller.set_kp(value); }
            }

            GainStepper {
                Layout.fillWidth: true
                label: "Ki"
                value: root.snapshot.ki
                inUse: root.snapshot.ki_in_use
                onStepped: function (direction) { controller.adjust_ki(direction); }
                onTyped: function (value) { controller.set_ki(value); }
            }

            RowLayout {
                Layout.fillWidth: true
                Layout.topMargin: theme.space_2
                spacing: theme.space_3

                Item { Layout.fillWidth: true }

                AppButton {
                    variant: "ghost"
                    text: "Close"
                    onClicked: root.closeRequested()
                }

                AppButton {
                    variant: "primary"
                    text: "Apply gains"
                    enabled: root.snapshot.kp !== root.snapshot.kp_in_use
                        || root.snapshot.ki !== root.snapshot.ki_in_use
                    onClicked: controller.apply_gains()
                }
            }
        }
    }
}
