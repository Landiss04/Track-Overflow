# no-automatic-reversal

**Status:** current
**Owner:** Landis
**Provenance:** asserted by Landis 2026-10-06 (reversing is not supported yet; flag it to the dispatcher with a popup when a train would need to)
**Aliases:** reversal alert, train reversal, reverse direction, turn back
**Last updated:** 2026-10-06

## Definition

The CTC Office never reverses a train. When a train is held by something that will not
clear by itself (see [reroute-around-blockage](reroute-around-blockage.md)) and the only
way round means reversing, the train waits, and the CTC Office alerts the dispatcher
with a popup. The popup names the train, what holds it, and the block where it would
have to reverse.

The dispatcher can select the train or dismiss the alert. A dismissed alert does not
come back unless the situation clears and then happens again.

## Notes

- The dispatcher decides what to do: reroute the train, clear the way, or reverse it
  by hand.
- A train reverses only in a block it may leave by the end it came in by, under the
  directions of travel in the layout files.
