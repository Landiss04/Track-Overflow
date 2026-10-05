// Rotary speed dial. The centre reads the target; the ring fills to the
// actual speed. Drag or press the ring to set the target in Manual.
//
// Canvas angles run clockwise from +x with y pointing down, so the face
// starts at the lower left (135 degrees) and sweeps 270 degrees round to
// the lower right. The 90 degrees left open at the bottom are the dead
// zone, and anything inside it reads as zero rather than as full scale.
import QtQuick
import QtQuick.Layouts
import "../../../ui"

Item {
    id: root

    property real target: 0
    property real actual: 0
    property real limit: 70
    property bool interactive: false
    signal targetRequested(int mph)

    readonly property real startDeg: 135
    readonly property real sweepDeg: 270
    readonly property real radius: Math.max(
        1, Math.min(width, height) / 2 - 8)
    readonly property real ringWidth: Math.max(12, radius * 0.16)

    implicitWidth: 190
    implicitHeight: 190

    function angleFor(value) {
        const span = limit <= 0 ? 0 : Math.max(0, Math.min(1, value / limit));
        return startDeg + span * sweepDeg;
    }

    function valueFor(degrees) {
        let delta = (degrees - startDeg + 360) % 360;
        if (delta > sweepDeg + (360 - sweepDeg) / 2)
            delta = 0;
        return Math.max(0, Math.min(1, delta / sweepDeg)) * limit;
    }

    onTargetChanged: face.requestPaint()
    onActualChanged: face.requestPaint()
    onLimitChanged: face.requestPaint()
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
            const w = root.ringWidth;
            const rad = function (degrees) { return degrees * Math.PI / 180; };

            // Track.
            ctx.lineWidth = w;
            ctx.lineCap = "butt";
            ctx.strokeStyle = theme.bg_sunken;
            ctx.beginPath();
            ctx.arc(cx, cy, r, rad(root.startDeg),
                    rad(root.startDeg + root.sweepDeg), false);
            ctx.stroke();

            // Fill, to the speed the train is actually doing.
            ctx.strokeStyle = theme.accent;
            ctx.beginPath();
            ctx.arc(cx, cy, r, rad(root.startDeg),
                    rad(root.angleFor(root.actual)), false);
            ctx.stroke();

            // Ten-mph ticks.
            ctx.lineWidth = 1;
            ctx.strokeStyle = theme.border_strong;
            for (let mark = 0; mark <= root.limit; mark += 10) {
                const a = rad(root.angleFor(mark));
                ctx.beginPath();
                const outer = Math.max(0, r - w - 2);
                const inner = Math.max(0, r - w - 8);
                ctx.moveTo(cx + outer * Math.cos(a), cy + outer * Math.sin(a));
                ctx.lineTo(cx + inner * Math.cos(a), cy + inner * Math.sin(a));
                ctx.stroke();
            }

            // Target handle. Muted while the dial cannot be moved, so it
            // never looks live when the console is locked.
            const handle = rad(root.angleFor(root.target));
            ctx.beginPath();
            ctx.arc(cx + (r - w / 2) * Math.cos(handle),
                    cy + (r - w / 2) * Math.sin(handle),
                    w * 0.6, 0, 2 * Math.PI);
            ctx.fillStyle = root.interactive ? theme.text_primary
                                             : theme.text_muted;
            ctx.fill();
            ctx.lineWidth = 3;
            ctx.strokeStyle = theme.bg_surface;
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
        const degrees = Math.atan2(mouse.y - height / 2, mouse.x - width / 2)
            * 180 / Math.PI;
        root.targetRequested(Math.round(valueFor((degrees + 360) % 360)));
    }

    ColumnLayout {
        anchors.centerIn: parent
        spacing: 0

        FieldLabel {
            Layout.alignment: Qt.AlignHCenter
            text: qsTr("TARGET SPEED")
        }

        Text {
            Layout.alignment: Qt.AlignHCenter
            text: Math.round(root.target)
            color: theme.text_primary
            font.family: theme.mono_family
            font.pixelSize: Math.max(32, root.radius * 0.6)
            font.weight: theme.weight_bold
        }

        MonoText {
            Layout.alignment: Qt.AlignHCenter
            text: "mph"
            color: theme.text_muted
        }
    }
}
