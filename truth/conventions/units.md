# units

**Status:** current
**Owner:** Kevin
**Provenance:** asserted by Kevin 2026-09-25; quantity list migrated from `common/Units.md` as it stood before `35e6c77`; cross-checked against `common/interfaces.py` unit suffixes and `documents/srs-filled.md`
**Aliases:** units, unit conventions, measurement units
**Last updated:** 2026-09-29

Two unit systems exist and they are not interchangeable. Everything that is stored,
computed, or passed across a module boundary is metric SI, with temperature as the
single exception — temperature is Fahrenheit everywhere, backend included. Everything
a user sees is imperial, with power as the single exception — power is displayed in
kilowatts.

Conversion happens at the display layer only. State, signals, and interface payloads
are never converted. A value that crosses a module boundary is always in its backend
unit.

## Backend units

Canonical units for state, computation, and all cross-module signals.

| Quantity        | Unit            | Symbol | Notes                                              |
|-----------------|-----------------|--------|----------------------------------------------------|
| Speed           | meters/second   | m/s    |                                                    |
| Speed limit     | meters/second   | m/s    |                                                    |
| Distance        | meters          | m      |                                                    |
| Time            | seconds         | s      |                                                    |
| Gradient        | degrees         | deg    | Positive = uphill in direction of travel           |
| Elevation       | meters          | m      | Above datum                                        |
| Temperature     | Fahrenheit      | F      | Ambient and cabin temperature. Exception to metric |
| Authority       | meters          | m      | Distance the train may travel. **See Conflict**    |
| Acceleration    | meters/second²  | m/s^2  |                                                    |
| Force           | Newtons         | N      |                                                    |
| Mass            | kilograms       | kg     |                                                    |
| Power           | Watts           | W      |                                                    |
| Passenger count | integer         | persons|                                                    |

## UI display units

What every UI renders. Converted from the backend unit at the display layer.

| Quantity        | Unit            | Symbol | Notes                                                |
|-----------------|-----------------|--------|------------------------------------------------------|
| Speed           | miles/hour      | mph    |                                                      |
| Speed limit     | miles/hour      | mph    |                                                      |
| Distance        | feet            | ft     |                                                      |
| Time            | seconds         | s      | No imperial equivalent; unchanged                    |
| Gradient        | degrees         | deg    | No imperial equivalent; unchanged                    |
| Elevation       | feet            | ft     |                                                      |
| Temperature     | Fahrenheit      | F      | Already Fahrenheit in the backend; no conversion     |
| Authority       | feet            | ft     | Distance. **See Conflict**                           |
| Acceleration    | feet/second²    | ft/s^2 |                                                      |
| Force           | pound-force     | lbf    |                                                      |
| Mass            | short tons      | ton    |                                                      |
| Power           | kilowatts       | kW     | Exception to imperial. Never horsepower              |
| Passenger count | integer         | persons| Not a measurement; unchanged                         |

## Conversion factors

Backend → UI. Multiply by the factor unless the formula column says otherwise.

| Quantity     | From  | To     | Factor / formula          |
|--------------|-------|--------|---------------------------|
| Speed        | m/s   | mph    | × 2.236936                |
| Speed limit  | m/s   | mph    | × 2.236936                |
| Distance     | m     | ft     | × 3.280840                |
| Elevation    | m     | ft     | × 3.280840                |
| Acceleration | m/s^2 | ft/s^2 | × 3.280840                |
| Authority    | m     | ft     | × 3.280840                |
| Force        | N     | lbf    | × 0.2248089               |
| Mass         | kg    | ton    | × 0.001102311             |
| Power        | W     | kW     | × 0.001                   |
| Temperature  | F     | F      | none — Fahrenheit already |

Reverse conversion (UI → backend) divides by the same factor. Conversions are exact
to the digits shown; do not round the factor before applying it, round the displayed
result instead.

Supporting factors, for reference when a value arrives in a non-canonical unit:

