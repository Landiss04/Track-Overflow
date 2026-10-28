# Prompt: create `class diagram supplemen` in draw.io

Create a **supplementary UML class diagram** for the Train Model software module.
You have no prior knowledge of the codebase and do not need access to its source.
The supplied class diagram image and the inventory below contain the information
you need. Deliver the diagram itself, not instructions for someone else to draw it.

The existing diagram deliberately hides smaller operations to stay readable. Your
diagram is a separate companion that documents those omitted operations. Preserve
the existing diagram exactly. Do not replace it, redraw it in full, or add the
omitted operations to its class boxes.

## Deliverable and reference

- Create a **new, separate file** named `class diagram supplemen.drawio`.
- Give it one page named exactly `class diagram supplemen`, and use that same
  wording as its visible title. Preserve this spelling.
- Use uncompressed draw.io XML: `<mxfile>` containing a `<diagram>` with an
  editable `<mxGraphModel>`.
- Use the supplied `04_class.png` as the visual reference. It is also available in
  the originating repository at
  `documents/uml/train-model-uml(2)(1)-png/04_class.png`.
- If an existing `.drawio` file is supplied, read it only to inspect styling and
  class identities. Do not overwrite it or add pages to it.
- If draw.io export is available, also provide `class diagram supplemen.png` and
  inspect that export. The editable `.drawio` file is required regardless.

## Background and scope

The Train Model simulates a train's physics and onboard state. The main diagram
already shows its boundary dataclasses, configuration, protocol, concrete model,
exceptions, Qt state wrapper, and window bootstrap function.

Two distinct types share the short name `TrainModel`:

- `train_model::interface::TrainModel` is a Python protocol.
- `train_model::model::TrainModel` is its concrete implementation.

`train_model::state::TrainModelState` is a Qt `QObject` wrapping one concrete model.
It republishes values for the window. It is not a subclass of the physics model.
An external driver advances the model through `step`; the state wrapper's idle
timer only detects whether steps are arriving and is not a simulation clock.

Limit this supplement to omitted members of these existing types and the small
free functions in `train_model::model`. Do not add fleet, process, wire, test UI,
harness, or other railway-module internals. Do not redesign the software.

This inventory describes the inspected implementation, not new requirements or
approved changes to its interface. Do not invent operations or reconcile historical
design differences by editing the original diagram.

## Required content

Use the following UML operation labels, retaining spelling, parameter order, types,
and return types. `+` means public and `-` means implementation-private by Python's
underscore convention. Omit the implicit `self`. Preserve `__init__` as a public
constructor rather than interpreting its underscores as private visibility.

### Package `train_model::model`

Draw one class box headed `train_model::model::TrainModel`, with a subtitle or
attached note: **“Supplementary members; see main class diagram for full state and
public interface.”** Include these omitted operations:

```text
+__init__(config: TrainConfig): None
-_add_elapsed(dt: float): None
-_refresh_discrete_outputs(): None
-_mass_kg(): float
-_traction_n(power_cmd_w: float, velocity_mps: float): float
-_brake_n(service: bool, emergency: bool): float
-_integrate(dt: float, inputs: TrainModelInputs, grade_rad: float): None
-_detect_block_change(polarity: bool): bool
-_update_passengers(door_left: bool, door_right: bool, boarded: int, *, stopped: bool): None
-_update_cabin_temp(dt: float, setpoint_c: float): None
-_build_outputs(inputs: TrainModelInputs | None, block_changed: bool): TrainModelOutputs
+clear_passenger_brake_for_test(): None
```

The `*` marks a keyword-only parameter, not a multiplication or multiplicity.
Keep it in the label or explain it in the legend.

Add compact notes beside the relevant operation groups:

- `_add_elapsed`: compensated accumulation of accepted elapsed time.
- `_refresh_discrete_outputs`: updates reported discrete state without advancing
  physics time.
- `_mass_kg`, `_traction_n`, `_brake_n`, `_integrate`: operating mass, traction,
  braking force, and motion integration.
- `_detect_block_change`, `_update_passengers`, `_update_cabin_temp`: block polarity
  change detection, passenger updates, and cabin-temperature updates.
- `_build_outputs`: assembles boundary outputs from current state and inputs.
- `clear_passenger_brake_for_test`: explicit testing override; not a passenger
  window release action.

Do not repeat `step`, `validate_inputs`, `snapshot`, `set_failures`, or
`pull_passenger_emergency_brake`: the main diagram already shows them.

Draw a second box labelled **`«module functions» train_model::model`**, containing:

```text
-_is_number(value: object): bool
-_is_finite(value: float): bool
-_sign(value: float): float
-_brakes_engaged(service_cmd: bool, emergency_cmd: bool, passenger_pulled: bool, brake_failed: bool): tuple[bool, bool]
```

