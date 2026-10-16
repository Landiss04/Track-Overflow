// Ticket sales per simulated clock hour over the last 12 hours: one small
// bar chart per line, on one shared scale so the lines compare.
//
// Each chart is labeled with its line name and drawn in --accent. The
// line-identity colors are not used: the style guide keeps them to track
// strokes and section letters, and red and green bars cannot be told
// apart with deuteranopia. Hovering a bar shows its value in the header
// line (a popup tooltip would escape the window's scale transform).
pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import "../../../../ui"

ColumnLayout {
    id: root

    // CtcHost.throughputHistory: { hours, series: [{ line, counts }],
    // peak, current }.
    property var history: null

    readonly property var hours: history ? history.hours : []
    readonly property var series: history ? history.series : []
    readonly property int peak: history ? history.peak : 0
    readonly property int current: history ? history.current : -1
    readonly property int barGap: 2
    readonly property int chartHeight: 36
    readonly property int labelWidth: 48
    // The hovered bar, as "line|hour index"; empty when none.
    property string hovered: ""

    function hoverText() {
        if (root.hovered === "")
            return root.peak > 0
                ? qsTr("Tickets sold per hour · peak %1").arg(root.peak)
                : qsTr("No ticket sales yet");
        const parts = root.hovered.split("|");
        const index = Number(parts[1]);
        const line = root.series.find(function (s) {
            return s.line === parts[0];
        });
        const start = root.hours[index];
        const end = index + 1 < root.hours.length
            ? root.hours[index + 1]
            : String((Number(start.slice(0, 2)) + 1) % 24).padStart(2, "0")
                + ":00";
        return qsTr("%1 line, %2–%3: %4 tickets%5").arg(parts[0])
            .arg(start).arg(end).arg(line ? line.counts[index] : 0)
            .arg(index === root.current ? qsTr(" (hour in progress)") : "");
    }

    spacing: theme.space_1

    HelperText {
        Layout.fillWidth: true
        text: root.hoverText()
        color: root.hovered === "" ? theme.text_muted : theme.text_primary
    }

    Repeater {
        model: root.series

        delegate: RowLayout {
            id: chartRow

            required property var modelData

            Layout.fillWidth: true
            spacing: theme.space_2

            Text {
                Layout.preferredWidth: root.labelWidth
                Layout.alignment: Qt.AlignBottom
                text: chartRow.modelData.line
                color: theme.text_secondary
                font.family: theme.ui_family
                font.pixelSize: theme.size_small
            }

            Item {
                id: plot

                readonly property real slotWidth: (width
                    - root.barGap * (root.hours.length - 1))
                    / Math.max(1, root.hours.length)

                Layout.fillWidth: true
                implicitHeight: root.chartHeight

                // Baseline: recessive, so the bars carry the ink.
                Rectangle {
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.bottom: parent.bottom
                    height: 1
                    color: theme.border_strong
                }

                Repeater {
                    model: chartRow.modelData.counts

                    delegate: Item {
                        id: slot

                        required property int index
                        required property int modelData
                        readonly property string key:
                            chartRow.modelData.line + "|" + index

                        x: index * (plot.slotWidth + root.barGap)
                        width: plot.slotWidth
                        height: plot.height

                        Rectangle {
                            // Any sale shows at least a sliver.
                            readonly property real barHeight: root.peak > 0
                                && slot.modelData > 0
                                ? Math.max(2, (plot.height - 1)
                                    * slot.modelData / root.peak)
                                : 0
                            anchors.left: parent.left
                            anchors.right: parent.right
                            anchors.bottom: parent.bottom
                            anchors.bottomMargin: 1
                            height: barHeight
                            visible: barHeight > 0
                            color: root.hovered === slot.key
                                ? theme.accent_active : theme.accent
                            // Rounded data end, square on the baseline.
                            topLeftRadius: Math.min(4, barHeight / 2)
                            topRightRadius: Math.min(4, barHeight / 2)
                        }

                        // The whole slot is the hover target, bigger than
                        // the bar.
                        MouseArea {
                            anchors.fill: parent
                            hoverEnabled: true
                            onContainsMouseChanged: {
                                if (containsMouse)
                                    root.hovered = slot.key;
                                else if (root.hovered === slot.key)
                                    root.hovered = "";
                            }
                        }
                    }
                }
            }
        }
    }

    // Hour axis, shared by both charts: every third hour.
    Item {
        Layout.fillWidth: true
        Layout.leftMargin: root.labelWidth + theme.space_2
        implicitHeight: axisProbe.implicitHeight

        MonoText {
            id: axisProbe
            visible: false
            text: "00:00"
            font.pixelSize: theme.size_label
        }

        Repeater {
            model: root.hours

            delegate: MonoText {
                required property int index
                required property string modelData
                readonly property real slotWidth: (parent.width
                    - root.barGap * (root.hours.length - 1))
                    / Math.max(1, root.hours.length)

                visible: index % 3 === 0
                x: index * (slotWidth + root.barGap)
                text: modelData
                color: theme.text_muted
                font.pixelSize: theme.size_label
            }
        }
    }
}
