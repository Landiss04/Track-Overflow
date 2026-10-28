# Prompt: draw the Train Model software architecture in draw.io

You are drawing the software architecture of one module, the **Train Model**: the
physics simulation of the trains in a five-module railway course project. Draw **the
Train Model only**. The rest of the system appears only as grey stubs at the module's
edge, with nothing drawn inside them. You have no access to the code. Every fact you
need is in this prompt. Don't invent components, connections or names that aren't
listed here. If something seems missing, say so in your report rather than filling the
gap.

## 1. Deliverable

- **One file:** `train-model-architecture.drawio`, uncompressed draw.io XML
  (`<mxfile>`), so it can be diffed and edited by hand. It holds one page, named
  `Architecture`.
- **Optional:** if the draw.io desktop CLI is already installed (`drawio` or
  `draw.io`), export the page to PNG beside the file and use it to check your work
  (section 7). Don't download or install anything to get it.
- **Report back:** the files you wrote, whether they exported, and any place you
  departed from this prompt.

## 2. Notation

Use UML component notation with native draw.io shapes only, no images.

- **Module boundary:** one large rounded container with an accent-coloured outline,
  labelled `«module» Train Model`. Everything in section 4 goes inside it.
- **Component** (a Python module or class): a rectangle with the UML component icon
  (`shape=component` or `shape=module`), labelled with the class name in bold and the
  Python module path below it in monospace, e.g. **TrainModelFleet** /
  `train_model.fleet`.
- **QML view:** a folded-corner rectangle (`shape=note`) labelled with the QML file
  names.
- **Layer bands:** light, unlabelled-fill horizontal bands inside the boundary, one per
  layer in section 4, each with its layer name at the left edge.
- **Provided and required interfaces:** UML lollipop (provided) and socket (required)
  on the module boundary, labelled as in section 5.
- **Stubs outside the boundary:** grey rectangles with a dashed outline, labelled as in
  section 5. Draw only their outline and label, never their insides.
- **Actors:** UML stick figures (`shape=umlActor`).
- **Connectors:**
  - Dashed line, open arrowhead, `«use»`: a code dependency (one component calls or
    imports another).
  - Dashed line, no arrowhead: a QML binding (a view reads a context property).
  - Solid line, open arrowhead: data flow across the boundary, or from an actor.
- **Legend:** a small box in the bottom-right corner explaining every line style and
  colour used.
- **Ids:** give every cell a readable id prefixed `arch-`, e.g. `arch-fleet`,
  `arch-state-model`.

## 3. Rules the diagram must respect

- **Physics only (D009).** The Train Model regulates nothing: no speed governor, no
  70 km/h cap, no door interlock. Don't draw a controller inside it.
- **Own types only (D005).** The module defines only its own boundary types. It never
  imports another module's types. Whoever drives it maps other modules' data onto these
  types outside the module.
- **Stepped from outside (D006).** The module has no clock. It is advanced by
  `step(dt, inputs)` with a fixed dt.
- **Failures** are injected only by Murphy in the Train Model window and are never
  reported outward.
- **`common/interfaces.py` is stale (D008).** Don't draw it.
- **Out of scope for this diagram:** the central harness's internals, the other four
  modules, the Raspberry Pi hardware, and the Train Model test UI's internals. None of
  them gets a component box.

## 4. Components inside the module

Stack the layers bottom to top in this order so `«use»` arrows point downward.

| Layer | Component | Module path | Role |
|---|---|---|---|
| Types | **Boundary types** | `train_model.interface` | Frozen dataclasses. List the names inside the box: `TrainConfig`, `ControllerCommands`, `TrackInputs`, `TrackInfo`, `TrackSignal`, `Beacon`, `TrainModelInputs`, `ControllerOutputs`, `TrackOutputs`, `TrainModelOutputs`, `TrainModelSnapshot`, `FailureState`, and the `TrainModel` protocol. |
| Physics | **TrainModel** | `train_model.model` | Pure Python, no Qt. `step(dt, inputs) -> outputs`, `snapshot()`, `set_failures()`, `pull_passenger_emergency_brake()`. Validates inputs, then updates motion, passengers, cabin temperature and block change. |
| Observable state | **TrainModelState** | `train_model.state` | Qt `QObject` wrapping one `TrainModel`. Republishes a flat snapshot for the window; exposes the window's slots (emergency brake, failures). Multiplicity `1 per train`. |
| Fleet | **TrainModelFleet** | `train_model.fleet` | Qt `QObject` holding every train's `TrainModelState` by train ID, and the train the window has selected. |
| Presentation | **Main.qml, MainView.qml** | `TrainModel/ui/` | The Train Model window. Binds to the context property `fleet` and its `fleet.current`. |
| Presentation | **run_window** | `train_model.app` | Starts the Qt application and QML engine, sets context properties, loads the QML. |
| Driver adapter | **TrainModelProcess** | `train_model.module_process` | The module's process entry. Owns the fleet; on each step adds trains newly named, removes trains no longer named, steps each train on its own inputs, and returns outputs plus any per-train rejections. |
| Driver adapter | **wire** | `train_model.wire` | `decode_inputs()` / `encode_outputs()`: the boundary types to and from JSON. |

