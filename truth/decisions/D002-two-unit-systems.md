# D002-two-unit-systems

**Status:** current
**Owner:** Kevin
**Provenance:** asserted by Kevin 2026-09-25; temperature exception removed by Kevin 2026-09-30
**Aliases:** unit split, metric backend imperial UI, display units decision
**Last updated:** 2026-09-30

## Context

The project mixes unit systems. The course material and the layout file format use
metric; the operators the UI is written for read imperial. Earlier code and documents
drifted between the two — telemetry was rendered in m/s in one place and mph in
another, and the style guide pointed at a units file that had never existed at the
path it named. Without one rule, every readout and every interface signature becomes
an independent judgment call.

## Decision

Two unit systems, split at the display layer. The backend has no exception; the UI has one.

- **Backend is metric SI.** Everything stored, computed, or passed across a module
  boundary is metric, temperature included (Celsius).
- **UI is imperial.** Everything a user sees is imperial. **Exception: power is
  displayed in kilowatts**, never horsepower.
- **Conversion happens at the display layer only.** State, signals, and interface
  payloads are never converted. A value crossing a module boundary is always in its
  backend unit.

The full quantity-by-quantity tables and the conversion factors are recorded in
[`../conventions/units.md`](../conventions/units.md). That entry, not this one, is the
lookup surface; this file records why the split exists.

## Consequences

- A quantity carries its unit in its identifier name, so the side of the boundary a
  value is on is visible at the call site: `speed_mps` in the backend, `speed_mph` at
  the display layer. See `conventions/naming.md`.
- Unit conversion is a display-layer concern with no place in domain logic. In the
  Train Model UI this is already the shape — `mph()` and `ft()` helpers in
  `TrainModel/ui/MainView.qml`, with state left metric.
- Where a layout file supplies a non-canonical unit, the loader converts on read.
  Nothing downstream sees the file's unit.
- Temperature is converted like every other quantity: °C in the backend, °F in the UI.
- The unit questions once open against this decision — authority, gradient, backend
  temperature, and four UI display units — are resolved in `conventions/units.md`
  `## Resolved`. The track layout file format is resolved as JSON.
- Documents that named units independently have been repointed at
  `conventions/units.md` rather than restating it — `truth/ui/style-guide.md` §6.5. Any future
  document needing units cites that entry; it does not copy the tables.

## Supersedes

- Backend exception: previously temperature was Fahrenheit, backend included; now the
  backend is Celsius with no exception (Kevin 2026-09-30, adopting `common/Units.md` on
  development, `35e6c77`).
