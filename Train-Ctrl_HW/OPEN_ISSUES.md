# Train-Ctrl_HW — open issues for review

Found but not fixed. Each entry says what goes wrong and where, so it can be
picked up later. Grouped by who has to act; numbers are kept, so references
from `REQUIREMENTS.md` and the code stay valid. Last reviewed 2026-10-31,
against `claude/quirky-fermi-sickg4` `57e8847` and truth `84c7d44`
(`REQUIREMENTS.md` M0–M21; M5 is merged into M3).

## Controller: to decide or build

26. **Which simulator the bench uses.** Deferred to later by decision
    (2026-10-31). The bench's simulation is separate (`bench_sim.py`
    `SimTrain`, R15), still the toy plant. The choice:
    - (a) keep the toy plant (Euler, rolling resistance only under a brake
      failure, no grade; its service brake state does not go false under
      the e-brake as the Train Model's does); or
    - (b) reuse the Train Model's pure-Python `train_model.model.TrainModel`
      from `development` inside `SimTrain`: one physics, with real rolling
      resistance and grade. D005 says modules do not import each other's
      boundary types, so this needs a team decision.

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

43. **Where the bench differs from the harness it stands in for.**
    Decided 2026-10-31: the bench is a stand-in for the central harness
    while the bench drives the system, and does nothing while the harness
    is connected. Where it still differs from the harness:
    - **Timing.** It answers each command on the next tick; the harness
      answers two ticks later. The controller allows for it (`echo_ticks`,
      #42), but a rule tested only on the bench is tested at one tick.
    - **Train Model physics.** The toy plant has no grade, no load and no
      rolling resistance outside an injected brake failure, so a dead
      engine coasts at constant speed. Deferred with #26.
    - **Track Model, Track Controller and CTC Office.** There is no track:
      authority changes only with the Block change button, commanded
      speed and the signal ahead only when edited, and the beacon only
      with the `at_station` row.
    - **Failures.** None left: clearing an injected failure clears it in
      the bench's simulation only, and the controller resolves each one
      itself (M0, M3, #23).

45. **The bench should spawn the console for the line** (planned, the
    weekend of 2026-11-07; Jonathan, 2026-10-30; plan confirmed
    2026-10-31). So the bench emulates the integrated system. The bench
    opens only when asked for: `main.py --test`, or the central harness
    asking for the test bench. It opens on its own, and **Spawn** on the Red
    Line opens (or reuses) the HW Train Controller console, on the Green
    Line the SW one, each with its own backend and titled as under the
    harness (M13, `run(variant=…)`). To design: one bench editing trains
    held by two backends. Also then: setting the bench's time is slow
    with the scroll wheels (M15); the time is to be typed instead (#31,
    #32, #36).

## Outside the style guide and shared UI

37. **Service-brake amber and the 72 px hero readouts** (`brake_service` and
    `size_hero` in `train_ctrl/console_theme.py` `PENDING_TOKENS`) are
    outside the style guide; the proposal that carried both was removed
    from the inbox (`69b5cc9`).

38. **Other sizes kept to Ivan's design but outside the style guide**
    (restored 2026-10-07 at Jonathan's request): the speed and temperature
    dial figures are computed from the dial radius (`Math.max(24, r * 0.45)`,
    sized for "43.5", and `Math.max(30, r * 0.66)`) rather than a token, and the door and
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
    only, run by the AI to test the module offline: it is never run with
    the central harness, and the integration does not ship it.

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
  from the bench simulation and reads 0 under a harness. The drawer is
  for debugging outside integration, so what it shows under the central
  harness is not tracked as a bug (`BUGS.md`).
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
  detects resolution (M3); built for the brake (#44), signal pickup (R40)
  and the engine (R44).
- **23.** Brake and engine resolution with the emergency brake on:
  decided 2026-10-31. Brake: kept as built (#44), resolved once the
  driver releases the e-brake and asks for the service brake. Engine:
  the driver tries the train (option a, R44): with only an engine
  failure latched, the release opens a try, and the speed rising under
  power resolves it; outside a try the service brake holds the train
  against a rollback (`REQUIREMENTS.md` §4, measured there).
- **28.** Engine-failure false positives on grades: the steady-fall rule
  Kevin accepted (R91) is ported from `460579b` (R43,
  `tests/test_engine_detection.py`); measured in `REQUIREMENTS.md` §4.
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
- **34.** E-brake left off in Automatic with a failure latched: kept,
  by decision (2026-10-31). The driver may also release the e-brake at a
  stand during a failure in Automatic, not only in Manual (M2, M3, R42).
- **42.** Two ticks between a command and its report under the harness:
  the fleet takes `echo_ticks` (ECHO_TICKS, 2, under the harness; 1 on
  the bench), and the brake-failure rule (M4) and the passenger-pull
  test (M2) use the report due for each command.
- **35.** The module diverged on `claude/quirky-fermi-sickg4`: Kevin
  pulled this branch's `e0e142d` there (`74159e9`), and `f05053b` brought
  his changes back, so the two matched at `51eca3b`. That branch's harness
  sends M18's two brake states. `module_process.py` runs only there, where
  `utils/module_link` is.
- **44.** Integrated, a brake failure never resolved: the controller
  now concludes it resolved when a service brake commanded with the
  e-brake off reads applied in its report (§4), and the bench clears
  only its own simulation's brake failure.
- Emergency echo re-latching the brake: fixed (M2, R16).
- `old_main.py`: removed in `c98393e`.
- Rolling resistance: decided, the controller models none (M19); the
  bench simulation's goes with #26.
- **27.** Signal light ahead (M20): truth has `signals/signal-aspect-ahead`,
  and this controller takes its `SUPER_GREEN` spelling (Kevin, 2026-10-28),
  so the harness passes the light through unchanged.
- "Arriving soon" on a rise to 3 blocks: accepted (M7, R29).

## Notes for other modules

Questions and possible errors whose answer lies with another module or
the team's shared documents.

**Truth and the SRS:**

19. **Module rules are not recorded outside this folder.** Rules M0–M21
    in `REQUIREMENTS.md` are in neither truth's Train Controller contract
    (still a placeholder) nor the SRS. Update the documentation later.

**Train Model:**

- A train with more than about 125 passengers cannot climb Green's 5 %
  grade at all (`REQUIREMENTS.md` §7, `BUGS.md` B3).

**CTC Office:**

- TC-1, a Green train over its limit after dispatch: should the commanded
  speed drop before a slower block? (`BUGS.md`, Notes for other modules).
