// Who is at the console, which mode it is in, and which train it is
// pointed at. Everything below this bar depends on these three.
import QtQuick
import QtQuick.Layouts
import "../../../ui"
import "../components"

Rectangle {
    id: root

    readonly property var s: controller.snapshot

    color: theme.bg_raised
    implicitHeight: content.implicitHeight + 2 * theme.space_3

    Rectangle {
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        implicitHeight: 1
        color: theme.border
    }

    RowLayout {
        id: content
        anchors.fill: parent
        anchors.topMargin: theme.space_3
        anchors.bottomMargin: theme.space_3
        anchors.leftMargin: theme.space_5
        anchors.rightMargin: theme.space_5
        spacing: theme.space_5

        // All three sit on one baseline: every field is a Label-token
        // caption over a control of the same height, top-aligned.
        // The engineer option stays visible once the gains are set and
        // selecting it is simply refused, so nothing moves.
        FormField {
            Layout.alignment: Qt.AlignTop
            Layout.preferredWidth: 240
            label: qsTr("Operator")

            SegmentedToggle {
                Layout.fillWidth: true
                options: [qsTr("Driver"), qsTr("Engineer")]
                currentIndex: root.s.operator_index
                onActivated: function (index) {
                    controller.select_operator(index);
                }
            }
        }

        FormField {
            Layout.alignment: Qt.AlignTop
            Layout.preferredWidth: 240
            label: qsTr("Operating mode")
            enabled: root.s.signed_in

            SegmentedToggle {
                Layout.fillWidth: true
                enabled: root.s.signed_in
                options: [qsTr("Automatic"), qsTr("Manual")]
                currentIndex: root.s.manual ? 1 : 0
                onActivated: function (index) {
                    controller.set_manual(index === 1);
                }
            }
        }

        Item { Layout.fillWidth: true }

        // Whether this train has been commissioned. Gains are per
        // train, so a console pointed at a fresh one says so rather
        // than leaving the driver to wonder why nothing moves.
        StatusBadge {
            Layout.alignment: Qt.AlignBottom
            Layout.bottomMargin: theme.space_1
            label: root.s.gains_locked ? qsTr("Gains set")
                                       : qsTr("Gains missing")
            variant: root.s.gains_locked ? "ok" : "warning"
        }

        TrainPicker {
            objectName: "trainPicker"
            Layout.preferredWidth: 280
            Layout.alignment: Qt.AlignTop
            enabled: root.s.signed_in && root.s.train_count > 0
            label: qsTr("Current selected train")
            trains: controller.trains
            currentId: root.s.has_train ? root.s.train_id : ""
            onPicked: function (trainId) { controller.select_train(trainId); }
        }
    }
}
