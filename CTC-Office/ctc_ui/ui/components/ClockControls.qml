// Simulation clock readout and controls: the time in mono at 13 px muted
// (style guide 6.7), a Paused / Running badge, Run / Pause, and the
// 1× / 10× speed toggle. Used by the CTC Office header and by the test
// UI, which controls the same clock over the clock link.
import QtQuick
import QtQuick.Layouts
import "../../../../ui"

ColumnLayout {
    id: root

    property string time: "--:--:--"
    property bool paused: true
    property int speed: 1
    // False greys out Run / Pause and the speed toggle, e.g. while the
    // test UI has no CTC Office to control.
    property bool controlsEnabled: true
    // The clock accepts only these multipliers.
    readonly property var speeds: [1, 10]

    // Requests for the shared simulation clock's pause() / resume() /
    // setSpeed().
    signal pauseRequested()
    signal resumeRequested()
    signal speedRequested(int speed)

    spacing: theme.space_1

    FieldLabel { text: qsTr("SIMULATION CLOCK") }

    RowLayout {
        Layout.preferredHeight: theme.control_h_md
        spacing: theme.space_2

        MonoText {
            text: root.time
            color: theme.text_muted
        }

        // Always shown, and both controls are sized to their wider
        // label, so the row does not shift when toggled.
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
            enabled: root.controlsEnabled
            text: root.paused ? qsTr("Run") : qsTr("Pause")
            Accessible.name: root.paused
                ? qsTr("Run the simulation")
                : qsTr("Pause the simulation")
            onClicked: root.paused ? root.resumeRequested()
                : root.pauseRequested()
        }

        SegmentedToggle {
            enabled: root.controlsEnabled
            opacity: enabled ? 1 : 0.45
            options: root.speeds.map(function (multiplier) {
                return qsTr("%1×").arg(multiplier);
            })
            currentIndex: root.speeds.indexOf(root.speed)
            Accessible.name: qsTr("Simulation speed")
            onActivated: function (index) {
                root.speedRequested(root.speeds[index]);
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
