# D002-two-unit-systems

**Status:** current
**Owner:** Kevin
**Provenance:** asserted by Kevin 2026-09-25
**Aliases:** unit split, metric backend imperial UI, display units decision
**Last updated:** 2026-09-25

## Context

The project mixes unit systems. The course material and the layout file format use
metric; the operators the UI is written for read imperial. Earlier code and documents
drifted between the two — telemetry was rendered in m/s in one place and mph in
another, and the style guide pointed at a units file that had never existed at the
path it named. Without one rule, every readout and every interface signature becomes
an independent judgment call.

## Decision

Two unit systems, split at the display layer, each with exactly one exception.

- **Backend is metric SI.** Everything stored, computed, or passed across a module
  boundary is metric. **Exception: temperature is Fahrenheit**, backend included.
- **UI is imperial.** Everything a user sees is imperial. **Exception: power is
  displayed in watts** (as kilowatts), never horsepower.
- **Conversion happens at the display layer only.** State, signals, and interface
  payloads are never converted. A value crossing a module boundary is always in its
  backend unit.

The full quantity-by-quantity tables and the conversion factors are recorded in
[`../conventions.md`](../conventions.md) `## Units`. That entry, not this one, is the
lookup surface; this file records why the split exists.

## Consequences

- A quantity carries its unit in its identifier name, so the side of the boundary a
  value is on is visible at the call site: `speed_mps` in the backend, `speed_mph` at
  the display layer. See `## Naming` in `conventions.md`.
- Unit conversion is a display-layer concern with no place in domain logic. In the
  Train Model UI this is already the shape — `mph()` and `ft()` helpers in
  `TrainModel/ui/MainView.qml`, with state left metric.
- Where a layout file supplies a non-canonical unit, the loader converts on read.
  Nothing downstream sees the file's unit.
- Three unit questions remain open and are recorded as conflicts in
  `conventions.md` `## Units`: authority as a distance vs. a block ID, gradient in
  degrees vs. percent, and the track layout file format that the gradient question
  depends on.
- Documents that named units independently have been repointed at
  `conventions.md` rather than restating it — `documents/UI_Style_Guide.md` §6.5 and
  `documents/ui-style-guide-preview.html`. Any future document needing units cites
  that entry; it does not copy the tables.
