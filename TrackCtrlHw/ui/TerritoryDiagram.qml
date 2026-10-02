import QtQuick

// Wayside territory schematic, ported from the SVG in
// TrackCtrlHw/ui/html/track-controller.html. Geometry is kept in the original
// 678 x 450 coordinate space and scaled to fit, so the drawing stays a direct
// transcription. Every colour comes from the shared theme; block state is
// carried by fill *and* by the printed label, per Style Guide §2 and §8.
Item {
    id: root

    readonly property real designWidth: 678
    readonly property real designHeight: 450

    property real zoom: 1.0

    readonly property int microSize: 12
    readonly property int labelSize: 12
    readonly property int valueSize: 13

    clip: true

    onWidthChanged: canvas.requestPaint()
    onHeightChanged: canvas.requestPaint()
    onZoomChanged: canvas.requestPaint()

    Canvas {
        id: canvas
        anchors.fill: parent
        renderTarget: Canvas.Image

        // Text is drawn in design units, so a fit scale below 1 would shrink it
        // past the 12 px floor in §8. Oversize it by the inverse of the scale,
        // capped so labels do not collide with the geometry around them.
        property real fontScale: 1.0

        function uiFont(size) {
            return "bold " + Math.round(size * fontScale) + "px \"" + theme.ui_family + "\"";
        }

        function monoFont(size) {
            return Math.round(size * fontScale) + "px \"" + theme.mono_family + "\"";
        }

        function thinLine(ctx, x1, y1, x2, y2) {
            ctx.beginPath();
            ctx.strokeStyle = theme.border_strong;
            ctx.lineWidth = 1;
            ctx.setLineDash([]);
            ctx.moveTo(x1 + 0.5, y1);
            ctx.lineTo(x2 + 0.5, y2);
            ctx.stroke();
        }

        function dashLine(ctx, x1, y1, x2, y2) {
            ctx.beginPath();
            ctx.strokeStyle = theme.border_strong;
            ctx.lineWidth = 1;
            ctx.setLineDash([4, 4]);
            ctx.moveTo(x1 + 0.5, y1);
            ctx.lineTo(x2 + 0.5, y2);
            ctx.stroke();
            ctx.setLineDash([]);
        }

        function leg(ctx, x1, y1, x2, y2) {
            ctx.beginPath();
            ctx.strokeStyle = theme.text_secondary;
            ctx.lineWidth = 1.5;
            ctx.setLineDash([]);
            ctx.moveTo(x1, y1);
            ctx.lineTo(x2, y2);
            ctx.stroke();
        }

        function blockFree(ctx, x, y, w, h) {
            ctx.fillStyle = theme.bg_raised;
            ctx.fillRect(x, y, w, h);
            ctx.strokeStyle = theme.border_strong;
            ctx.lineWidth = 1;
            ctx.setLineDash([]);
            ctx.strokeRect(x + 0.5, y + 0.5, w - 1, h - 1);
        }

        function blockOccupied(ctx, x, y, w, h) {
            ctx.fillStyle = theme.info;
            ctx.fillRect(x, y, w, h);
        }

        function blockClosed(ctx, x, y, w, h) {
            ctx.fillStyle = theme.warning;
            ctx.fillRect(x, y, w, h);
        }

        function solid(ctx, x, y, w, h) {
            ctx.fillStyle = theme.text_secondary;
            ctx.fillRect(x, y, w, h);
        }

        function plate(ctx, x, y, w, h) {
            ctx.fillStyle = theme.bg_surface;
            ctx.fillRect(x, y, w, h);
        }

        function signalHead(ctx, cx, cy) {
            ctx.beginPath();
            ctx.fillStyle = theme.bg_sunken;
            ctx.strokeStyle = theme.text_muted;
            ctx.lineWidth = 1;
            ctx.setLineDash([]);
            ctx.arc(cx, cy, 4.5, 0, 2 * Math.PI);
            ctx.fill();
            ctx.stroke();
        }

        function switchMark(ctx, cx, cy) {
            ctx.beginPath();
            ctx.fillStyle = theme.text_secondary;
            ctx.moveTo(cx - 6, cy);
            ctx.lineTo(cx, cy - 6);
            ctx.lineTo(cx + 6, cy);
            ctx.lineTo(cx, cy + 6);
            ctx.closePath();
            ctx.fill();
        }

        function micro(ctx, text, x, y) {
            ctx.fillStyle = theme.text_muted;
            ctx.font = uiFont(root.microSize);
            ctx.textAlign = "left";
            ctx.fillText(text, x, y);
        }

        function label(ctx, text, x, y, align) {
            ctx.fillStyle = theme.text_muted;
            ctx.font = monoFont(root.labelSize);
            ctx.textAlign = align !== undefined ? align : "left";
            ctx.fillText(text, x, y);
        }

        function value(ctx, text, x, y, align) {
            ctx.fillStyle = theme.text_primary;
            ctx.font = monoFont(root.valueSize);
            ctx.textAlign = align !== undefined ? align : "left";
            ctx.fillText(text, x, y);
        }

        function signalMast(ctx, x, leftHead, rightHead, name, states) {
            thinLine(ctx, x, 154, x, 126);
            signalHead(ctx, leftHead, 120);
            signalHead(ctx, rightHead, 120);
            label(ctx, name, x, 94, "center");
            label(ctx, states, x, 106, "center");
        }

        onPaint: {
            var ctx = getContext("2d");
            ctx.reset();
            ctx.clearRect(0, 0, width, height);

            var scale = Math.min(width / root.designWidth, height / root.designHeight) * root.zoom;
            fontScale = Math.min(1.35, Math.max(1.0, 1.0 / scale));
            ctx.save();
            ctx.translate((width - root.designWidth * scale) / 2,
                          (height - root.designHeight * scale) / 2);
            ctx.scale(scale, scale);
            ctx.textBaseline = "alphabetic";

            micro(ctx, "SCHEMATIC \u00B7 MAIN LINE AND SIDING", 0, 12);

            // territory limits
            dashLine(ctx, 28, 140, 28, 180);
            dashLine(ctx, 658, 140, 658, 180);

            // wayside signals, one head per direction
            signalMast(ctx, 120, 112, 128, "SIG-11/12", "SG \u00B7 SG");
            signalMast(ctx, 210, 202, 218, "SIG-12/13", "SG \u00B7 G");
            signalMast(ctx, 390, 382, 398, "SIG-14/15", "SG \u00B7 R");
            signalMast(ctx, 480, 472, 488, "SIG-15/16", "R \u00B7 Y");

            // road crossing
            label(ctx, "XING-15", 434, 66, "center");
            label(ctx, "GATES DOWN", 434, 78, "center");
            thinLine(ctx, 426, 112, 426, 204);
            thinLine(ctx, 442, 112, 442, 204);
            solid(ctx, 422, 130, 24, 3);
            solid(ctx, 422, 188, 24, 3);

            // main line blocks 11..17
            blockFree(ctx, 32, 154, 84, 12);
            blockFree(ctx, 122, 154, 84, 12);
            blockFree(ctx, 212, 154, 84, 12);
            blockFree(ctx, 302, 154, 84, 12);
            blockOccupied(ctx, 392, 154, 84, 12);
            blockFree(ctx, 482, 154, 84, 12);
            blockOccupied(ctx, 572, 154, 84, 12);

            // switches and their diverging legs
            switchMark(ctx, 300, 160);
            leg(ctx, 300, 166, 374, 290);
            switchMark(ctx, 570, 160);
            leg(ctx, 570, 166, 632, 218);

            // block identity plates
            plate(ctx, 46, 211, 56, 16);
            plate(ctx, 136, 211, 56, 16);
            plate(ctx, 226, 211, 56, 16);
            plate(ctx, 316, 211, 56, 16);
            plate(ctx, 406, 211, 56, 30);
            plate(ctx, 496, 211, 56, 16);
            plate(ctx, 586, 211, 56, 30);

            label(ctx, "D-11", 74, 222, "center");
            label(ctx, "D-12", 164, 222, "center");
            label(ctx, "D-13", 254, 222, "center");
            label(ctx, "D-14", 344, 222, "center");
            label(ctx, "E-15", 434, 222, "center");
            label(ctx, "E-16", 524, 222, "center");
            label(ctx, "E-17", 614, 222, "center");
            value(ctx, "T-104 \u2192", 434, 237, "center");
            value(ctx, "T-117 \u2192", 614, 237, "center");

            plate(ctx, 272, 242, 56, 28);
            label(ctx, "SW-1", 300, 252, "center");
            label(ctx, "NORMAL", 300, 264, "center");

            label(ctx, "SW-2", 674, 252, "right");
            label(ctx, "NORMAL", 674, 264, "right");
            label(ctx, "TO YARD", 674, 276, "right");

            // siding blocks 18..19
            blockFree(ctx, 380, 290, 84, 12);
            blockClosed(ctx, 470, 290, 84, 12);
            solid(ctx, 558, 284, 4, 24);
            label(ctx, "F-18", 422, 320, "center");
            label(ctx, "F-19", 512, 320, "center");
            label(ctx, "CLOSED", 512, 332, "center");
            label(ctx, "END OF SIDING", 566, 320);

            // legend
            micro(ctx, "BLOCK AND DEVICE STATE", 0, 356);
            blockOccupied(ctx, 0, 372, 14, 10);
            label(ctx, "OCCUPIED", 20, 381);
            blockFree(ctx, 130, 372, 14, 10);
            label(ctx, "CLEAR", 150, 381);
            blockClosed(ctx, 240, 372, 14, 10);
            label(ctx, "CLOSED", 260, 381);
            signalHead(ctx, 356, 377);
            signalHead(ctx, 372, 377);
            label(ctx, "SIGNAL \u00B7 ONE HEAD PER DIRECTION", 384, 381);

            switchMark(ctx, 10, 403);
            label(ctx, "SWITCH", 24, 403);
            thinLine(ctx, 146, 392, 146, 406);
            thinLine(ctx, 154, 392, 154, 406);
            solid(ctx, 143, 398, 14, 2);
            label(ctx, "CROSSING", 166, 403);
            dashLine(ctx, 300, 403, 320, 403);
            label(ctx, "TERRITORY LIMIT", 326, 403);

            label(ctx, "R RED \u00B7 Y YELLOW \u00B7 G GREEN \u00B7 SG SUPER GREEN", 0, 425);
            label(ctx, "BLOCK LABELS READ SECTION-BLOCK \u00B7 STATES READ LEFT HEAD \u00B7 RIGHT HEAD", 0, 439);

            ctx.restore();
        }
    }

    Accessible.role: Accessible.Graphic
    Accessible.name: "Wayside territory schematic"
    Accessible.description: "Green line sections D and E carry main-line blocks 11 to 17; " +
        "section F carries siding blocks 18 and 19. Switches SW-1 and SW-2 are normal. " +
        "Blocks 15 and 17 are occupied by T-104 and T-117, both travelling right. " +
        "Block 19 is closed. Crossing XING-15 has its gates down."
}
