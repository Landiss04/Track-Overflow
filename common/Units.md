# Units

| Quantity | Frontend Unit | Backend Unit | Conversion (Backend -> Frontend) | Notes |
|---|---|---|---|---|
| Speed | mph | m/s | mph = m/s x 2.23694 | |
| Speed limit | mph | m/s | mph = m/s x 2.23694 | |
| Distance | ft | m | ft = m x 3.28084 | |
| Time | s | s | 1:1 | |
| Gradient | % | % | 1:1 | Matches `grade_percent` in TrackModel/*.json; positive = uphill in direction of travel |
| Elevation | ft | m | ft = m x 3.28084 | Above datum |
| Temperature | °F | °C | °F = °C x 9/5 + 32 | Ambient and cabin temperature |
| Authority | block ID | block ID | 1:1 | Destination block up to which the train may travel; not a physical unit |
| Acceleration | mph/s | m/s² | mph/s = m/s² x 2.23694 | |
| Force | N/A | N | N/A | Internal physics calculation only, not shown in UI |
| Mass | lb | kg | lb = kg x 2.20462 | |
| Power | hp | W | hp = W x 0.00134102 | |
| Passenger count | persons | persons | 1:1 | |

