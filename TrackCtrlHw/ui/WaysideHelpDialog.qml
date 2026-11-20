import QtQuick
import QtQuick.Layouts

import "components"
import "../../ui" as Shared

// Window-level help. Opened from the header's "?" button. The full,
// consolidated Help File for this module is TrackCtrlHw/docs/help.md; this
// dialog is a quick pointer to it plus the most-asked-about terms.
ModalDialog {
    id: root

    title: qsTr("Help \u2014 reading this window")
    dialogWidth: 640

    footer: Shared.AppButton {
        text: qsTr("Close")
        variant: "secondary"
        onClicked: root.close()
    }

    Shared.HelperText {
        Layout.fillWidth: true
        text: qsTr("Every value shown here comes from the wayside's running "
            + "PLC program, not from this window. A mismatch between a "
            + "\u201ccommanded\u201d and \u201creported\u201d value usually "
            + "means the physical device hasn't caught up yet, or has "
            + "failed to.")
    }

    Shared.KeyValueRow {
        Layout.fillWidth: true
        label: qsTr("Agreement (Switches)")
        value: qsTr("Reported position vs. commanded")
    }

    Shared.KeyValueRow {
        Layout.fillWidth: true
        label: qsTr("CTC asks")
        value: qsTr("A request only \u2014 the PLC decides")
    }

    Shared.KeyValueRow {
        Layout.fillWidth: true
        label: qsTr("Set by")
        value: qsTr("PLC program, or fail-safe default")
    }

    Shared.KeyValueRow {
        Layout.fillWidth: true
        rule: false
        label: qsTr("Channel fault")
        value: qsTr("The program's two compiled forms disagreed")
    }

    Shared.HelperText {
        Layout.fillWidth: true
        text: qsTr("Full Help File (window, PLC language, troubleshooting): "
            + "TrackCtrlHw/docs/help.md")
        color: theme.text_muted
    }
}


