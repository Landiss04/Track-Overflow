// Module window header, style guide 6.7: module name and instance, the user
// and mode selectors, and the simulation clock. An engaged emergency brake is
// mirrored by a persistent Fault badge (style guide 7).
import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

Rectangle {
    id: root

    property var snapshot: ({})
    signal userSelected(string role)
    signal modeSelected(string mode)

    readonly property var userOptions: ["Driver", "Engineer"]
    readonly property var modeOptions: ["Automatic", "Manual"]

    implicitHeight: theme.control_h_lg + theme.space_3
    color: theme.bg_raised

    Rectangle {
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        height: 1
        color: theme.border
    }

    RowLayout {
        anchors.fill: parent
        anchors.leftMargin: theme.space_5
        anchors.rightMargin: theme.space_5
        spacing: theme.space_4

        ColumnLayout {
            spacing: 2

            Text {
                text: qsTr("Train Controller")
                color: theme.text_primary
                font.family: theme.ui_family
                font.pixelSize: theme.size_h3
                font.weight: theme.weight_bold
            }

            FieldLabel {
                text: (root.snapshot.line + " · block "
                    + root.snapshot.current_block).toUpperCase()
            }
        }

        Rectangle {
            Layout.preferredWidth: 1
            Layout.preferredHeight: theme.control_h_md
            color: theme.border
        }

        FieldLabel { text: "TRAIN" }

        ComboBox {
            id: trainPicker

            implicitWidth: 152
            implicitHeight: theme.control_h_md
            model: root.snapshot.train_ids
            font.family: theme.mono_family
            font.pixelSize: theme.size_body

            background: Rectangle {
                radius: theme.radius_md
                color: theme.bg_sunken
                border.width: 1
                border.color: trainPicker.visualFocus ? theme.accent : theme.border_strong
            }
        }

        StatusBadge {
            visible: root.snapshot.emergency_brake === true
            variant: "fault"
            label: "E-brake on"
        }

        Item { Layout.fillWidth: true }

        FieldLabel { text: "USER" }

        SegmentedToggle {
            options: root.userOptions
            currentIndex: root.userOptions.indexOf(root.snapshot.user_role)
            onActivated: function (index) { root.userSelected(root.userOptions[index]); }
        }

        FieldLabel { text: "MODE" }

        SegmentedToggle {
            options: root.modeOptions
            currentIndex: root.modeOptions.indexOf(root.snapshot.mode)
            onActivated: function (index) { root.modeSelected(root.modeOptions[index]); }
        }

        Rectangle {
            Layout.preferredWidth: 1
            Layout.preferredHeight: theme.control_h_md
            color: theme.border
        }

        MonoText {
            text: root.snapshot.clock
            font.pixelSize: theme.size_h2
            font.weight: theme.weight_bold
        }
    }
}
