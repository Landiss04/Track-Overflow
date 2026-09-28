# Train Model UI Scaling Guide

## Purpose

The Train Model UI is a fixed visual composition, not a responsive layout.
When the window changes size, the entire composition must zoom uniformly. A
card, label, button, gap, font, border, and corner radius must retain its
position and proportion relative to every other element.

The reference canvas is **1440 x 900**. This is the size declared by
`refrence-docs/UIwireframe.css`, and it is a 16:10 aspect ratio.

## Implementation

`ui/Main.qml` owns scaling. Its `designCanvas` remains 1440 x 900, and its
`Scale` transform applies the same factor to both axes:

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

The minimum window size is 720 x 450, which renders the canvas at 0.5x.

## Aspect-ratio locking

The UI targets Windows 11. There, `train_model/aspect_lock.py` subclasses
the window procedure and rewrites the `WM_SIZING` rectangle Windows proposes
on every mouse move of an interactive resize. A Qt native event filter cannot
do this: `WM_SIZING` is sent directly to the window procedure, not posted to
the message queue, so the filter never sees it. The lock also snaps the
initial window to 16:10, because Qt shrinks the 1440 x 900 window to fit
smaller screens without keeping its shape. Windows itself then keeps the
client area at 16:10, so the dragged border tracks the pointer and the
opposite border stays still. For a corner drag, the axis that moved further
drives the size. The ratio comes from `referenceWidth` and `referenceHeight`
in `Main.qml`, and the minimum is `minimumWidth` in physical pixels.

Maximized, snapped and fullscreen windows are sized by the system and are not
16:10; the canvas is letterboxed in those states.

Other platforms have no hook to constrain an interactive resize (Wayland gives
clients no aspect-ratio control at all), so the lock is not installed there
and every window shape is letterboxed.

Never correct the window size from QML or Python after the fact, for example
from `onWidthChanged` or a timer. The window manager is still driving the drag
and reasserts its own size on the next mouse move, so the border jumps back
and forth.

## Common scaling failures

### Jitter while moving or resizing

**Cause:** Code changes native window dimensions while the window manager is
already moving or resizing the window.

**Fix:** Constrain the size before the window manager applies it
(`WM_SIZING` on Windows), or letterbox. Do not assign window geometry in
response to a geometry change.

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
by `documents/UI_Style_Guide.md`.

## Verification checklist

- Test at 720 x 450, 1440 x 900, and a larger 16:10 size such as 1920 x 1200.
- On Windows 11, drag each border and each corner. The window must stay 16:10
  throughout the drag, the dragged border must follow the pointer, and the
  opposite border must not move.
- On Windows 11, drag below the minimum size and across monitors with
  different display scaling.
- Move the window by its title bar near a screen edge. It must not jitter.
- Maximize, snap and fullscreen the window. The canvas must remain centered
  and proportionally identical, with letterboxing when required.
- Verify that `AppButton`, `SafetyButton`, and `HelperText` remain unchanged.

## Change policy

Keep the reference dimensions and transform in `ui/Main.qml` and the aspect
lock in `train_model/aspect_lock.py`. Changes to colors, font sizes, radii,
or spacing belong in the UI style guide and are outside the scaling mechanism.
