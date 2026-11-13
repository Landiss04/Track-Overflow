// Engineer-only Kp/Ki tuning, shown over the cab when USER is Engineer.
// This is an in-canvas overlay rather than a QtQuick.Controls Popup: a Popup
// is reparented to the window overlay, which sits outside the scaled design
// canvas, so it would not scale with the window.
import QtQuick
import QtQuick.Layouts
import "components"

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

    Rectangle {
        id: dialog

        anchors.centerIn: parent
        width: 520
        height: column.implicitHeight + 2 * theme.space_5
        color: theme.bg_surface
        radius: theme.radius_lg
        border.color: theme.border
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
                text: "Adjust the pending values, then apply them. The train "
                    + "keeps using the values marked In use until you do."
            }

            ColumnLayout {
                Layout.fillWidth: true
                spacing: theme.space_2

                FieldLabel { text: "STEP SIZE" }

                SegmentedToggle {
                    Layout.fillWidth: true
                    options: root.steps.map(function (step) { return step.toFixed(3); })
                    currentIndex: root.stepIndex()
                    onActivated: function (index) {
                        controller.setGainStep(root.steps[index]);
                    }
                }
            }

            GainStepper {
                Layout.fillWidth: true
                label: "Kp"
                value: root.snapshot.kp
                inUse: root.snapshot.kp_in_use
                onStepped: function (direction) { controller.adjustKp(direction); }
            }

            GainStepper {
                Layout.fillWidth: true
                label: "Ki"
                value: root.snapshot.ki
                inUse: root.snapshot.ki_in_use
                onStepped: function (direction) { controller.adjustKi(direction); }
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
                    onClicked: controller.applyGains()
                }
            }
        }
    }
}
