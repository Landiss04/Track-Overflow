# UI Scaling Guide

## Purpose

Every module UI is a fixed visual composition, not a responsive layout.
When the window changes size, the entire composition must zoom uniformly. A
card, label, button, gap, font, border, and corner radius must retain its
position and proportion relative to every other element.

All modules resize the same way, through one shared implementation in the
repository-level `ui/` folder. Do not write module-specific window sizing.

The reference canvas is **1440 x 900**, a 16:10 aspect ratio. The minimum
window size is **720 x 450**, which renders the canvas at 0.5x.

## Using it in a module

Two pieces, both in `ui/`:

1. **`ui/ScaledWindow.qml`** is the module's application window. It owns the
   reference canvas, the uniform scale, the letterbox, and the minimum size.
   Children declared inside it are placed on the 1440 x 900 canvas:

   ```qml
   import "../../ui"          // relative to your Main.qml; see ui/README.md

   ScaledWindow {
       title: qsTr("My Module")
       ColumnLayout { anchors.fill: parent /* ... */ }
   }
   ```

2. **`ui/aspect_lock.py`** keeps the window at 16:10 while it is dragged on
   Windows. Install it once the QML has loaded, and keep the returned
   object alive for the life of the window:

   ```python
   from ui.aspect_lock import install_window_scaling

   engine.load(...)
   window_scaling = install_window_scaling(engine.rootObjects()[0])
   ```

   It reads `referenceWidth` and `referenceHeight` from the window, so the
   lock and the canvas can never disagree.

Modules currently using it: CTC Office (`CTC-Office/ctc_ui/`) and Train
Model (`TrainModel/`).

## How scaling works

`ScaledWindow` keeps its `designCanvas` at 1440 x 900 and applies the same
`Scale` factor to both axes:

```qml
canvasScale: Math.min(window.width / referenceWidth,
                      window.height / referenceHeight)
xScale: window.canvasScale
yScale: window.canvasScale
```

The canvas is centered after scaling. If the native window is not 16:10, the
unused area is letterboxed around the canvas. Do not make child controls react
to the available window width or height; their geometry belongs to the fixed
reference canvas.

## Aspect-ratio locking

The UI targets Windows 11. There, `ui/aspect_lock.py` subclasses the window
procedure and rewrites the `WM_SIZING` rectangle Windows proposes on every
mouse move of an interactive resize. A Qt native event filter cannot do this:
`WM_SIZING` is sent directly to the window procedure, not posted to the
message queue, so the filter never sees it. The lock also snaps the initial
window to 16:10, because Qt shrinks the 1440 x 900 window to fit smaller
screens without keeping its shape. Windows itself then keeps the client area
at 16:10, so the dragged border tracks the pointer and the opposite border
stays still. For a corner drag, the axis that moved further drives the size.
The minimum is the window's `minimumWidth` in physical pixels.

**At the minimum size, dragging inward does nothing.** The window stays
exactly where it is instead of shrinking and snapping back; dragging outward
still grows it.

Maximized, snapped and fullscreen windows are sized by the system and are not
16:10; the canvas is letterboxed in those states.

Other platforms have no hook to constrain an interactive resize (Wayland gives
clients no aspect-ratio control at all), so the lock is not installed there
and every window shape is letterboxed.

Never correct the window size from QML or Python after the fact, for example
from `onWidthChanged` or a timer. The window manager is still driving the drag
and reasserts its own size on the next mouse move, so the border jumps back
and forth, or snaps back to the previous size.

## Common scaling failures

### Jitter or snapping back while resizing

**Cause:** Code changes native window dimensions while the window manager is
already moving or resizing the window. A module that rescales from
`onWidthChanged` or a timer snaps back to its previous size when one border
is dragged, because the window manager reapplies the untouched axis.

**Fix:** Use `ScaledWindow` and `install_window_scaling`. They constrain the
size before the window manager applies it (`WM_SIZING` on Windows), or
letterbox. Do not assign window geometry in response to a geometry change.

### Large blank areas in fullscreen or on a tall window

**Cause:** The window itself is not 16:10, but the canvas is intentionally
preserved at 16:10.

**Fix:** This is expected letterboxing. Do not stretch either scale axis or
reflow child controls to fill the extra area.

### Text or controls changing size independently

**Cause:** A child uses a size binding tied to the live window dimensions, or
a font size is changed dynamically.

**Fix:** Remove the child-level responsive binding. Scaling must happen only at
the `designCanvas` transform. Font and token values remain the values defined
by the UI style guide.

## Verification checklist

- Test at 720 x 450, 1440 x 900, and a larger 16:10 size such as 1920 x 1200.
- On Windows 11, drag each border and each corner. The window must stay 16:10
  throughout the drag, the dragged border must follow the pointer, and the
  opposite border must not move.
- At 720 x 450, drag each border and corner inward. The window must not move
  or change size.
- On Windows 11, drag below the minimum size and across monitors with
  different display scaling.
- Move the window by its title bar near a screen edge. It must not jitter.
- Maximize, snap and fullscreen the window. The canvas must remain centered
  and proportionally identical, with letterboxing when required.
- Verify that `AppButton`, `SafetyButton`, and `HelperText` remain unchanged.

## Change policy

The reference dimensions, canvas transform and minimum size live only in
`ui/ScaledWindow.qml`; the aspect lock lives only in `ui/aspect_lock.py`. A
change there changes every module, so review it with each module's owner.
Changes to colors, font sizes, radii, or spacing belong in the UI style guide
and are outside the scaling mechanism.
