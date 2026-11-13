// The Train Model interface bench.
//
// Left, everything that goes into the controller: the signals the
// Train Model will send, and beside them the controls a driver or an
// engineer would press at the console. Right, what the controller
// sends back out. The bar on top belongs to the simulation rather
// than to any one train.
import QtQuick
import QtQuick.Layouts
import "../../../ui"
import "../panels"

Item {
    id: root

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: theme.space_3
        spacing: theme.space_2

        BenchBar {
            Layout.fillWidth: true
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.bottomMargin: theme.space_1
            spacing: theme.space_3

            TestInputsPanel {
                Layout.fillWidth: true
                Layout.preferredWidth: 2
                Layout.fillHeight: true
            }

            TestOutputsPanel {
                Layout.fillWidth: true
                Layout.preferredWidth: 1
                Layout.fillHeight: true
            }
        }
    }
}
