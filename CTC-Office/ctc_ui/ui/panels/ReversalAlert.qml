// Reversal alert: a train the CTC holds because the only way round what
// blocks it (a closed or failed block, or a train that is not moving)
// means reversing, which the CTC never does. Shows the first alert of
// CtcHost.reversalAlerts; the dispatcher selects the train or dismisses.
// A plain item rather than a Popup, like OccupancyWindow.qml, so it
// stays inside the window's scale transform.
import QtQuick
import QtQuick.Layouts
import "../../../../ui"

Rectangle {
    id: root

    // CtcHost.reversalAlerts: { train, line, reverseAt, destination,
    // blockedBy } per held train.
    property var alerts: []
    readonly property var alert: alerts.length > 0 ? alerts[0] : null

    signal selectRequested(string trainId)
    signal dismissRequested(string trainId)

    visible: alert !== null
    width: 520
    height: column.implicitHeight + 2 * theme.space_5
    color: theme.bg_surface
    border.color: theme.border_strong
    border.width: 1
    radius: theme.radius_lg

    ColumnLayout {
        id: column
        anchors.fill: parent
        anchors.margins: theme.space_5
        spacing: theme.space_3

        RowLayout {
            Layout.fillWidth: true
            spacing: theme.space_3

            StatusBadge {
                variant: "warning"
                label: qsTr("Reversal needed")
            }

            Item { Layout.fillWidth: true }

            HelperText {
                visible: root.alerts.length > 1
                text: qsTr("1 of %1").arg(root.alerts.length)
            }
        }

        Text {
            Layout.fillWidth: true
            text: root.alert
                ? qsTr("%1 must reverse at %2 block %3")
                    .arg(root.alert.train).arg(root.alert.line)
                    .arg(root.alert.reverseAt)
                : ""
            color: theme.text_primary
            font.family: theme.ui_family
            font.pixelSize: theme.size_h3
            font.weight: theme.weight_bold
            wrapMode: Text.WordWrap
        }

        Text {
            Layout.fillWidth: true
            text: root.alert
                ? qsTr("%1 cannot reach block %2: %3. The only way round is "
                    + "to reverse at block %4, and the CTC does not reverse "
                    + "trains, so %1 is waiting. Reroute it, clear the way, "
                    + "or reverse it by hand.")
                    .arg(root.alert.train).arg(root.alert.destination)
                    .arg(root.alert.blockedBy).arg(root.alert.reverseAt)
                : ""
            color: theme.text_secondary
            font.family: theme.ui_family
            font.pixelSize: theme.size_body
            wrapMode: Text.WordWrap
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.topMargin: theme.space_2
            spacing: theme.space_3

            Item { Layout.fillWidth: true }

            AppButton {
                variant: "secondary"
                text: qsTr("Dismiss")
                onClicked: root.dismissRequested(root.alert.train)
            }

            AppButton {
                variant: "primary"
                text: qsTr("Select train")
                onClicked: root.selectRequested(root.alert.train)
            }
        }
    }
}
