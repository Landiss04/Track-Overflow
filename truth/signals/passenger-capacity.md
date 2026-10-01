# passenger-capacity

**Status:** current
**Owner:** Train Model
**Provenance:** `Train_Model_Backend_Design.pdf` §5.2 (Locked) and Interfaces table, supplied by Kevin Schillinger 2026-09-30
**Aliases:** Passenger Capacity, remaining capacity, boarding capacity
**Last updated:** 2026-09-30

## Definition

An integer count of the passengers the train can still take on. The Train Model reports
it to the Track Model at a station, computing it after it draws the disembark count.

## Notes

- Station sequence:
  1. The Train Model draws a disembark count, bounded by the passengers onboard.
  2. The Train Model reports the remaining capacity.
  3. The Track Model sends Passengers Boarded, which is at most that capacity.
  4. The Train Model recomputes its mass.
- Passengers onboard range from 0 to 222. Crew is fixed at 5, counted separately, and
  does not reduce passenger capacity.
- Disembark counts are not reported. Throughput is handled between the Track Model and
  the CTC Office.
- The source is the Train Model design. The Track Model owner has not confirmed it.
