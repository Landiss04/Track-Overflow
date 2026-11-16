// Signal lights: the aspect each wayside light shows, as the Track
// Controller last reported it, one column per line. A row is the
// block the light stands on (its switch's points), the aspect's marker
// and name, and the switch it belongs to (the Track Controller names
// the light by it). The same markers are drawn on the track map.
// Display only: aspects never feed an authority or a speed.
pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import "../../../../ui"

Panel {
    id: root

    // TrackMapModel.signals: { line, signalId, blockId } per light.
    property var lights: []
    // CtcHost.signalStates: "Line:switch" -> aspect.
    property var states: ({})

    readonly property int reportedCount: {
        let count = 0;
        for (const light of root.lights) {
            if (root.states[light.line + ":" + light.signalId])
                count += 1;
        }
        return count;
    }

    function aspectName(aspect) {
        return aspect === "RED" ? qsTr("Red")
            : aspect === "YELLOW" ? qsTr("Yellow")
            : aspect === "GREEN" ? qsTr("Green")
            : aspect === "SUPER_GREEN" ? qsTr("Super green")
            : qsTr("Not reported");
    }

    title: qsTr("Signals")

    headerItems: [
        HelperText {
            text: qsTr("%1 of %2 reported").arg(root.reportedCount)
                .arg(root.lights.length)
            wrapMode: Text.NoWrap
        }
    ]

    RowLayout {
        Layout.fillWidth: true
        spacing: theme.space_4

        Repeater {
            model: ["Red", "Green"]

            delegate: ColumnLayout {
                id: column
                required property string modelData
                Layout.fillWidth: true
                Layout.preferredWidth: 1
                Layout.alignment: Qt.AlignTop
                spacing: theme.space_1

                FieldLabel {
                    Layout.bottomMargin: theme.space_1
                    text: (column.modelData === "Red" ? qsTr("Red line")
                        : qsTr("Green line")).toUpperCase()
                }

                Repeater {
                    model: root.lights.filter(
                        light => light.line === column.modelData)

                    delegate: RowLayout {
                        id: row
                        required property var modelData
                        readonly property string aspect: root.states[
                            modelData.line + ":" + modelData.signalId] || ""
                        objectName: "signal-row-" + modelData.line + "-"
                            + modelData.signalId
                        Layout.fillWidth: true
                        spacing: theme.space_2

                        SignalMarker {
                            aspect: row.aspect
                        }

                        // The light's block, as on the map.
                        MonoText {
                            Layout.preferredWidth: 28
                            horizontalAlignment: Text.AlignRight
                            text: row.modelData.blockId
                            font.weight: theme.weight_bold
                        }

                        Text {
                            Layout.fillWidth: true
                            text: root.aspectName(row.aspect)
                            textFormat: Text.PlainText
                            elide: Text.ElideRight
                            color: row.aspect !== "" ? theme.text_primary
                                : theme.text_muted
                            font.family: theme.ui_family
                            font.pixelSize: theme.size_small
                        }

                        HelperText {
                            text: qsTr("sw %1").arg(row.modelData.signalId)
                            wrapMode: Text.NoWrap
                            color: theme.text_muted
                        }
                    }
                }
            }
        }
    }

    HelperText {
        Layout.fillWidth: true
        Layout.topMargin: theme.space_2
        text: qsTr("Light's block, aspect and switch. Display only.")
    }

    Item { Layout.fillHeight: true }
}
