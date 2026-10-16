import QtQuick
import QtQuick.Layouts

// Key to the territory schematic. It sits outside the drawing, so it stays
// readable at any zoom. Each state is named, never shown by colour alone.
Flow {
    id: root

    spacing: theme.space_4

    component Caption: Text {
        textFormat: Text.PlainText
        color: theme.text_muted
        font.family: theme.mono_family
        font.pixelSize: theme.size_label
        anchors.verticalCenter: parent.verticalCenter
    }

    component Swatch: Canvas {
        property string state: "free"
        width: 22
        height: 12
        anchors.verticalCenter: parent.verticalCenter
        onPaint: {
            const ctx = getContext("2d");
            ctx.reset();
            if (state === "free") {
                ctx.fillStyle = theme.bg_raised;
                ctx.fillRect(0, 0, width, height);
                ctx.strokeStyle = theme.border_strong;
                ctx.strokeRect(0.5, 0.5, width - 1, height - 1);
                return;
            }
            ctx.fillStyle = state === "occupied" ? theme.info
                : state === "closed" ? theme.warning : theme.danger;
            ctx.fillRect(0, 0, width, height);
            ctx.strokeStyle = theme.bg_surface;
            ctx.lineWidth = 1.5;
            ctx.beginPath();
            if (state === "closed") {
                for (let i = -12; i < width + 12; i += 6) {
                    ctx.moveTo(i, height);
                    ctx.lineTo(i + 12, 0);
                }
            } else if (state === "failure") {
                ctx.moveTo(6, 2); ctx.lineTo(14, 10);
                ctx.moveTo(14, 2); ctx.lineTo(6, 10);
            }
            ctx.stroke();
        }
    }

    Row { spacing: theme.space_2; Swatch { state: "free" } Caption { text: qsTr("CLEAR") } }
    Row { spacing: theme.space_2; Swatch { state: "occupied" } Caption { text: qsTr("OCCUPIED") } }
    Row { spacing: theme.space_2; Swatch { state: "closed" } Caption { text: qsTr("CLOSED") } }
    Row { spacing: theme.space_2; Swatch { state: "failure" } Caption { text: qsTr("FAILURE") } }

    Row {
        spacing: theme.space_2
        Rectangle {
            width: 12
            height: 12
            radius: 6
            color: theme.success
            border.color: theme.text_secondary
            anchors.verticalCenter: parent.verticalCenter
        }
        Caption { text: qsTr("SIGNAL \u00b7 R Y G SG") }
    }

    Row {
        spacing: theme.space_2
        Rectangle {
            width: 9
            height: 9
            rotation: 45
            color: theme.text_secondary
            anchors.verticalCenter: parent.verticalCenter
        }
        Caption { text: qsTr("SWITCH \u00b7 DASHED LEG NOT SET") }
    }

    Row {
        spacing: theme.space_2
        Item {
            width: 18
            height: 14
            anchors.verticalCenter: parent.verticalCenter
            Rectangle { x: 3; width: 1; height: 14; color: theme.text_muted }
            Rectangle { x: 14; width: 1; height: 14; color: theme.text_muted }
            Rectangle { y: 5; width: 18; height: 3; color: theme.text_secondary }
        }
        Caption { text: qsTr("CROSSING") }
    }
}
