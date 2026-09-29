# D002-two-unit-systems

**Status:** current
**Owner:** Kevin
**Provenance:** asserted by Kevin 2026-09-25
**Aliases:** unit split, metric backend imperial UI, display units decision
**Last updated:** 2026-09-29

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
- Open unit questions are recorded as conflicts in `conventions/units.md`:
  authority as a distance vs. a block ID, gradient in degrees vs. percent, backend
  temperature, and four UI display units (see `## Conflict` below). The track layout
  file format is resolved as JSON.
- Documents that named units independently have been repointed at
  `conventions/units.md` rather than restating it — `truth/ui/style-guide.md` §6.5. Any future
  document needing units cites that entry; it does not copy the tables.

## Conflict

Owner: Kevin.

Both exceptions in this decision are contested by `common/Units.md` on development
(`35e6c77`, brabosil3, 2026-09-26), written the day after this decision: it stores
temperature in Celsius and displays power in horsepower. It also differs on mass,
acceleration, and force display units. Each value and its provenance is in
`conventions/units.md` `## Conflict`.
