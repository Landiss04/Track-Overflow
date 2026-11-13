# Route requests at the Red passing sidings — implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development or superpowers:executing-plans
> (Braden chooses) to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** The HW Track Controller reads the CTC Office's `route_requests`,
feeds them to PLC programs as `REQSW_s` / `REQREV_s`, and the Red-2 program
follows them at switches 27, 32, 38 and 43.

**Architecture:** A new `CtcInputs.route_requests` field travels the same
path as `switch_commands` (validation, wire, wayside input image, test UI).
Only the Red-2 program reads it. The vital block is untouched.

**Tech Stack:** Python 3.14 venv `C:\Dev\trains\.venv`, PySide6 6.11,
`unittest`; QML test UI.

**Spec:** [2026-11-03-route-requests-design.md](2026-11-03-route-requests-design.md)

**Workspace:** clone `C:\Dev\trains-route`, branch
`feature/TrackCtrl-HW-route-requests`. Run tests from `TrackCtrlHw`:
`C:\Dev\trains\.venv\Scripts\python.exe -m unittest discover -s tests -t .`

## Global Constraints

- Code lines ≤ 79 characters; docstrings and comments ≤ 72.
- No OS-specific path separators.
- `vital.py` is not modified.
- Wire entry shape for a request: `{"line", "switch_id", "position"}`,
  `position` ∈ {`normal`, `reverse`} — identical to `switch_commands`.
- A missing `ctc.route_requests` on the wire decodes as no requests.
- PLC names: `REQSW_s` (a request exists for switch `s`), `REQREV_s`
  (it is reverse; 0 with no request). `s` is the switch's listed block.
- Every interface change updates test UI, link and wire in the same
  commit.
- `CAUTION_s` does not read requests.

## Review Focus

1. A request into a closed leg must not move the switch (Task 3 test).
2. A train on the points block (27, 33, 38, 44) must hold the switch
   where it reports, request or not (Task 3 test).
3. A maintenance command must win over a request (Task 3 test).
4. A request for a switch on another wayside, or on Green, must be
   ignored without error (Task 2 test).
5. An old sender without `route_requests` must still decode (Task 1
   test).

---

### Task 1: `route_requests` on the CTC inputs and the wire

**Files:**
- Modify: `TrackCtrlHw/track_ctrl_hw/interface.py` (`CtcInputs`)
- Modify: `TrackCtrlHw/track_ctrl_hw/controller.py` (input validation)
- Modify: `TrackCtrlHw/track_ctrl_hw/wire.py` (`inputs_to_wire`,
  `inputs_from_wire`)
- Modify: `TrackCtrlHw/tests/support.py` (`inputs(..., route_requests=)`)
- Test: `TrackCtrlHw/tests/test_wire_and_views.py`,
  `TrackCtrlHw/tests/test_controller.py`

**Interfaces:**
- Produces: `CtcInputs.route_requests: Mapping[BlockRef,
  SwitchPosition]`, default `{}`; `support.inputs(...,
  route_requests: dict[str, str] | None = None)` keyed by block number.

- [ ] **Step 1: Write the failing tests**
  - `Wire.test_round_trips_through_json`: add
    `route_requests={"12": "reverse"}` to `sent`; assert
    `wire["ctc"]["route_requests"] == [{"line": "Green", "switch_id":
    "12", "position": "reverse"}]` and the round trip is equal.
  - `Wire.test_route_requests_are_optional_on_the_wire`: delete
    `wire["ctc"]["route_requests"]`; `inputs_from_wire(wire).ctc
    .route_requests == {}`.
  - `Wire.test_rejects_malformed_messages`: add path
    `("ctc", "route_requests", 0, "position")` → `"sideways"` (needs
    `route_requests={"12": "reverse"}` in `good`).
  - `test_controller.py`: `step` with `route_requests={"12":
    "sideways"}` raises `InvalidInputError`.
- [ ] **Step 2: Run, expect FAIL** (`TypeError: unexpected keyword
  'route_requests'`).
