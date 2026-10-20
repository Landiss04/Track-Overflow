# Train Model open issues

Reviewed against current code on October 20, 2026. Accepted design comes from
[SDD v0.2](../../documents/Railway_Sim_SDD_Train_Model.md) and Kevin Schillinger’s
review. New truth proposals await human promotion; this file records status.

## Implementation reconciliation

The following concurrent edits are present in the inspected working tree. Their
presence is source-inspection evidence, not a claim that local checks passed.

| Area | Accepted design | Inspected implementation |
|---|---|---|
| Simultaneous brakes | Independent engagement; sum both engaged configured forces. Service failure blocks service only. | `model.py` now reports independent states and sums forces. |
| Beacon bound | Complete ASCII JSON array `[station_name, platform_side, underground]`, at most 128 characters; reject without truncation. | `utils/beacon_codec.py` enforces the complete payload in model validation and local producers/edges. Keep typed/named envelopes. See [encoding](module-interface.md#beacon-payload-encoding). |
| Integrated clock | Display harness time; independently check every 15 harness ticks, including rejected trains. | `module_process.py` holds fixed creation epochs; `fleet.py` fans out time; `state.py` compares at `1e-6 s` tolerance; `Main.qml` displays selected-train diagnostics. See [clock contract](integration.md#integrated-time-reconciliation-and-drift). |
| Arrival row | Remove arrival; retain next station/platform and fleet identity/line. | Current `MainView.qml` omits arrival; `fleet.py` and `state.py` supply ID and line. |

## Remaining integration dependencies

- Phase 2 wires the Track Model process with direct harness edges
  (`common/harness/track_edges.py`), which check every beacon with
  `utils/beacon_codec.py`; the fixed feed is gone. A scripted wayside still stands
  in for the Track Controller, so the commanded speed and authority the Train Model
  passes on are scripted until Phase 3. `track_model_edges.py` retains legacy
  catalog conversions, off the running path.
- Production boarding events must respect Track Model station ownership, and all
  beacon producers must apply the complete canonical payload bound.
- Backend/UI work has local verification sources, including `test_beacon_codec.py`
  and `test_integrated_clock.py`. This documentation task did not run product tests
  or establish their results. Exercise those paths as part of their implementation
  review, including rejected/late-created trains and midnight display wrapping.
- Truth proposals require human review/promotion, and existing diagram artifacts
  require author corrections. Neither is performed by this documentation task.

## Configured speed is not enforced here

`TrainConfig.v_max_mps` records 70 km/h (19.444… m/s). The Train Controller owns
speed regulation and enforcement (D009); do not add a physics velocity clamp.

## Resolved scope and ownership

- Keep the existing segmented numerical algorithm: exact constant-force segments,
  midpoint power-limited integration, event boundaries and fixed external dt.
- Maximum power is confirmed at 480 kW. Rolling resistance with existing
  `c_rr = 0.002` is the only passive resistance term in scope. Grade is gravitational
  force and brakes are commanded forces. Aerodynamic drag, wheel slip and brake
  build-up are outside scope; no real-world calibration study is claimed.
- Train Controller owns the door interlock. Train Model follows commands; there
  ownership is settled by Kevin’s review.
- Track Model sends boarding events only at stations. Train Model checks rest,
  open doors, valid counts and capacity without a station gate.
- Pickup failure already outputs commanded speed 0 m/s and authority 0 blocks,
  leaving terrain unaffected. Offset references the front of the train.
- Controller `passenger_brake_release` already clears the passenger latch without
  canceling its independently held emergency command. The window has no release.
- Train identity and line come from the fleet/harness roster. Arrival sourcing
  is no longer requested.

## Development and diagram follow-up

The standalone test UI is a developer utility. Its older 30-tick drift check is
separate from the integrated check. Existing tests are local developer
verification utilities; no enforcement policy is introduced.

The author must correct existing product use case diagrams to remove the testing
role and utility operations, add controller latch release, and align labels with
the reviewed integration and physics design. The [UML brief](uml-diagram-brief.md)
and [draw.io brief](uml-drawio-prompt.md) describe the corrections. Existing diagram
artifacts are unchanged.
