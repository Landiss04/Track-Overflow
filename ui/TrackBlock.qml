// Read-only occupancy indicator, style guide 6.4; actions belong to controls.
import QtQuick

Rectangle {
    id: root
    property string blockId: ""
    property string occupancy: "free" // free | occupied | closed | failure | maintenance
    readonly property string stateLabel: occupancy === "free" ? "FREE"
        : occupancy === "occupied" ? "OCCUPIED"
        : occupancy === "closed" ? "CLOSED"
        : occupancy === "failure" ? "FAILURE"
        : occupancy === "maintenance" ? "MAINT" : "UNKNOWN"

    implicitWidth: label.implicitWidth + 2 * theme.space_3
    implicitHeight: theme.control_h_md
    radius: theme.radius_sm
    color: occupancy === "free" ? theme.bg_raised
        : occupancy === "occupied" ? theme.info
        : occupancy === "closed" ? theme.warning
        : occupancy === "failure" ? theme.danger : theme.text_muted
    border.width: occupancy === "free" ? 1 : 0
    border.color: theme.border_strong
    Accessible.role: Accessible.StaticText
    Accessible.name: label.text

    MonoText {
        id: label
        anchors.centerIn: parent
        text: (root.blockId === "" ? "" : root.blockId + " · ") + root.stateLabel
        font.pixelSize: theme.size_label
        font.weight: theme.weight_bold
        color: root.occupancy === "free" ? theme.text_secondary : theme.text_inverse
    }
}