Two shared helpers sit **outside the boundary** as grey stubs, used by the module:

- `utils.module_link` (**ModuleLink**) — the process's connection to its driver.
- `utils.beacon_codec` — encodes a beacon to its ≤ 128-character payload.

The repository's shared `ui/` theme is not drawn.

## 5. Boundary, stubs and connectors

**Provided interface** on the left edge of the boundary, a lollipop labelled
`step(dt, inputs) → outputs per train`. **Stub** outside it: `Driver — central harness
(integrated) or test UI (standalone)`, with a socket connected to the lollipop. Attach
a note to the stub: "Maps the Train Controller's and Track Model's data onto the Train
Model's types and back. Not part of this module."

**Actors** on the right, outside the boundary: `Passenger`, `Murphy`.

| From | To | Style | Label |
|---|---|---|---|
| Driver stub | ModuleLink | data flow, two arrows | `JSON: step {tick, sim time, trains: {id: {line, controller, track}}}` / `outputs per train, rejected: {id: reason}` |
| ModuleLink | TrainModelProcess | data flow | `step request` |
| TrainModelProcess | wire | «use» | |
| TrainModelProcess | TrainModelFleet | «use» | `add / remove / step per train` |
| TrainModelProcess | run_window | «use» | `opens window` |
| run_window | Main.qml | «use» | `loads` |
| Main.qml | TrainModelFleet | QML binding | `fleet, fleet.current` |
| TrainModelFleet | TrainModelState | «use» | `1..* by train ID` |
| TrainModelState | TrainModel | «use» | `step(dt, inputs)` |
| wire | Boundary types | «use» | |
| TrainModel | Boundary types | «use» | |
| TrainModel | `utils.beacon_codec` | «use» | |
| Passenger | Main.qml | data flow | `views status; announcements; pulls emergency brake` |
| Murphy | Main.qml | data flow | `injects / clears engine, signal pickup, brake failure` |

**Notes** (UML note shapes, attached with a dashed line):

- On TrainModelProcess: "A train whose inputs are invalid does not step this tick; the
  others do, and the reply names it. Its outputs stay as they were."
- On TrainModel: "Physics only (D009). No speed governing, no speed cap, no door
  interlock."
- On the module boundary: "No clock of its own: stepped from outside with a fixed dt
  (D006)."

## 6. Layout guidance

- Landscape page. Driver stub on the left, module boundary in the centre, actors on
  the right.
- Leave at least 40 px between sibling components and 20 px of padding inside every
  container.
- Orthogonal connectors (`edgeStyle=orthogonalEdgeStyle`), no diagonals, no crossings
  where a reroute avoids one. Connector labels get a white label background.
- One sans-serif font throughout: 12 pt for component names, 10 pt for module paths
  and labels.

## 7. Check your work before reporting

1. **Page.** Exactly one page, named `Architecture`.
2. **XML.** Well-formed. Every `id` is unique, and every `parent`, `source` and
   `target` points at an existing cell. Every connector has both a source and a target.
3. **Scope.** Nothing outside the module boundary except the driver stub, the two
   shared-helper stubs, the two actors, notes and the legend. No harness internals, no
   other modules, no test UI internals, no `common/interfaces.py`.
4. **Look at the page.** Export to PNG if the CLI is already installed; otherwise
   render the cells with a small script. Check that no label overlaps another label or
   a shape, nothing spills out of its container, and every connector label is readable.
5. **Fix the layout, not the content.** If a label doesn't fit, move or resize shapes.
   Don't shorten a label without reporting it.

**Report back:** the files you wrote, whether they exported, and any place you departed
from this prompt.
