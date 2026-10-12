**Target:** truth/conventions/units.md
**Action:** replace
**Proposed by:** Claude on ctc-interfacing
**Provenance:** asserted by Kevin 2026-09-25 and resolutions by Kevin 2026-09-30, unchanged; authority as a count of blocks per D013 (team decision including Kevin, asserted by Landis 2026-10-06)

---

# units

**Status:** current
**Owner:** Kevin
**Provenance:** asserted by Kevin 2026-09-25; quantity list migrated from `common/Units.md` as it stood before `35e6c77`; cross-checked against `common/interfaces.py` unit suffixes and `documents/srs-filled.md`; gradient, temperature and display-unit conflicts resolved by Kevin 2026-09-30; authority as a count of blocks per D013 (team decision including Kevin, asserted by Landis 2026-10-06)
**Aliases:** units, unit conventions, measurement units
**Last updated:** 2026-10-06

Two unit systems exist and they are not interchangeable. Everything that is stored,
computed, or passed across a module boundary is metric SI, with no exception.
Everything a user sees is imperial, with power as the single exception — power is
displayed in kilowatts.

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
| Temperature     | Celsius         | °C     | Ambient and cabin temperature                      |
| Authority       | integer         | blocks | Blocks ahead of the current block the train may still enter; 0 = stop before leaving the current block. See D013 |
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
| Temperature     | Fahrenheit      | °F     |                                                      |
| Authority       | integer         | blocks | A count, not a measurement; unchanged                |
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
| Force        | N     | lbf    | × 0.2248089               |
| Mass         | kg    | ton    | × 0.001102311             |
| Power        | W     | kW     | × 0.001                   |
| Temperature  | °C    | °F     | °F = °C × 9/5 + 32        |

Reverse conversion (UI → backend) divides by the same factor. Temperature is the one
formula that is not a plain factor: °C = (°F − 32) × 5/9. Conversions are exact to the
digits shown; do not round the factor before applying it, round the displayed result
instead.

Supporting factors, for reference when a value arrives in a non-canonical unit:

| From         | To    | Factor / formula                 |
|--------------|-------|----------------------------------|
| grade %      | deg   | deg = atan(% ÷ 100) × 180 ÷ π    |
| km/h         | m/s   | ÷ 3.6                            |
| metric tonne | kg    | × 1000                           |
| metric tonne | ton   | × 1.102311                       |
| kg           | lb    | × 2.204623                       |
| m            | mi    | × 0.000621371                    |

Grade percent is rise over run, not a scaled angle, so the gradient conversion is an
arctangent and not a factor.

## Resolved

**Authority — count of blocks.** D013, team decision including Kevin, 2026-10-06.
Authority is the number of blocks ahead of the train's current block that it may still
enter before it must stop, as a non-negative integer. It overrides the distance reading
in `srs-filled.md` §1.3, `requirements-matrix.md` §2 and the `authority_m: float` fields
in `common/interfaces.py`, and the block-ID reading in `common/Units.md` on development
(`35e6c77`).

**Gradient — degrees.** Kevin 2026-09-30. The backend stores degrees, as
`common/interfaces.py` `BlockState.grade_deg` carries. Layout files give grade in percent
(`srs-filled.md` Appendix A, `grade_percent` in `TrackModel/*.json`); the loader converts
on read with the formula above, and nothing downstream sees percent. The percent row in
`common/Units.md` on development (`35e6c77`) does not stand.

**Temperature — Celsius backend, Fahrenheit display.** Kevin 2026-09-30, adopting
`common/Units.md` on development (`35e6c77`). D002 no longer carries a temperature
exception.

**UI display units — power, mass, acceleration, force.** Kevin 2026-09-30. The table above
stands: kW, short tons, ft/s², lbf. The hp, lb, mph/s and hidden-force values in
`common/Units.md` on development (`35e6c77`) do not stand.

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

## Supersedes

- Backend temperature: previously Fahrenheit, the single exception to metric (D002);
  now Celsius (Kevin 2026-09-30).
- Authority: previously a block ID naming the destination block (Kevin 2026-09-30); now
  a count of blocks, per D013 (2026-10-06).