| From         | To    | Factor       |
|--------------|-------|--------------|
| Celsius      | F     | × 9/5, + 32  |
| km/h         | m/s   | ÷ 3.6        |
| metric tonne | kg    | × 1000       |
| metric tonne | ton   | × 1.102311   |
| kg           | lb    | × 2.204623   |
| m            | mi    | × 0.000621371|

## Conflict

Owner: Kevin.

**Authority — distance vs. block ID. Open.**

| Value | Provenance |
|-------|-----------|
| meters (distance) | `srs-filled.md` §1.3 glossary ("the maximum distance a train is permitted to travel before stopping"); `requirements-matrix.md` §2 ("Authority (distance) from Wayside Controller"); `common/interfaces.py` — `TrackSignal.authority_m`, `set_commanded_signal`, `receive_suggestion`, `get_commanded_signal` all carry `authority_m: float` |
| block ID (string) | `common/Units.md` as migrated into this entry — "Destination block up to which the train may travel"; `common/Units.md` on development (`35e6c77`, brabosil3, 2026-09-26) — block ID in backend and UI, 1:1 |

The backend and UI tables above carry meters, because that is what three sources
including the agreed interface contract transport. The block-ID reading is recorded
here rather than discarded: two versions of `common/Units.md` assert it, the later one
dated after this entry was written, so it is not simply a superseded design. These are
not the same kind of value — one is a measurement that converts to feet for display,
the other is an identifier that does not convert at all — so this must be resolved,
not left ambiguous.

**Gradient — degrees vs. percent. Open.**

| Value | Provenance |
|-------|-----------|
| degrees | `common/Units.md` as migrated into this entry; `common/interfaces.py` — `BlockState.grade_deg` |
| percent | `srs-filled.md` Appendix A (layout file field "grade (%)"); `grade_percent` in `TrackModel/*.json`; `common/Units.md` on development (`35e6c77`, brabosil3, 2026-09-26) — % in backend and UI, 1:1 |

Degrees and percent are not the same quantity, so no conversion factor between them
is recorded here until the resolution says which one the backend stores. The agreed
interface contract carries `grade_deg`, which favors degrees; the layout files and the
later units table both carry percent.

**Temperature (backend) — Fahrenheit vs. Celsius. Open.**

| Value | Provenance |
|-------|-----------|
| Fahrenheit | D002 (asserted by Kevin 2026-09-25) — the single exception to metric |
| Celsius | `common/Units.md` on development (`35e6c77`, brabosil3, 2026-09-26) — °C backend, °F display, °F = °C × 9/5 + 32 |

**UI display units — four quantities. Open.**

| Quantity | This entry and D002 | `common/Units.md` on development (`35e6c77`, brabosil3, 2026-09-26) |
|----------|---------------------|-----|
| Power | kW — "never horsepower" (D002 exception) | hp, × 0.00134102 |
| Mass | short tons, × 0.001102311 | lb, × 2.20462 |
| Acceleration | ft/s², × 3.280840 | mph/s, × 2.23694 |
| Force | lbf, × 0.2248089 | not shown in the UI |

The tables above carry this entry's values until the conflicts are resolved. The
later table was written the day after D002, on `main`, and has not been reconciled
with it.

## Resolved

**Track layout file format — JSON.** `srs-filled.md` §3.1.3 REQ-INTF-012 and
Appendix A on development (`c058082`) specify JSON files loaded at startup, matching
the layout files in `TrackModel/`.

**Speed — m/s.** `srs-filled.md` Appendix A gives the layout file field "speed limit
(km/h)". That is an input-format difference only: the loader converts on read and
nothing downstream sees km/h. The backend unit for speed is m/s, as recorded above.

The style documents are not a source of unit conflicts. `MAX_SPEED_KMH`,
`speed_kmh`, and `grade_percent` in `Coding Standards (Group).docx` and
`PYTHON_STYLE_GUIDE.md` illustrate the naming format — that a unit belongs in the
name — and do not assert which unit a quantity carries.
