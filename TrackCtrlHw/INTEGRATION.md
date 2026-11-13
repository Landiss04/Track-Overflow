# Track Controller HW: Phase 5 integration

2026-10-21. This guide records implementation on
`claude/quirky-fermi-sickg4`; normative facts remain on `truth`.

The host owns the window and a `RemoteTrackController` implementing the
existing controller interface. `ModuleLink` implements the design's
`HarnessEndpoint` role: it receives STEP and supplies the harness time as
the HW `time_s`. `HardwareRelay` and `SerialTransport` implement the relay
and design's `PiSerialLink` role. On the Pi,
`PiLinkServer` drives `HwTrackController`, `Wayside` and the PLC engine.
There is no Pi clock. Production discovery uses the K5 USB serial identity;
a missing Pi holds readiness and the whole clock. A simulated local agent is
an explicit development/test selection, never an automatic fallback.

## Source merges and design

PR #43's source branch was merged as `8407baf`; the GitHub PR was left open.
Braden's WP2 design was merged separately as `2335197`. The design's Pi/core
and host/window split is followed. PR #43 implements two independently
compiled PLC channels and five-bit `SPD_n_0..4`/`CMD_n_0..4`. It contains no
generated read-only vital PLC block. Kevin's K3b says all HW safety lives in
PLC code, so the test programs carry it. The design's planned generated vital
block remains for Harry and Braden to confirm. Kevin confirmed the no-vital policy covers SW too. No SW vital logic was
changed under the original implementation scope; that mismatch remains a
separate SW owner follow-up.

## Integration test copies

The three `data/waysides/red_wayside_*_integration_test.json` databases and
matching `data/plc/*.plc` files are explicitly **not Braden's files**. He must
replace or approve them. Every database block is an exact cut of
`TrackModel/red_line.json`, including `next_blocks`.

| Wayside | Blocks | Count |
| --- | --- | --- |
| Red-1 | 1–24, 73–76 | 28 |
| Red-2 | 25–45, 67–72 | 27 |
| Red-3 | 46–66 | 21 |

All 76 Red blocks belong to exactly one database. Blocks 9 and 75 stay in the
same wayside. Switch listed rows and their points stay in one wayside.

Programs keep switches NORMAL at rest, hold a reported reverse position
while an occupied point locks it, reject correspondence failures on switch
approaches, set signal aspects, hold closures at zero, and activate crossings
11/47 when their own block or either neighbor is occupied. They apply the SW
starter's occupied-own-block separation rule, preserving an empty next
block's preload. Every five-bit speed is capped to the block limit rounded
down to whole m/s in the PLC, and held authority sends zero speed.

`Block.next_blocks` preserves read-only adjacent occupancy inputs across
wayside boundaries. This does not transfer output ownership. Edge mappings
must provide the full Red occupied set, including failures as occupied;
filtering it to a territory would remove safety inputs. As in the existing
boundary, absence from the occupied set means clear: there is no separate
presence bitmap. A disconnected harness module holds clock advancement; no
missing-data fallback is introduced.

## Red yard and owner decisions

Kevin confirmed the yard connects physically to Red block 9, section C.
Adjacency now puts `yard` on 9 and removes it from 75. The original
`75-yard` switch text remains unchanged for the Track Model owner and Braden.
Readers consistently interpret that authoritative Red-9 row as point 9,
NORMAL toward block 10 and REVERSE toward the yard. The NORMAL leg is an
explicit integration assumption awaiting those owners, not a settled source
correction. The Track Model, HW territory, harness device map and SW layout
reader agree. The SW reader change is topology only.

A NORMAL-only starter run reaches station 16 and holds a 45 s dwell. It does
not establish a complete Red return: the return route eventually needs a
switch at 52 reversed. Automatic Red turnback has not been demonstrated.

## Verification

`QT_QPA_PLATFORM=offscreen python -m pytest -q tests` from `TrackCtrlHw`:
80 passed and 50,506 subtests. The pre-repair baseline was 73 passed and
48,074 subtests, with one known missing-`next_blocks` failure; that failure is
repaired. `test_red_integration.py` checks exact coverage, all-switch reader
agreement, all 32 speed-bit values on every Red block, crossings,
cross-boundary separation, closures, correspondence and occupied locking.

SW layout tests: 25 passed. Track Model layout tests: 19 passed. These are
targeted checks, separate from the wider integration handover's final suites.
Use the project virtual environment and offscreen Qt for local verification;
socket/process tests need a host environment allowing local IPC.

Pi setup instructions are in `documents/pi-owner-setup.md`. They are untested
on hardware. USB timing, owner provisioning and executable packaging remain
steps 10–12 and have not started.
