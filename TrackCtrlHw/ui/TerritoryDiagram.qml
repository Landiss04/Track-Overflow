import QtQuick

// Wayside territory schematic, drawn from the loaded database.
//
// Geometry comes from track_ctrl_hw.schematic: along the track, positions
// are in block columns; across it, in fixed pixels. Zooming stretches the
// columns, so symbols and labels keep their size and the 12 px text floor
// (style guide 8) holds at every zoom. 100 % fits the whole territory to the
// view; zoom in with the buttons or the wheel (about the cursor) and drag to
// pan. Every colour is a theme token, and block state is carried by fill
// pattern as well as colour (style guide 2 and 8).
Item {
    id: root

    property var diagram: ({})
    property real zoom: 1.0

    readonly property int columns: diagram.columns !== undefined ? diagram.columns : 0
    readonly property real margin: 56
    readonly property real fitPitch: columns > 0
        ? Math.max(8, (width - 2 * margin) / columns) : 64
    readonly property real pitch: fitPitch * zoom
    // Never stretch a block past 200 px.
    readonly property real maxZoom: Math.max(1, 200 / fitPitch)
    readonly property real contentWidth: columns * pitch + 2 * margin
    readonly property real contentHeight: diagram.height !== undefined ? diagram.height : 0
    property real offsetX: 0
    property real offsetY: 0

    readonly property int labelSize: 12

    clip: true

    function clampOffsets() {
        offsetX = contentWidth <= width ? (width - contentWidth) / 2
            : Math.min(0, Math.max(width - contentWidth, offsetX));
        offsetY = contentHeight <= height ? (height - contentHeight) / 2
            : Math.min(0, Math.max(height - contentHeight, offsetY));
    }

    // Zoom so the point under (x, y) in the view stays where it is.
    function zoomAbout(factor, x) {
        const next = Math.min(maxZoom, Math.max(1, zoom * factor));
        if (next === zoom)
            return;
        const column = (x - offsetX - margin) / pitch;
        zoom = next;
        offsetX = x - margin - column * pitch;
        clampOffsets();
        canvas.requestPaint();
    }

    function zoomIn() { zoomAbout(1.25, width / 2); }
    function zoomOut() { zoomAbout(1 / 1.25, width / 2); }
    function fit() {
        zoom = 1;
        clampOffsets();
        canvas.requestPaint();
    }

    onWidthChanged: { clampOffsets(); canvas.requestPaint(); }
    onHeightChanged: { clampOffsets(); canvas.requestPaint(); }
    onDiagramChanged: { clampOffsets(); canvas.requestPaint(); }
    onColumnsChanged: fit()

    Canvas {
        id: canvas
        anchors.fill: parent
        renderTarget: Canvas.Image

        function monoFont(bold) {
            return (bold ? "bold " : "") + root.labelSize + "px \"" + theme.mono_family + "\"";
        }

        function xOf(column) { return root.margin + column * root.pitch; }
        function yOf(row) { return root.diagram.top + row * root.diagram.rowHeight; }

        function line(ctx, x1, y1, x2, y2, color, width, dashed) {
            ctx.beginPath();
            ctx.strokeStyle = color;
            ctx.lineWidth = width;
            ctx.setLineDash(dashed ? [4, 4] : []);
            ctx.moveTo(x1, y1);
            ctx.lineTo(x2, y2);
            ctx.stroke();
            ctx.setLineDash([]);
        }

        function text(ctx, value, x, y, align, color, bold) {
            ctx.font = monoFont(bold === true);
            ctx.fillStyle = color;
            ctx.textAlign = align;
            ctx.fillText(value, x, y);
        }

        // A plate behind a label hides any line that crosses it.
        function plateText(ctx, value, x, y, color) {
            ctx.font = monoFont(false);
            const w = ctx.measureText(value).width + 6;
            ctx.fillStyle = theme.bg_surface;
            ctx.fillRect(x - w / 2, y - root.labelSize, w, root.labelSize + 4);
            text(ctx, value, x, y, "center", color, false);
        }

        function block(ctx, x, y, w, state) {
            const top = y - 6;
            if (state === "free") {
                ctx.fillStyle = theme.bg_raised;
                ctx.fillRect(x, top, w, 12);
                ctx.strokeStyle = theme.border_strong;
                ctx.lineWidth = 1;
                ctx.strokeRect(x + 0.5, top + 0.5, w - 1, 11);
                return;
            }
            ctx.fillStyle = state === "occupied" ? theme.info
                : state === "closed" ? theme.warning : theme.danger;
            ctx.fillRect(x, top, w, 12);
            ctx.save();
            ctx.beginPath();
            ctx.rect(x, top, w, 12);
            ctx.clip();
            ctx.strokeStyle = theme.bg_surface;
            ctx.lineWidth = 1.5;
            ctx.beginPath();
            if (state === "closed") {
                for (let i = -12; i < w + 12; i += 6) {
                    ctx.moveTo(x + i, top + 12);
                    ctx.lineTo(x + i + 12, top);
                }
            } else if (state === "failure") {
                for (let i = 0; i < w; i += 12) {
                    ctx.moveTo(x + i + 2, top + 2);
                    ctx.lineTo(x + i + 10, top + 10);
                    ctx.moveTo(x + i + 10, top + 2);
                    ctx.lineTo(x + i + 2, top + 10);
                }
            }
            ctx.stroke();
            ctx.restore();
        }

        function aspectColor(aspect) {
            return aspect === "red" ? theme.danger
                : aspect === "yellow" ? theme.warning : theme.success;
        }

        onPaint: {
            const ctx = getContext("2d");
            ctx.reset();
            const d = root.diagram;
            if (d.blocks === undefined || root.columns === 0)
                return;
            ctx.save();
            ctx.translate(root.offsetX, root.offsetY);
            ctx.textBaseline = "alphabetic";
            const gap = Math.min(6, root.pitch * 0.12);

            // Rails, and the territory limits at their ends.
            for (const span of d.rows) {
                const y = yOf(span.row);
                const x1 = xOf(span.first), x2 = xOf(span.last);
                line(ctx, x1 - 10, y, x2 + 10, y, theme.border_strong, 1, false);
                if (span.row === 0)
                    line(ctx, x1 - 14, y - 22, x1 - 14, y + 22, theme.border_strong, 1, true);
                line(ctx, x2 + 14, y - 22, x2 + 14, y + 22, theme.border_strong, 1, true);
            }

            // Reverse legs: solid when the switch is set to them.
            for (const sw of d.switches) {
                const xj = xOf(sw.joint), y = yOf(sw.row);
                const reverse = sw.position === "reverse";
                const ink = reverse ? theme.text_secondary : theme.border_strong;
                const weight = reverse ? 2 : 1;
                const leg = sw.reverse;
                if (leg.kind === "stub") {
                    const dx = leg.direction * Math.min(0.45 * root.pitch, 48);
                    line(ctx, xj, y, xj + dx, y + 40, ink, weight, !reverse);
                    text(ctx, leg.label, xj + dx + leg.direction * 4, y + 48,
                         leg.direction > 0 ? "left" : "right", theme.text_muted, false);
                } else if (leg.kind === "loop") {
                    const xe = xOf(leg.col), top = y - 76 - 10 * leg.level;
                    ctx.beginPath();
                    ctx.strokeStyle = ink;
                    ctx.lineWidth = weight;
                    ctx.setLineDash(reverse ? [] : [4, 4]);
                    ctx.moveTo(xj, y);
                    ctx.lineTo(xj, top);
                    ctx.lineTo(xe, top);
                    ctx.lineTo(xe, y);
                    ctx.stroke();
                    ctx.setLineDash([]);
                } else {
                    line(ctx, xj, y, xOf(leg.col), yOf(leg.row), ink, weight, !reverse);
                }
                if (reverse) {
                    // Break the main line at the points: it is not the route.
                    ctx.fillStyle = theme.bg_surface;
                    ctx.fillRect(xj - gap / 2 - 1, y - 2, gap + 2, 4);
                }
            }

            // Blocks, then their labels. A label is drawn only where it
            // will not overlap another; blocks in a notable state go first.
            for (let i = 0; i < d.blocks.length; ++i) {
                const b = d.blocks[i];
                const x = xOf(b.col) + gap / 2;
                block(ctx, x, yOf(b.row), root.pitch - gap, b.state);
            }
            ctx.font = monoFont(false);
            const placed = [];
            const order = d.blocks.filter(b => b.state !== "free")
                .concat(d.blocks.filter(b => b.state === "free"));
            for (const b of order) {
                const xc = xOf(b.col + 0.5), y = yOf(b.row);
                const half = ctx.measureText(b.label).width / 2 + 5;
                const clash = placed.some(p => p.row === b.row
                    && xc - half < p.right && xc + half > p.left);
                if (clash)
                    continue;
                placed.push({ row: b.row, left: xc - half, right: xc + half });
                plateText(ctx, b.label, xc, y + 24,
                          b.state === "free" ? theme.text_muted : theme.text_primary);
            }

            // Switches: the points, then name and position below.
            for (const sw of d.switches) {
                const xj = xOf(sw.joint), y = yOf(sw.row);
                ctx.beginPath();
                ctx.fillStyle = sw.agreeing ? theme.text_secondary : theme.danger;
                ctx.moveTo(xj - 6, y);
                ctx.lineTo(xj, y - 6);
                ctx.lineTo(xj + 6, y);
                ctx.lineTo(xj, y + 6);
                ctx.closePath();
                ctx.fill();
                plateText(ctx, "SW-" + sw.number, xj, y + 62, theme.text_primary);
                plateText(ctx, sw.position.toUpperCase(), xj, y + 76, theme.text_muted);
                if (!sw.agreeing)
                    plateText(ctx, "NOT AGREEING", xj, y + 90, theme.danger);
            }

            // Signals stand at the switches: one head, aspect named beside it.
            for (const sw of d.switches) {
                const x = xOf(sw.signalCol), y = yOf(sw.signalRow);
                line(ctx, x, y - 8, x, y - 28, theme.text_muted, 1, false);
                ctx.beginPath();
                ctx.fillStyle = aspectColor(sw.aspect);
                ctx.strokeStyle = theme.text_secondary;
                ctx.lineWidth = 1;
                ctx.arc(x, y - 36, 7, 0, 2 * Math.PI);
                ctx.fill();
                ctx.stroke();
                plateText(ctx, "SIG-" + sw.number + " \u00b7 " + sw.aspectLetter, x, y - 50,
                          theme.text_primary);
            }

            // Crossings: posts, and gate bars across the track when down.
            for (const xing of d.crossings) {
                const x = xOf(xing.col), y = yOf(xing.row);
                line(ctx, x - 9, y - 30, x - 9, y + 14, theme.text_muted, 1, false);
                line(ctx, x + 9, y - 30, x + 9, y + 14, theme.text_muted, 1, false);
                if (xing.active) {
                    ctx.fillStyle = theme.text_secondary;
                    ctx.fillRect(x - 15, y - 17, 30, 3);
                    ctx.fillRect(x - 15, y + 9, 30, 3);
                    ctx.fillStyle = theme.danger;
                    ctx.beginPath();
                    ctx.arc(x - 9, y - 33, 3, 0, 2 * Math.PI);
                    ctx.arc(x + 9, y - 33, 3, 0, 2 * Math.PI);
                    ctx.fill();
                }
                plateText(ctx, "XING-" + xing.number + " \u00b7 "
                          + (xing.active ? "DOWN" : "UP"), x, y - 50, theme.text_primary);
            }
            ctx.restore();
        }
    }

    MouseArea {
        anchors.fill: parent
        acceptedButtons: Qt.LeftButton
        cursorShape: root.contentWidth > root.width || root.contentHeight > root.height
            ? (pressed ? Qt.ClosedHandCursor : Qt.OpenHandCursor) : Qt.ArrowCursor
        property real lastX: 0
        property real lastY: 0

        onPressed: function (mouse) {
            lastX = mouse.x;
            lastY = mouse.y;
        }
        onPositionChanged: function (mouse) {
            if (!pressed)
                return;
            root.offsetX += mouse.x - lastX;
            root.offsetY += mouse.y - lastY;
            lastX = mouse.x;
            lastY = mouse.y;
            root.clampOffsets();
            canvas.requestPaint();
        }
        onDoubleClicked: root.fit()
        onWheel: function (wheel) {
            const steps = wheel.angleDelta.y / 120;
            if (steps !== 0)
                root.zoomAbout(Math.pow(1.25, steps), wheel.x);
            wheel.accepted = true;
        }
    }

    Accessible.role: Accessible.Graphic
    Accessible.name: qsTr("Wayside territory schematic")
}
