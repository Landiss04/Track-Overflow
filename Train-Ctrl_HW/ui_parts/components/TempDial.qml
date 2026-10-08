// Thermostat dial. Drag the ring to set the target; the centre reads
// the setpoint and the word above says whether the cabin is heating,
// cooling or holding, so the colour is never the only signal.
//
// Angles follow the same convention as SpeedDial: clockwise from +x
// with y down, starting at 120 degrees and sweeping 300.
import QtQuick
import QtQuick.Layouts
import "../../../ui"

Item {
    id: root

    property real target: 72
    property real actual: 70
    property bool interactive: true
    signal targetRequested(int degrees)

    readonly property real low: 60
    readonly property real high: 80
    readonly property real startDeg: 120
    readonly property real sweepDeg: 300
    readonly property real radius: Math.max(
        1, Math.min(width, height) / 2 - 6)
    readonly property string mode: target > actual + 0.5 ? qsTr("HEATING")
        : target < actual - 0.5 ? qsTr("COOLING") : qsTr("HOLDING")
    readonly property color tone: target > actual + 0.5 ? theme.warning
        : target < actual - 0.5 ? theme.accent : theme.text_muted

    implicitWidth: 150
    implicitHeight: 150

    function angleFor(value) {
        const span = Math.max(0, Math.min(1, (value - low) / (high - low)));
        return startDeg + span * sweepDeg;
    }

    function nudge(step) {
        if (root.interactive)
            root.targetRequested(Math.max(low, Math.min(high,
                Math.round(root.target) + step)));
    }

    // Keyboard reach and a visible focus ring (guide 8): arrows step
    // the target by one, the same request a drag makes.
    activeFocusOnTab: root.interactive
    Keys.onUpPressed: root.nudge(1)
    Keys.onRightPressed: root.nudge(1)
    Keys.onDownPressed: root.nudge(-1)
    Keys.onLeftPressed: root.nudge(-1)

    Rectangle {
        anchors.fill: parent
        visible: root.activeFocus && root.interactive
        color: "transparent"
        radius: width / 2
        border.width: 2
        border.color: theme.focus_ring
    }

    onTargetChanged: face.requestPaint()
    onActualChanged: face.requestPaint()
    onInteractiveChanged: face.requestPaint()

    Canvas {
        id: face
        anchors.fill: parent

        onPaint: {
            const ctx = getContext("2d");
            ctx.reset();

            const cx = width / 2;
            const cy = height / 2;
            const r = root.radius;
            const rad = function (degrees) { return degrees * Math.PI / 180; };

            // Tick ring, the way a thermostat face reads. Ticks up to
            // the setpoint carry the mode colour; the rest stay border.
            const ticks = 60;
            for (let i = 0; i <= ticks; ++i) {
                const span = i / ticks;
                const a = rad(root.startDeg + span * root.sweepDeg);
                const value = root.low + span * (root.high - root.low);
                const on = value <= root.target + 1e-6;
                const inner = Math.max(0, r - (i % 15 === 0 ? 14 : 9));
                ctx.lineWidth = on ? 3 : 2;
                ctx.strokeStyle = on ? root.tone : theme.border;
                ctx.beginPath();
                ctx.moveTo(cx + r * Math.cos(a), cy + r * Math.sin(a));
                ctx.lineTo(cx + inner * Math.cos(a), cy + inner * Math.sin(a));
                ctx.stroke();
            }

            // Setpoint marker.
            const a = rad(root.angleFor(root.target));
            ctx.lineWidth = 4;
            ctx.strokeStyle = root.interactive ? theme.text_primary
                                               : theme.text_muted;
            ctx.beginPath();
            ctx.moveTo(cx + r * Math.cos(a), cy + r * Math.sin(a));
            const stem = Math.max(0, r - 18);
            ctx.lineTo(cx + stem * Math.cos(a), cy + stem * Math.sin(a));
            ctx.stroke();
        }
    }

    MouseArea {
        anchors.fill: parent
        enabled: root.interactive
        onPressed: function (mouse) { root.pick(mouse); }
        onPositionChanged: function (mouse) { root.pick(mouse); }
    }

    function pick(mouse) {
        const degrees = (Math.atan2(mouse.y - height / 2, mouse.x - width / 2)
            * 180 / Math.PI + 360) % 360;
        let delta = (degrees - startDeg + 360) % 360;
        if (delta > sweepDeg + (360 - sweepDeg) / 2)
            delta = 0;
        const span = Math.max(0, Math.min(1, delta / sweepDeg));
        root.targetRequested(Math.round(low + span * (high - low)));
    }

    ColumnLayout {
        anchors.centerIn: parent
        spacing: 0

        FieldLabel {
            Layout.alignment: Qt.AlignHCenter
            text: root.mode
            color: root.tone
        }

        Text {
            Layout.alignment: Qt.AlignHCenter
            text: Math.round(root.target)
            color: theme.text_primary
            font.family: theme.mono_family
            font.pixelSize: Math.max(30, root.radius * 0.66)
            font.weight: theme.weight_bold
        }

        MonoText {
            Layout.alignment: Qt.AlignHCenter
            text: qsTr("\u00b0F TARGET")
            color: theme.text_muted
        }
    }
}