- [ ] **Step 3: Implement.** Field after `switch_commands` with a comment
  (request, not a command; the program decides). Validate with
  `_choices(ctc.route_requests, SWITCH_POSITIONS, "route_requests",
  BlockRef)`. Wire: `_ref_entries(..., "switch_id")` out;
  `_from_ref_entries(ctc.get("route_requests", []), ...)` in.
- [ ] **Step 4: Run, expect PASS** (whole suite).
- [ ] **Step 5: Commit** `Track Controller HW: CTC route requests on the
  inputs and the wire`.

### Task 2: `REQSW_s` / `REQREV_s` in the wayside input image

**Files:**
- Modify: `TrackCtrlHw/track_ctrl_hw/wayside.py` (`input_names`,
  `_run_program`, module docstring table)
- Modify: `TrackCtrlHw/README.md` (PLC names, precedence)
- Test: `TrackCtrlHw/tests/test_controller.py`,
  `TrackCtrlHw/tests/test_vital.py`

**Interfaces:**
- Consumes: `CtcInputs.route_requests` (Task 1).
- Produces: PLC inputs `REQSW_s`, `REQREV_s` for every switch of every
  wayside.

- [ ] **Step 1: Write the failing tests** (Green wayside 1, switch 12):
  - `input_names(territory(1))` contains `REQSW_12` and `REQREV_12`.
  - Program `VAR_IN REQSW_12 REQREV_12` / `VAR_OUT SW_12` /
    `SW_12 := REQSW_12 AND REQREV_12`: with
    `route_requests={"12": "reverse"}` → `switch_commands[k["12"]] ==
    "reverse"`; with `{"12": "normal"}` and with none → `"normal"`.
  - A request keyed `Red:27` sent to a Green-only controller: no
    error, outputs unchanged.
  - `test_vital.py`, with `run_permissive(red(2), ...)` (its program
    drives every `SW_s` reverse): `route_requests={"27": "reverse"},
    switch_commands={"27": "normal"}` → `"normal"`; `occupied=["27"],
    reported={"27": "normal"}, route_requests={"27": "reverse"}` →
    `"normal"`. The vital block still forces commands and locks.
