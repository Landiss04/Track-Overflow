# User Help Strategy — Train Control System

This document is the strategy deliverable for the User Help assignment (see
`documents/slides/` "User Help" deck, slide 17). It defines **what mix of help we
provide, to whom, and in what form**, before the content itself is written.

The actual help content (microcopy, in-app help files, printed/PDF user manual) is
written to this strategy as a separate pass per module.

## 1. Why a mixture, not one type

The source material is explicit: "most likely answer today is a mixture," and
separately lists three *types* of help (help file / user manual / microcopy) that
are not mutually exclusive. Our system has very different personas doing very
different things with it (see `documents/srs-filled.md#23-user-characteristics`),
so no single help type covers all of them. We use all three types, and all three
delivery channels (packaged, embedded, online), split by persona below.

## 2. Personas and what help they need

| Persona | Source | Technical expertise | Primary help need | Help type(s) |
|---|---|---|---|---|
| CTC Dispatcher | [srs-filled.md §2.3](srs-filled.md#23-user-characteristics) | Moderate | How to dispatch/monitor trains without memorizing the whole CTC UI | Microcopy (labels, tooltips, confirmations) + short embedded help panel |
| Train Driver (manual mode) | same | Minimal | How to safely operate a train manually | Microcopy + one-page quick-reference (printable) |
| Programmer (PLC author) | same | Superb (writes Boolean PLC) | Wayside PLC language syntax, scan semantics, file format | Reference-style Help File (Markdown/HTML, linkable, versioned with the code) |
| Murphy (failure injection / tester) | same | Expert | What failure modes exist and how injection affects state | Help File (test UI docs) |
| Passenger | same | None | Not a real user of any help system — out of scope | N/A |
| Track Builder | same | Mechanical | Track layout JSON schema, how a block/switch/crossing is declared | Help File (schema reference) |
| Dr. Profeta (grading persona) | assignment slide 17 | N/A — grader | Judge whether the strategy and content are reasonable | This document + linked help content |

Passenger-facing UI (Train Model) has no separate human operating it in this
simulation, so it is excluded from the help plan; station/ticketing microcopy still
follows the writing rules in §4 wherever passenger-facing text exists.

## 3. Channel mix per help type

| Help type | Channel | Where it lives | Why |
|---|---|---|---|
| Microcopy | Embedded | Directly in each module's QML UI (labels, tooltips, inline validation, error dialogs) | Lowest friction — the user never leaves the task. Matches "guides them simply through to the next step." |
| Help File | Online + packaged | Markdown in-repo (`<module>/docs/` or `<module>/README.md`), rendered to HTML/PDF for the final deliverable | Our test/dev audience (Programmer, Murphy, Track Builder) already works in the repo; Markdown is versioned alongside the code it documents. |
| User Manual | Packaged (PDF) | One document per end-user-facing module (CTC, Train Driver quick-reference), built from `documents/` the same way `srs-filled.md` builds to PDF (`srs-pdf.css`) | Dispatcher/Driver personas are the closest analogue to "real" operators per slide 5 (install/configure/use/maintain structure). |

## 4. Writing rules (applied to all three types)

Taken directly from the "General Rules" slides and applied to this project:

- **Be concise.** Lead with the action, not the explanation. e.g. prefer
  *"Set authority to 0 before releasing the switch"* over a paragraph of rationale.
- **Short sentences, active voice.** Avoid passive/bureaucratic phrasing already
  flagged as a known smell in this repo's own writing (see
  `documents/PYTHON_STYLE_GUIDE.md` for the code-comment equivalent of this rule).
- **One tone per surface.** CTC/dispatcher-facing copy is plain and operational
  (safety-critical domain — no humor, no idioms). Internal developer help
  (Programmer/Murphy) can be more technical/dense since the audience expects it.
- **Plain English, no idioms.** This project has no internationalization
  requirement (`documents/srs-filled.md` — Windows 11, English-only), but plain
  language is still the right default for a safety-critical operator UI.
- **Icons/symbols where the UI already has a convention.** Use the shared
  `ui/` kit's existing status/severity treatment (see
  [`ui/README.md`](../ui/README.md)) instead of inventing new iconography for help text.
- **Error messages name the problem and the fix, never blame the user or leak
  internals.** e.g. not *"COM+ caught an access violation at 0x00213BC8"* — instead
  *"Switch 15 is already set by another command. Wait for it to clear, then retry."*

## 5. Content plan (per module)

| Module | Microcopy | Help File | User Manual |
|---|---|---|---|
| CTC Office | Dispatch controls, schedule entry, conflict warnings | `CTC-Office/ctc_ui/README.md` operator section (link existing: [CTC-Office/ctc_ui/README.md](../CTC-Office/ctc_ui/README.md)) | 1-page dispatcher quick-reference (new) |
| Track Controller (HW + SW) | Wayside status, PLC load/ready indicators, fault banners | PLC language reference (new, lives next to [`TrackCtrlSW/track_ctrl/`](../TrackCtrlSW/track_ctrl/)) | N/A (no direct human operator in steady state) |
| Train Controller | Manual-mode controls, emergency brake, fault indicators | [`TrainController/README.md`](../TrainController/README.md) driver section (extend existing) | 1-page driver quick-reference (new) |
| Track Model / Train Model | Test UI field labels, failure-injection controls | [`TrainModel/README.md`](../TrainModel/README.md), [`TrainModel/docs/`](../TrainModel/docs/) (Murphy/tester audience, already exists — extend) | N/A — test-only personas |

Each "new" item above is a follow-on content task against this strategy, scoped to
whichever module owner is doing that work (see
`documents/project-overview.md` ownership table in repo memory for current owners).

## 6. How we validate the help is good

Per slide 14: give the copy to a novice and watch what they don't understand,
using the same UX-testing approach already used for the rest of the UI (see
`documents/UI_Style_Guide.md` / `truth/ui/style-guide.md` review process). For this
project specifically:

- Dispatcher/Driver-facing microcopy and quick-references: tested on a team member
  who has not touched that module's code.
- Programmer/Track-Builder-facing Help Files: tested by having someone write a
  trivial PLC program or track block using only the Help File, no prior context.

## 7. Risks

- **Scope risk:** seven modules, limited time — the content plan above
  prioritizes the personas closest to the SRS's safety-critical "operator" role
  (Dispatcher, Driver) over purely internal/test audiences.
- **Drift risk:** Help Files living next to code can go stale if not updated in the
  same PR as the feature — no enforcement mechanism exists yet (candidate for a PR
  checklist item).
- **Single grader as "user":** Dr. Profeta is grading as a stand-in for a real
  operator; the content plan still targets the real personas above rather than
  writing only to the grading rubric, since help that would satisfy a real
  dispatcher is a strictly higher bar.