These are module-level functions, **not methods of `TrainModel`**. The box is a
notation convenience, not an additional implemented class. Include a note to that
effect. `_brakes_engaged` returns `(emergency, service)`, in that order.

Connect the concrete model to this box with a dashed dependency labelled `«use»`.
Do not draw every internal function call as a relationship edge.

### Package `train_model::state`

Draw one class box headed `TrainModelState`, stereotyped `«QObject»`, and marked
**“Supplementary members.”** Include these omitted operations:

```text
+__init__(config: TrainConfig | None = None, parent: QObject | None = None, *, train_id: str = "", line: str = ""): None
-_initial_snapshot(): dict[str, Any]
-_mark_running(): None
-_set_running(running: bool): None
-_refresh(): None
+validate_inputs(dt: float, inputs: TrainModelInputs): None
+set_harness_time(sim_time_s: float): None
+set_clock_drift(drift_s: float, tick: int): bool
+command_values(): dict[str, Any]
+reset(): None
+clear_passenger_brake_for_test(): None
```

Add the omitted read-only Python properties in a separate property compartment:

```text
«property, readOnly» +elapsed_s: float
«property, readOnly» +train_id: str
«property, readOnly» +line: str
```

Add only these supporting private attributes, which give context to the omitted
helpers without copying the full original attribute compartment:

```text
-_train_id: str
-_line: str
-_next_station: tuple[str, str] | None
-_harness_time_s: float | None
-_idle: QTimer | None
```

Notes:

- `_initial_snapshot` builds the initial presentation dictionary; `_refresh`
  republishes the model's current state for the view.
- `_mark_running` and `_set_running` maintain the running indicator using an idle
  timeout. They do not advance simulation time.
- `set_harness_time` publishes supplied global time; `set_clock_drift` publishes
  a diagnostic and returns whether a discrepancy was detected.
- `command_values` exposes current producer inputs with consumed boarding events
  cleared; `reset` replaces the wrapped model and clears failures.

Do not repeat the signals, Qt properties, slots, `step`, or `outputs` already shown
in the main diagram. In particular, do not portray `releaseEmergencyBrake` as a
new functional release operation; the original diagram marks it as a no-op.

## Relationships and reference types

Show one composition from `TrainModelState` to the concrete
`train_model::model::TrainModel`, with the **filled diamond at the state wrapper**,
role `_model`, and multiplicity `1` at each end. This is the same ownership as in
the main diagram, repeated only to orient the supplement's two principal boxes.

Use names in signatures for `TrainConfig`, `TrainModelInputs`, and
`TrainModelOutputs`. If necessary for clarity, show small boxes marked
`«reference; defined in main class diagram»` for them. Do not copy their fields.
Python built-ins, `Any`, `QObject`, and `QTimer` need no expanded class definitions.
Never draw inheritance or composition merely because a type appears in a signature.

The interface protocol, `TrainConfig`'s derived properties, boundary dataclasses,
exceptions, and `app.run_window` already appear in the main diagram. Do not redraw
them as complete boxes here. Do not attach private implementation helpers to the
protocol.

## Layout and editability

- Match the reference's restrained UML style: white background, black outlines,
  package frames, bold class names, thin compartment dividers, and readable labels.
- Place the concrete model and module functions together inside the model package;
  place the state wrapper inside the state package alongside them.
- Group operations with subtle compartment labels such as “Physics”, “Discrete
  updates”, and “Presentation helpers” if helpful. These are categories, not classes.
- Use native editable draw.io UML shapes and text. Do not embed the reference image,
  screenshots, rasterized text, or SVG diagrams as the deliverable.
- Give relationship edges real `source` and `target` cell IDs so they follow boxes
  when moved. Use orthogonal routing and keep edges outside text compartments.
- Use a comfortably readable font, preferably at least 12 pt. Widen boxes and wrap
  long signatures rather than shrinking the text or removing parameters.
- Include a short legend for visibility, module-function notation, optional types,
  keyword-only parameters, and references to the main diagram.
- Put this note near the title: **“Companion to the main Train Model class diagram.
  Only supplementary members are shown; omitted compartments remain defined there.”**

## Verification and handoff

Check that every operation and property in the required inventory appears once,
under the correct owner. Check that no helper was invented as a class, no free
function became an instance method, and no new relationship implies unsupported
ownership. Ensure the XML parses and cell IDs are unique. If rendering is available,
inspect for clipped labels, overlapping boxes, and edges crossing operation text.

Return the new `.drawio` file, any exported preview, and a brief statement of what
you created and how you checked it. Report any unavailable rendering capability.
Leave every existing diagram and all source code unchanged.
