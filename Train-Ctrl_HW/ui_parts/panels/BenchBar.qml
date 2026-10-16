// The simulation's own controls, in three groups that do different
// jobs: on the left, which running train the bench is pointed at and
// removing it; in the middle, how to put a new one on the line; on
// the right, what is running and how fast time runs.
//
// Spawning and selecting are deliberately separate. One creates a
// train and fixes what cannot change afterwards — its id, its line
// and where its authority ends. The other picks which of the running
// trains the panels below are editing.
import QtQuick
import QtQuick.Layouts
import "../../../ui"
import "../components"

Rectangle {
    id: root

    readonly property var s: controller.snapshot
    property int spawnNumber: 1
    property string spawnLine: "GREEN LINE"
    property string spawnTarget: "A"
    // Removing a train is a second press: the first only arms it.
    property bool confirmRemove: false
    readonly property string selectedTrain: root.s.train_id
    onSelectedTrainChanged: confirmRemove = false

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

        // ------------------------------------- the selected train
        TrainPicker {
            objectName: "benchTrainPicker"
            Layout.fillWidth: false
            Layout.preferredWidth: 250
            label: qsTr("Editing train")
            enabled: root.s.train_count > 0
            trains: controller.trains
            currentId: root.s.has_train ? root.s.train_id : ""
            onPicked: function (trainId) { controller.select_train(trainId); }
        }

        // Beside the picker, because it acts on the train picked. Red
        // throughout so it is never mistaken for a routine control;
        // the first press only arms it.
        AppButton {
            Layout.alignment: Qt.AlignBottom
            visible: !root.confirmRemove
            enabled: root.s.has_train
            variant: "danger"
            text: qsTr("Remove train")
            onClicked: root.confirmRemove = true
        }

        AppButton {
            Layout.alignment: Qt.AlignBottom
            visible: root.confirmRemove
            variant: "danger"
            text: qsTr("Remove %1").arg(root.s.train_id)
            onClicked: {
                root.confirmRemove = false;
                controller.remove_train(root.s.train_id);
            }
        }

        AppButton {
            Layout.alignment: Qt.AlignBottom
            visible: root.confirmRemove
            variant: "ghost"
            text: qsTr("Cancel")
            onClicked: root.confirmRemove = false
        }

        Rectangle {
            Layout.fillHeight: true
            Layout.topMargin: theme.space_1
            Layout.bottomMargin: theme.space_1
            implicitWidth: 1
            color: theme.border
        }

        // ------------------------------------------ a new train
        ValueField {
            Layout.fillWidth: false
            Layout.preferredWidth: 90
            label: qsTr("Number")
            kind: "int"
            text: String(root.spawnNumber)
            onCommitted: function (value) { root.spawnNumber = value; }
        }

        SelectField {
            Layout.fillWidth: false
            Layout.preferredWidth: 160
            label: qsTr("Line")
            model: ["GREEN LINE", "RED LINE"]
            currentIndex: root.spawnLine === "RED LINE" ? 1 : 0
            onCommitted: function (value) { root.spawnLine = value; }
        }

        ValueField {
            Layout.fillWidth: false
            Layout.preferredWidth: 130
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

        Rectangle {
            Layout.fillHeight: true
            Layout.topMargin: theme.space_1
            Layout.bottomMargin: theme.space_1
            implicitWidth: 1
            color: theme.border
        }

        // --------------------------------------- status and time
        // One line, elided: how many trains run, and what the last
        // spawn or removal did. A wrapped line would grow the bar and
        // push the bench's last rows off the window.
        HelperText {
            Layout.fillWidth: true
            Layout.alignment: Qt.AlignBottom
            Layout.bottomMargin: theme.space_2
            wrapMode: Text.NoWrap
            elide: Text.ElideRight
            text: (root.s.train_count === 0 ? qsTr("No trains yet")
                : root.s.train_count === 1 ? qsTr("1 train running")
                : qsTr("%1 trains running").arg(root.s.train_count))
                + (root.s.spawn_note !== ""
                   ? " · " + root.s.spawn_note : "")
        }

        // The tick rate does not change; each tick advances ten times
        // the simulated seconds, so the control law keeps its
        // timestep and only the world moves faster.
        FormField {
            Layout.fillWidth: false
            Layout.preferredWidth: 140
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
