// The simulation's own controls, in two groups that do different
// jobs: on the left, which running train the bench is pointed at; in
// the middle, how to put a new one on the line; on the right, how
// fast time runs.
//
// Spawning and selecting are deliberately separate. One creates a
// train and fixes what cannot change afterwards — its id, its line
// and where its authority ends. The other picks which of the running
// trains the panels below are editing.
import QtQuick
import QtQuick.Layouts
import "../../../ui"

Rectangle {
    id: root

    readonly property var s: controller.snapshot
    property int spawnNumber: 1
    property string spawnLine: "GREEN LINE"
    property string spawnTarget: "A"

    color: theme.bg_raised
    implicitHeight: content.implicitHeight + 2 * theme.space_2
    radius: theme.radius_lg
    border.color: theme.border
    border.width: 1

    RowLayout {
        id: content
        anchors.fill: parent
        anchors.margins: theme.space_2
        anchors.leftMargin: theme.space_3
        anchors.rightMargin: theme.space_3
        spacing: theme.space_3

        // ---------------------------------------------- select
        SelectField {
            Layout.fillWidth: false
            Layout.preferredWidth: 250
            label: qsTr("Editing train")
            enabled: root.s.train_count > 0
            model: root.s.train_count > 0
                ? controller.trains
                : [{"id": "", "label": qsTr("No trains available")}]
            textRole: "label"
            valueRole: "id"
            currentIndex: Math.max(0, root.s.train_index)
            onCommitted: function (value) {
                if (value !== "")
                    controller.select_train(value);
            }
        }

        Rectangle {
            Layout.fillHeight: true
            Layout.topMargin: theme.space_1
            Layout.bottomMargin: theme.space_1
            implicitWidth: 1
            color: theme.border
        }

        // ---------------------------------------------- spawn
        ValueField {
            Layout.fillWidth: false
            Layout.preferredWidth: 110
            label: qsTr("Number")
            kind: "int"
            text: String(root.spawnNumber)
            onCommitted: function (value) { root.spawnNumber = value; }
        }

        SelectField {
            Layout.fillWidth: false
            Layout.preferredWidth: 175
            label: qsTr("Line")
            model: ["GREEN LINE", "RED LINE"]
            currentIndex: root.spawnLine === "RED LINE" ? 1 : 0
            onCommitted: function (value) { root.spawnLine = value; }
        }

        ValueField {
            Layout.fillWidth: false
            Layout.preferredWidth: 150
            label: qsTr("Stops at block")
            kind: "string"
            text: root.spawnTarget
            onCommitted: function (value) { root.spawnTarget = value; }
        }

        AppButton {
            Layout.alignment: Qt.AlignBottom
            variant: "secondary"
            text: qsTr("Spawn train")
            onClicked: controller.spawn_train(root.spawnNumber,
                                             root.spawnLine,
                                             root.spawnTarget)
        }

        HelperText {
            Layout.fillWidth: true
            Layout.alignment: Qt.AlignBottom
            Layout.bottomMargin: theme.space_1
            elide: Text.ElideRight
            text: root.s.spawn_note
        }

        // ---------------------------------------------- time
        HelperText {
            Layout.alignment: Qt.AlignBottom
            Layout.bottomMargin: theme.space_1
            text: root.s.train_count === 0
                ? qsTr("No trains yet")
                : root.s.train_count === 1
                    ? qsTr("1 train running")
                    : qsTr("%1 trains running").arg(root.s.train_count)
        }

        // The tick rate does not change; each tick advances ten times
        // the simulated seconds, so the control law keeps its
        // timestep and only the world moves faster.
        FormField {
            Layout.fillWidth: false
            Layout.preferredWidth: 150
            label: qsTr("Speed")

            SegmentedToggle {
                Layout.fillWidth: true
                options: [qsTr("1x"), qsTr("10x")]
                currentIndex: root.s.sim_rate_index
                onActivated: function (index) {
                    controller.set_sim_rate(index);
                }
            }
        }
    }
}
