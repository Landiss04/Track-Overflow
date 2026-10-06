// Shown until an operator signs in. Nothing else is reachable, so the
// console cannot be driven by whoever walks past the cab.
import QtQuick
import "../../../ui"

Item {
    id: root

    EmptyState {
        anchors.centerIn: parent
        heading: qsTr("Select an operator to unlock the console")
        body: qsTr("The driver drives the train. The engineer sets the "
                   + "control gains once, before the run starts.")
    }
}
