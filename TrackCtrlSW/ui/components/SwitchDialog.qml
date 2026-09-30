// Hand-set one switch. Maintenance mode only.
//
// Taking a switch by hand drops the controller's authority to zero
// until it is released, so the dialog says so before APPLY rather than
// after: this is a safety-critical control under style guide 7 and
// gets the confirmation and the explicit consequence.
import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

Dialog {
    id: root

    property var switches: []
    property int currentIndex: 0
    property bool reverse: false

    readonly property var currentSwitch: switches.length > 0
        ? switches[Math.min(currentIndex, switches.length - 1)] : null

    signal applied(string switchId, bool reverse)
    signal released(string switchId)

    modal: true
    anchors.centerIn: parent
    width: 380
    padding: 0
    closePolicy: Popup.CloseOnEscape

    background: Rectangle {
        color: theme.bg_surface
        border.color: theme.border_strong
        border.width: 1
        radius: theme.radius_md
    }

    // Reset to the live position each time it opens, so the dialog
    // never proposes a stale throw.
    onOpened: root.reverse = currentSwitch ? currentSwitch.reverse : false

    contentItem: ColumnLayout {
        spacing: 0

        Rectangle {
            Layout.fillWidth: true
            implicitHeight: theme.control_h_md
            color: theme.bg_sunken

            Text {
                anchors.left: parent.left
                anchors.leftMargin: theme.space_4
                anchors.verticalCenter: parent.verticalCenter
                text: qsTr("SET SWITCH MANUALLY")
                color: theme.text_secondary
                font.family: theme.ui_family
                font.pixelSize: theme.size_label
                font.weight: theme.weight_bold
                font.letterSpacing: theme.label_letter_spacing
            }

            Rectangle {
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.bottom: parent.bottom
                implicitHeight: 1
                color: theme.border
            }
        }

        ColumnLayout {
            Layout.fillWidth: true
            Layout.margins: theme.space_4
            spacing: theme.space_4

            ColumnLayout {
                Layout.fillWidth: true
                spacing: theme.space_2

                FieldLabel { text: qsTr("Switch") }

                ComboBox {
                    id: switchBox
                    Layout.fillWidth: true
                    model: root.switches.map(function (item) {
                        return item.id + "  ·  block " + item.block;
                    })
                    currentIndex: root.currentIndex
                    onActivated: function (index) {
                        root.currentIndex = index;
                        root.reverse = root.switches[index].reverse;
                    }
                }
            }

            ColumnLayout {
                Layout.fillWidth: true
                spacing: theme.space_2

                FieldLabel { text: qsTr("Position") }

                SegmentedToggle {
                    Layout.fillWidth: true
                    options: [qsTr("Normal"), qsTr("Reverse")]
                    currentIndex: root.reverse ? 1 : 0
                    onActivated: function (index) { root.reverse = index === 1; }
                }

                Text {
                    Layout.fillWidth: true
                    visible: root.currentSwitch !== null
                    text: root.currentSwitch === null ? ""
                        : qsTr("Normal routes to %1. Reverse routes to %2.")
                            .arg(root.currentSwitch.normal_to)
                            .arg(root.currentSwitch.reverse_to)
                    color: theme.text_muted
                    font.family: theme.ui_family
                    font.pixelSize: theme.size_label
                    wrapMode: Text.WordWrap
                }
            }

            Rectangle {
                Layout.fillWidth: true
                implicitHeight: consequence.implicitHeight + 2 * theme.space_3
                color: theme.warning_bg
                border.color: theme.warning
                border.width: 1
                radius: theme.radius_sm

                Text {
                    id: consequence
                    anchors.fill: parent
                    anchors.margins: theme.space_3
                    text: qsTr("While any switch is held by hand, this "
                        + "controller commands zero authority. Release it "
                        + "to give the program its switches back.")
                    color: theme.warning
                    font.family: theme.ui_family
                    font.pixelSize: theme.size_label
                    wrapMode: Text.WordWrap
                }
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: theme.space_2

                AppButton {
                    text: qsTr("Release")
                    variant: "ghost"
                    enabled: root.currentSwitch !== null
                        && root.currentSwitch.manual
                    onClicked: {
                        root.released(root.currentSwitch.id);
                        root.close();
                    }
                }

                Item { Layout.fillWidth: true }

                AppButton {
                    text: qsTr("Cancel")
                    variant: "secondary"
                    onClicked: root.close()
                }

                AppButton {
                    text: qsTr("Apply")
                    variant: "primary"
                    enabled: root.currentSwitch !== null
                    onClicked: {
                        root.applied(root.currentSwitch.id, root.reverse);
                        root.close();
                    }
                }
            }
        }
    }
}
