# Conventions

## Naming

*Unpopulated.*

## Units

**Status:** current
**Owner:** Kevin
**Provenance:** asserted by Kevin 2026-09-25; quantity list migrated from `common/Units.md`
**Aliases:** units, unit conventions, measurement units
**Last updated:** 2026-09-25

Two unit systems exist and they are not interchangeable. Everything that is stored,
computed, or passed across a module boundary is metric SI, with temperature as the
single exception — temperature is Fahrenheit everywhere, backend included. Everything
a user sees is imperial, with power as the single exception — power is displayed in
watts.

Conversion happens at the display layer only. State, signals, and interface payloads
are never converted. A value that crosses a module boundary is always in its backend
unit.

### Backend units

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
| Authority       | block ID        | string | Destination block up to which the train may travel |
| Acceleration    | meters/second²  | m/s^2  |                                                    |
| Force           | Newtons         | N      |                                                    |
| Mass            | kilograms       | kg     |                                                    |
| Power           | Watts           | W      |                                                    |
| Passenger count | integer         | persons|                                                    |

### UI display units

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
| Authority       | block ID        | string | Not a measurement; unchanged                         |
| Acceleration    | feet/second²    | ft/s^2 |                                                      |
| Force           | pound-force     | lbf    |                                                      |
| Mass            | short tons      | ton    |                                                      |
| Power           | kilowatts       | kW     | Exception to imperial. Never horsepower              |
| Passenger count | integer         | persons| Not a measurement; unchanged                         |

### Conversion factors

Backend → UI. Multiply by the factor unless the formula column says otherwise.

| Quantity     | From  | To     | Factor / formula          |
|--------------|-------|--------|---------------------------|
| Speed        | m/s   | mph    | × 2.236936                |
| Distance     | m     | ft     | × 3.280840                |
| Elevation    | m     | ft     | × 3.280840                |
| Acceleration | m/s^2 | ft/s^2 | × 3.280840                |
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
| metric tonne | kg    | × 1000       |
| metric tonne | ton   | × 1.102311   |
| kg           | lb    | × 2.204623   |
| m            | mi    | × 0.000621371|

## Identifiers

*Unpopulated.*

## File and path conventions

*Unpopulated.*
