# Train-Ctrl_HW — open issues for review

Found but not fixed. Each entry says what goes wrong and where, so it can be
picked up later. Grouped by who has to act; numbers are kept, so references
from `REQUIREMENTS.md` and the code stay valid. Last reviewed 2026-10-24,
against `claude/quirky-fermi-sickg4` `f6ed1a1` and truth `84c7d44`
(`REQUIREMENTS.md` M0–M21; M5 is merged into M3).

## Waiting on other owners or branches

19. **Module rules are not recorded outside this folder.** Rules M0–M21
    in `REQUIREMENTS.md` are in neither truth's Train Controller contract
    (still a placeholder) nor the SRS. Update the documentation later.

23. **Brake and engine resolution cannot be seen while the emergency brake
    is on.** Blocks M3. On detection the controller latches the
    e-brake, and the pills are meant to clear before the driver releases
    it. But on `development` (`TrainModel/docs/physics.md` §3–4):
    - the Train Model reports the service brake as **not engaged whenever
      the e-brake is engaged**, so a repaired service brake never reads
      applied;
    - the e-brake force (about 140 kN) is far above full traction (about
      25.7 kN), so a repaired engine can never show rising speed.

    Signal pickup is unaffected (a non-zero Track Signal can return at any
    time). Decided in part (R29, M2, M3): once the train stands, the
    driver may release the e-brake in Manual with the failure still
    latched, and the failure does not engage it again. That lets a
    repaired service brake read applied, since the driver may command it
    under a brake failure (M4, R32), and the controller then concludes
    the brake failure resolved (#44). It does not settle the engine: a
    latched failure keeps the target at 0, so no power is commanded and
    §4's "commanded power gives rising speed again" cannot happen.
    Candidate approaches for the rest, none chosen:
    - (a) Once stopped, hold an engine failure on the service brake
      instead of the e-brake, and probe with power.
    - (b) Once stopped, briefly drop the controller's e-brake command and
      probe: command the service brake for a brake failure, a little power
      for an engine failure. Risk: rollback on a grade.
    - (c) Ask Kevin to report the service brake's state independently of
      the e-brake.

27. **Signal light ahead** (M20). Mapped on `claude/quirky-fermi-sickg4`,
    from the Track Model directly (`aspect_to_train_controller`), and truth
    now has `signals/signal-aspect-ahead`. Truth spells the fourth aspect
    `SUPER_GREEN`; this controller accepts only `"SUPER GREEN"`, so the
    harness converts it. Closes when that branch merges, unless the
    controller takes truth's spelling.

35. **This module has diverged on `claude/quirky-fermi-sickg4`.** That
    branch runs this module as both Train Controller variants (M13):
    `train_ctrl/module_process.py` for the harness, and `common/hw_link`
    for the Pi. But its copy of `Train-Ctrl_HW` is older than this
    branch's: the toy plant is still inside `control.py`; its harness
    edge still sends one `brake_state` [emergency, service] input, not
    M18's two; its engine-failure rule is the steady-fall check (#28); and
    it has none of M21, the M6 / M7 boarding or the Cab controls panel.
    The two need reconciling before integration; that touches another
    branch, so it waits for the owners.

## Controller: to decide or build

26. **Which simulator the bench uses.** The bench's simulation is
    separate (`bench_sim.py` `SimTrain`, R15), still the toy plant. Not
    decided:
    - (a) keep the toy plant (Euler, rolling resistance only under a brake
      failure, no grade; its service brake state does not go false under
      the e-brake as the Train Model's does); or
    - (b) reuse the Train Model's pure-Python `train_model.model.TrainModel`
      from `development` inside `SimTrain`: one physics, with real rolling
      resistance and grade. D005 says modules do not import each other's
      boundary types, so this needs a team decision.

28. **Engine-failure detection false-positives; the accepted rule is not
    on this branch.** This branch still has the old rule (power that
    should pull 0.1 m/s² by `F = P/v`, speed not up 0.05 m/s in 2 s),
    which flags a healthy full train 2.4–2.9 s onto a +2 % or +5 % grade.
    Kevin accepted a replacement on 2026-10-21 (R91), built on
    `claude/quirky-fermi-sickg4` and proposed there for truth
    (`truth/_inbox/claude/quirky-fermi-sickg4/20261021-1220-engine-failure-steady-fall-accepted.md`):
    never within 0.05 m/s of the target; otherwise latch only when, over a
    6 s window, power is above 0 on every tick, no brake is commanded or
    reported on any tick, and the half-second speed means fall by more
    than 0.05 m/s, each within 10 % of that fall of a straight line. Port
    it here (#35); `REQUIREMENTS.md` §4 states it. Its own limits: a stationary dead engine is not
    flagged, and a heavy train that cannot hold speed on Green 7's 5 %
    grade can be.

    Measured 2026-10-21: this controller against `development`'s
    `TrainModel` (`de7a98f`), grades from `Track_layout/` (Green ±5 %,
    Red ±2 %), commanded 15 m/s. Worst speed fall over a window with
    power above 0, no brake, and outside a 0.1 m/s band of the target:

    | Case | 2 s | 3 s | 4 s | 5 s |
    |---|---|---|---|---|
    | Healthy, flat | 0 | 0 | 0 | 0 |
    | Healthy, onto +2 %, full load | 0.19 | 0.23 | 0.26 | 0.27 |
    | Healthy, onto +5 %, crew only | 0.44 | 0.50 | 0.53 | 0.53 |
    | Healthy, onto +5 %, full load | 0.55 | 0.67 | 0.74 | 0.81 |
    | Engine failed, flat (any load, 5 or 15 m/s) | 0.04 | 0.06 | 0.08 | 0.10 |
    | Engine failed, +2 % | 0.43 | 0.65 | 0.86 | 1.08 |
    | Engine failed, +5 % | 1.02 | 1.53 | 2.04 | 2.55 |

    (m/s; a 0.05 or 0.2 m/s band changes these by under 0.1.) On the
    flat a dead engine loses only rolling resistance (0.0196 m/s²), less
    than a healthy full train loses under full power on +5 %. On the
    bench nothing falls at all: the bench simulation has no resistance,
    so a dead engine coasts at constant speed.

34. **E-brake left off in Automatic with a failure latched** (R31, to
    test later). The driver releases the emergency brake in Manual at a
    stand, failure still latched, then switches to Automatic: the brake
    stays off, and the train is held only by the 0 target (and the
    service brake if it moves). That follows M3 ("does not engage it
    again"). To decide after testing: keep it, or have Automatic engage
    it again while a failure is latched.

## Bench and console

31. **Setting the bench clock is a jump.** The lights act only if the
    jump changes night to day or back. 05:00 (the start) to 18:00 is night
    to night, so nothing changes; set a daytime first, or 17:59 and let
    the clock run.

32. **Choices made without a specification, for review:**
    - Wording: "The train *id* is departing from *station*" (the request
      said "train *id* is departing", without "The").
    - The bench sends a beacon once after any beacon row is sent, so
      setting underground alone works. Sent with no authority, no
      commanded speed and the train standing, that beacon is an arrival
      (M6), as a real one would be.
    - Lights: both interior and exterior switch together.
    - The bench's hours wheel runs 0–23, not 0–24 as asked: 24:00 is
      00:00, and 24:30 is not a time of day (R27).
    - Switching to Manual during a brake failure (R26) lets the driver ask
      for the service brake (the button is live, R32; the e-brake can be
      released in Manual at a stand, R31); once the bench clears its
      injected failure, the service brake answers and the controller
      resolves the failure (#44).
    - With an uncommissioned train selected nobody is signed in, so
      nobody can reach its emergency brake from the console; it commands
      0 W and cannot move under its own power.
    - A station stop or an open door holds the train by setting its
      target to 0 (M6), so in Manual the driver sets a speed again once
      the doors have closed.

33. **What the cut-off text scan cannot see** (R23). It catches text Qt
    elides and text drawn past the window's edge, at the states the
    self-check reaches. It does not catch text overlapping a neighbour
    inside the window, or a state the check never reaches (a very long
    station name, say).

36. **The bench header runs out of room with five pills or more.** With
    the mode, Underground, E-brake, a failure and the Station dwell pill
    all showing, the bench's time wheels push its clock and **Set time**
    past the window edge. The console's header has no time wheels and
    fits.

43. **The bench does not stand in for the rest of the system** (reported
    2026-10-24). Its job is to simulate the controller's inputs, and how
    they would behave with the whole system, without the other modules
    connected: it substitutes for every connected module. Where it falls
    short today:
    - **Timing.** It answers each command on the next tick; the harness
      answers two ticks later. The controller allows for it (`echo_ticks`,
      #42), but a rule tested only on the bench is tested at one tick.
    - **Train Model physics.** The toy plant has no grade, no load and no
      rolling resistance outside an injected brake failure, so a dead
      engine coasts at constant speed and neither engine rule can trip at
      a cruise (#26, #28).
    - **Train Model reports.** Its service brake state does not go false
      while the e-brake is engaged, as the Train Model's does (#23); its
      passenger pull lasts one tick and is never latched, where the
      Train Model's holds until the e-brake command goes off (#25,
      closed).
    - **Track Model, Track Controller and CTC Office.** There is no track:
      authority changes only with the Block change button, commanded
      speed and the signal ahead only when edited, and the beacon only
      with the `at_station` row. Nothing moves the train through blocks,
      stations and signals as the rest of the system would.
    - **Failures.** Clearing an injected engine or signal pickup
      failure clears it in the controller directly (M0, M3), so the bench
      never exercises how the integrated controller would see those
      resolved (#23). A brake failure the controller resolves itself
      (#44).

    Reusing the Train Model's physics (#26 (b)) would close the physics
    and report gaps; the track side needs a track to run on.

## Outside the style guide and shared UI

37. **Service-brake amber and the 72 px hero readouts** (`brake_service` and
    `size_hero` in `train_ctrl/console_theme.py` `PENDING_TOKENS`) are
    outside the style guide; the proposal that carried both was removed
    from the inbox (`69b5cc9`).

38. **Other sizes kept to Ivan's design but outside the style guide**
    (restored 2026-10-07 at Jonathan's request): the speed and temperature
    dial figures are computed from the dial radius (`Math.max(32, r * 0.6)`
    and `Math.max(30, r * 0.66)`) rather than a token, and the door and
    light tiles are 52 px tall (the guide's control heights are 28 / 36 /
    44) with Label-token text instead of the button type scale.

39. **Local near-duplicates of shared components** — `ConsoleHeader`
    (ModuleHeader plus `alerts` and the dwell pill), `HeroReadout`,
    `BrakeButton`, `SignalEditRow`, and `TrainPicker` — each needs a
    change to the shared `ui/` folder to retire or share.

40. **Kp/Ki unit labels are SI** ("W per m/s", "W per m"); converting them
    changes the numbers engineers type.

## Repository and checks

21. **The self-check is timing-sensitive.** Several `check.py` sections
    wait on wall-clock deadlines (`_until`) while the control timer runs.
    On a loaded machine the timer is starved and checks fail that pass
    alone: on 2026-10-16 a run started straight after another reported 9
    failures in the failure-handling section, and the same code then
    passed with 0 in 34 s. Run `--check` on its own; a fix would step the
    controller directly instead of waiting on the timer, as the checks
    added since 2026-10-24 do. `check.py` is a development self-check
    only: the integration does not run or ship it.

41. **The root `requirements.txt` on this branch lacks the PySide6 pin**
    that `development` has (`PySide6==6.11.2`).

## Notes

Not issues: things to know.

- **The "Show all numbers" drawer will be removed** in the final
  iteration. Going with it, each commented in the code: the drawer
  (`ui_parts/panels/NumbersDrawer.qml`) and its place in
  `ui_parts/views/ConsoleView.qml`, with the hero row's `visible`
  binding there; the snapshot keys only it reads (`accel_mps2`,
  `authority_target`, `max_power_kw`, `power_channels`, `power_vote`) and
  the backend's `_power_channels` and `_power_vote`;
  `ControllerCore.last_vote`; and the drawer step in `check.py`. M12's
  acceleration exception goes with it; the drawer's acceleration comes
  from the bench simulation and reads 0 under a harness.
- **The vote is shown failing only in `check.py`** (M21), which swaps
  power channels for faulty ones. The bench has no row for it: it would
  have to reach inside the controller (M0).
- **Yard departure announcements.** Leaving the yard has no announcement
  of its own: the yard is not a station and sends no beacon, so there is
  no boarding and no "departing". The departure is the first tick the
  train is commissioned and receives commanded speed and authority above
  0. With 3 blocks or fewer, "The train *id* is arriving soon" is sent at
  once, also when the count arrived before the gains were set; with
  more, it is sent when the authority comes down to 3 (M7).

## Resolved

One line each; the details are in `CHANGELOG.md`.

- **11.** Block lengths unknown: authority is used as given (M16, R13).
- **14.** How a failure clears once integrated: decided, the controller
  detects resolution (M3); building it waits on #23.
- **16.** The gains hand-over signed a driver in unasked: fixed, it hands
  over only on the train just commissioned (M9, `bf277b1`).
- **17.** No block-change dummy: none needed; the bench's Block change
  button stands in for the Track Model (R13).
- **18.** Automatic lights: built (M8, R20).
- **20.** flake8 clean (`7a1f581`). The committed `ui/__pycache__` files
  are left alone by decision.
- **22.** Harness-spawned trains never armed: decided, the engineer
  commissions every train (M9).
- **24.** The Train Model's speed limit: no longer sent (2026-10-28, on
  this owner's word, relayed by Kevin); commanded speed is the limit (M1).
- **25.** The passenger brake release: closed by Kevin 2026-10-28. No
  release signal; the Train Model holds a passenger pull until the
  controller's emergency brake command goes from true to false, which the
  driver's release does (M2).
- **26 (most of it).** The bench's simulation moved out of the
  controller (M0, R15); the choice of simulator is still open (#26).
- **29.** The dial's 70 km/h scale against M1: display only, accepted
  (M14, R29).
- **30.** Rules not yet in the code: dropped, as `REQUIREMENTS.md` §1's
  Status column is the record.
- **31 (first bullet).** The bench clock runs from the first
  commissioning (M11, R37).
- **42.** Two ticks between a command and its report under the harness:
  the fleet takes `echo_ticks` (ECHO_TICKS, 2, under the harness; 1 on
  the bench), and the brake-failure rule (M4) and the passenger-pull
  test (M2) use the report due for each command.
- **44.** Integrated, a brake failure never resolved: the controller
  now concludes it resolved when a service brake commanded with the
  e-brake off reads applied in its report (§4), and the bench clears
  only its own simulation's brake failure.
- Emergency echo re-latching the brake: fixed (M2, R16).
- `old_main.py`: removed in `c98393e`.
- Rolling resistance: decided, the controller models none (M19); the
  bench simulation's goes with #26.
- Signal aspect had no truth entry: truth has `signals/signal-aspect-ahead`
  (#27).
- "Arriving soon" on a rise to 3 blocks: accepted (M7, R29).
