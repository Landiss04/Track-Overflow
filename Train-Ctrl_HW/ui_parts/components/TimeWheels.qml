// Hours, minutes and seconds on three wheels, dragged up and down or
// scrolled, like a phone's timer picker. Hours run 0-23 (24:00 is
// 00:00), minutes and seconds 0-59, each wrapping round. Read the
// choice with timeText(), as HH:MM:SS.
import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "../../../ui"

RowLayout {
    id: root

    property alias hours: hoursWheel.currentIndex
    property alias minutes: minutesWheel.currentIndex
    property alias seconds: secondsWheel.currentIndex

    spacing: theme.space_1
    opacity: enabled ? 1.0 : 0.42

    function pad(value) {
        return (value < 10 ? "0" : "") + value;
    }

    function timeText() {
        return pad(hours) + ":" + pad(minutes) + ":" + pad(seconds);
    }

    component Wheel: Tumbler {
        id: wheel

        Layout.preferredWidth: 40
        // Three rows, in the header's height less a few pixels.
        Layout.preferredHeight: 56
        visibleItemCount: 3
        wrap: true

        background: Rectangle {
            radius: theme.radius_md
            color: theme.bg_app
            border.width: wheel.activeFocus ? 2 : 1
            border.color: wheel.activeFocus ? theme.focus_ring
                                            : theme.border_strong
        }

        // The middle row is the one chosen: full strength and bold;
        // the rows above and below fade.
        delegate: Text {
            text: root.pad(modelData)
            color: theme.text_primary
            font.family: theme.mono_family
            font.pixelSize: theme.size_small
            font.weight: Math.abs(Tumbler.displacement) < 0.5
                ? theme.weight_bold : theme.weight_regular
            opacity: 1.0 - Math.min(1, Math.abs(Tumbler.displacement)) * 0.6
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
        }

        // A scroll steps one number per notch, either way.
        WheelHandler {
            acceptedDevices: PointerDevice.Mouse | PointerDevice.TouchPad
            onWheel: function (event) {
                var step = event.angleDelta.y < 0 ? 1 : -1;
                wheel.currentIndex = (wheel.currentIndex + step + wheel.count)
                    % wheel.count;
            }
        }
    }

    Wheel {
        id: hoursWheel
        objectName: "hoursWheel"
        model: 24
        Accessible.name: qsTr("Hours")
    }
    MonoText { text: ":"; color: theme.text_muted }
    Wheel {
        id: minutesWheel
        objectName: "minutesWheel"
        model: 60
        Accessible.name: qsTr("Minutes")
    }
    MonoText { text: ":"; color: theme.text_muted }
    Wheel {
        id: secondsWheel
        objectName: "secondsWheel"
        model: 60
        Accessible.name: qsTr("Seconds")
    }
}
