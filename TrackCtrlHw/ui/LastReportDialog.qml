import QtQuick
import QtQuick.Layouts

import "components"
import "../../ui" as Shared

// The last report the wayside on screen sent to the CTC Office. A report is
// a dictionary: each key is a block (line, section, block number), each
// value that block's state. Opened from the CTC uplink's View button.
ModalDialog {
    id: root

    property var model: null
    property string waysideName: ""
    property string sentText: ""

    title: qsTr("Last report to CTC Office")
    meta: root.waysideName === "" ? "" : root.waysideName + " \u00b7 " + root.sentText
    dialogWidth: 840

    footer: Shared.AppButton {
        text: qsTr("Close")
        variant: "secondary"
        onClicked: root.close()
    }

    Shared.HelperText {
        Layout.fillWidth: true
        text: qsTr("Sent every scan. Each block key maps to that block's "
            + "occupancy, switch position, signal aspect, crossing state "
            + "and failure. A failed track circuit reports occupied. "
            + "Switch, signal and crossing state are as the Track Model "
            + "reports them.")
    }

    DataTable {
        Layout.fillWidth: true
        Layout.preferredHeight: Math.min(
            headerHeight + Math.max(1, root.model ? root.model.count : 0) * rowHeight,
            headerHeight + 10 * rowHeight)
        model: root.model
        emptyText: qsTr("Nothing sent yet. The first report goes out with the first scan.")
        columns: [
            { title: qsTr("Block key"), role: "key", width: 168, mono: true },
            { title: qsTr("Occupancy"), role: "occupied", width: 96 },
            { title: qsTr("Switch"), role: "switch", width: 80 },
            { title: qsTr("Signal"), role: "signal", width: 104 },
            { title: qsTr("Crossing"), role: "crossing", fill: true },
            { title: qsTr("Failure"), role: "failure", width: 112 }
        ]
    }
}
