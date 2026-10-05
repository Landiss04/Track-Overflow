// The Train Model interface bench, in its own window.
//
// Separate from the console on purpose: the two are launched from the
// home page, not navigated between, so neither can reach the other.
// Run both at once from one process (main.py --both) and the bench
// drives the console beside it; run main.py --test alone and it
// drives a controller with no console attached, which is still a
// controller.
import QtQuick
import QtQuick.Layouts
import "../../ui"
import "views"

ScaledWindow {
    id: window

    readonly property var s: controller.snapshot

    title: qsTr("Train Controller test bench")

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        ModuleHeader {
            Layout.fillWidth: true
            moduleName: qsTr("Train Controller test bench")
            instance: window.s.train_id
            mode: window.s.sim_rate > 1
                ? qsTr("%1 \u00b7 %2x speed").arg(window.s.mode_label)
                    .arg(window.s.sim_rate)
                : window.s.mode_label
            clock: window.s.clock
            faulted: window.s.emergency_brake || window.s.faulted
        }

        TestView {
            Layout.fillWidth: true
            Layout.fillHeight: true
        }
    }
}
