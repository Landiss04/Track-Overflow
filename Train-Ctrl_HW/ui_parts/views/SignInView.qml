// Shown until an operator signs in. Nothing else is reachable, so the
// console cannot be driven by whoever walks past the cab.
import QtQuick
import "../../../ui"

Item {
    id: root

    readonly property var s: controller.snapshot
    // A train nobody has commissioned has no driver's console yet.
    readonly property bool needsGains: s.has_train && !s.gains_locked

    EmptyState {
        anchors.centerIn: parent
        heading: root.needsGains
            ? qsTr("%1 is waiting for its gains").arg(root.s.train_id)
            : qsTr("Select an operator to unlock the console")
        body: root.needsGains
            ? qsTr("Sign in as Engineer to set Kp and Ki. The driver's "
                   + "console opens once they are set.")
            : qsTr("The driver drives the train. The engineer sets the "
                   + "control gains once, before the run starts.")
    }
}