- [ ] **Step 2: Run, expect FAIL** (undeclared input / name missing).
- [ ] **Step 3: Implement.** In `input_names`, add both names per
  switch. In `_run_program`, per switch:
  `route = ctc.route_requests.get(switch.key.ref)`;
  `image[f"REQSW_{number}"] = route is not None`;
  `image[f"REQREV_{number}"] = route == "reverse"`. Docstring table:
  two rows after `CTCREV_n`. README: names and precedence (lock >
  maintenance command > request > the program's own rule).
- [ ] **Step 4: Run, expect PASS.** `Generated.test_compiles_cleanly_for_every_database`
  must still pass (vital reads ⊆ inputs).
- [ ] **Step 5: Commit** `Track Controller HW: route requests reach the
  PLC as REQSW and REQREV`.

### Task 3: Red-2 follows route requests at 27, 32, 38, 43

**Files:**
- Modify: `TrackCtrlHw/data/plc/red_wayside_2_integration_test.plc`
- Modify: `TrackCtrlHw/CHANGELOG.md`
- Test: `TrackCtrlHw/tests/test_red_integration.py`

**Interfaces:**
- Consumes: `REQSW_s` / `REQREV_s` (Task 2).

Legs (switch, points, normal, reverse): 27/27/28/76, 32/33/32/72,
38/38/39/71, 43/44/43/67 (`RedSwitchRouting.ROUTES`).

- [ ] **Step 1: Write the failing tests** — new test methods on
  `RedSwitchRouting`, using its `scan` (it already passes
  `route_requests=` through to `support.inputs`). For each of the four:
  1. `route_requests={s: "reverse"}` → `"reverse"`; none → `"normal"`.
  2. `{s: "normal"}` with `occupied=[reverse]` (train waiting in the
     siding) → `"normal"` (the request beats today's rule).
  3. `{s: "reverse"}` with `closed=[reverse]` → `"normal"`.
  4. `{s: "reverse"}` with `occupied=[points]`,
     `reported={s: "normal"}` → `"normal"` (lock).
  5. `{s: "reverse"}` with `switch_commands={s: "normal"}` →
     `"normal"`.
  6. `{s: "reverse"}`, `reported={s: "reverse"}`: signal not red, and
     yellow (diverging route shows caution through `SWREV_s`).
- [ ] **Step 2: Run, expect FAIL** (1, 2 and 6).
- [ ] **Step 3: Implement.** Add `REQSW_s REQREV_s` for the four switches
  to `VAR_IN`. Per switch, before `WANT_s`:

```
REQ_R_s := REQSW_s AND REQREV_s AND NOT CLOSED_<reverse>
REQ_N_s := REQSW_s AND NOT REQREV_s AND NOT CLOSED_<normal>
AUTO_s := REQ_R_s OR (NOT REQ_N_s AND NOT REQ_R_s
          AND <today's AUTO_s right-hand side>)
```

  One comment line above the block. `WANT`, `LOCK`, `BAD`, `BLOCKED`,
  `CAUTION`, signals unchanged. The program must compile with no
  diagnostics.
- [ ] **Step 4: Run, expect PASS** (whole suite, including all existing
  `RedSwitchRouting` tests unchanged).
- [ ] **Step 5: Commit** `Red-2: follow CTC route requests into the
  passing sidings`.

### Task 4: Test UI drives route requests

**Files:**
- Modify: `TrackCtrlHw/track_ctrl_hw/harness.py`
- Modify: `TrackCtrlHw/test_ui/TestView.qml`
- Create: `TrackCtrlHw/tests/test_harness_inputs.py`

**Interfaces:**
- Produces: `BlockInputs.route_request: str = "NONE"` (options
  `SWITCH_COMMANDS`); `TestHarness.routeRequestsText` (QML property).

- [ ] **Step 1: Write the failing test.** A stub link (`QObject` with
  `connectedChanged`, `territoriesChanged`, `outputsChanged` signals,
  `territories = [territory(1)]`, `connected = True`). Select block
  `Green:12`; `setInput("ctc", "route_request", "REVERSE")`;
  `build_inputs(0.0).ctc.route_requests == {BlockRef("Green", "12"):
  "reverse"}`; `routeRequestsText == "Green:12=reverse"`. On a block
  without a switch the row has `applies == False`.
- [ ] **Step 2: Run, expect FAIL.**
- [ ] **Step 3: Implement.** Mirror `switch_command`: field, kind
  `enum`, options, CTC group, `applies` = has switch, `_route_requests`
  helper, `build_inputs`, `routeRequestsText`. QML: a
  `KeyValueRow { label: "route_requests" }` under `switch_commands`
  (move `rule: false` to it); helper text: a request is not a command,
  the program decides.
- [ ] **Step 4: Run, expect PASS**; capture the test UI with
  `ui/capture.py` for a visual check.
- [ ] **Step 5: Commit** `Track Controller HW test UI: route requests`.

### Task 5: Pi bench check

- [ ] **Step 1:** Build the bundle from this clone
  (`python -m common.hw_link.provision --module track-controller-hw`),
  copy to `track-pi`, `sudo ./install.sh`, restart the agent.
- [ ] **Step 2:** `bringup --module track-controller-hw`: HELLO accepted,
  hash matches.
- [ ] **Step 3:** Through `common.hw_link.relay` (scratch script in
  `%TEMP%`): load Red-2 + its program on the Pi, STEP with
  `route_requests={Red:27: reverse}` → `SW 27 reverse`; with 76 closed →
  normal; with a maintenance command normal → normal.
- [ ] **Step 4:** Record results; no commit (no repo change).

## Not on this branch

- Harness edge `ctc_edges.py` → `hw_wayside_edges.py` (Kevin).
- End-to-end CTC test (needs the harness edge and `PASSING_SIDINGS`).
