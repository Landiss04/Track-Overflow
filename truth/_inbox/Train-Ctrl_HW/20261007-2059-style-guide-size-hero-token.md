**Target:** truth/ui/style-guide.md
**Action:** replace
**Proposed by:** Claude on Train-Ctrl_HW
**Provenance:** asserted by Jonathan Tsang 2026-10-07 (Ivan Zheng's Train Controller design); also carries the `--brake-service` tokens from `20261006-2108-style-guide-brake-service-token.md`, so either promoted last loses nothing

---

# style-guide

**Status:** current
**Owner:** Kevin
**Provenance:** Team 3, `documents/UI_Style_Guide.md` v1.2 on development (`c0580825e7b9f72f289cecdc1618b6136557d44b`); D002 and v1.3 on `truth` (`e315da5`; the branch was formerly named truth-setup); relocation asserted by Kevin 2026-09-27; PySide6 per `documents/srs-filled.md` §3.1.3 REQ-INTF-014 (development, `c058082`); QML asserted by Kevin 2026-09-29; QML-specific values and the Idle badge background follow `UI-icon-standardization` (`3dc7a4d`) at Kevin's direction 2026-09-29; dark theme and preview removal and the Train Controller service-brake exemption asserted by Kevin 2026-09-29; line-identity tokens (§4.6) asserted by Landis 2026-10-02, values proposed for review on `ctc-interfacing`; Train Controller service-brake tokens asserted by Jonathan Tsang 2026-10-06; hero readout size asserted by Jonathan Tsang 2026-10-07 (Ivan Zheng's Train Controller design)
**Aliases:** UI Style Guide, UI_Style_Guide.md
**Last updated:** 2026-10-07

UI style guide for the ECE1140 Train Management System (University of Pittsburgh).

## Table of Contents

<!-- TOC -->
* [1. Purpose and Scope](#1-purpose-and-scope)
* [2. Design Principles](#2-design-principles)
* [3. Typography](#3-typography)
* [4. Color](#4-color)
  * [4.1 Surfaces and Borders](#41-surfaces-and-borders)
  * [4.2 Text](#42-text)
  * [4.3 Accent](#43-accent)
  * [4.4 Semantic Colors](#44-semantic-colors)
  * [4.5 Contrast Verification](#45-contrast-verification)
  * [4.6 Line Identity](#46-line-identity)
* [5. Spacing, Radius, and Elevation](#5-spacing-radius-and-elevation)
* [6. Components](#6-components)
  * [6.1 Buttons](#61-buttons)
  * [6.2 Inputs and Selects](#62-inputs-and-selects)
  * [6.3 Status Badges](#63-status-badges)
  * [6.4 Track Block Occupancy](#64-track-block-occupancy)
  * [6.5 Telemetry Readouts](#65-telemetry-readouts)
  * [6.6 Data Tables](#66-data-tables)
  * [6.7 Module Window Header](#67-module-window-header)
* [7. Safety-Critical Controls](#7-safety-critical-controls)
* [8. Accessibility Rules](#8-accessibility-rules)
* [9. Implementation Notes](#9-implementation-notes)
<!-- TOC -->

## 1. Purpose and Scope

This document defines the normative visual design tokens and component rules for all graphical
user interfaces in the ECE1140 Train Management System — CTC Office, Track Controller, Track
Model, Train Model, and Train Controller.

All modules **shall** use the tokens in Sections 3 through 6. Module authors **shall not**
introduce ad-hoc colors, font sizes, or spacing values. If a required token is missing, it is
added here first, then used.

**Daylight Ops** (light) is the only theme. There is no dark theme.

## 2. Design Principles

1. **Legibility over decoration.** This is an operator console, not a marketing page.
2. **Color is never the only signal.** Every colored state also carries a text label, an icon,
   or a pattern.
3. **Numbers do not jitter.** All telemetry uses a monospace face so digits stay column-aligned
   as values update at simulation tick rate.
4. **Destructive actions are hard to hit by accident.** Emergency and brake controls are
   oversized, isolated, and confirmed, except the Train Controller brakes, which act
   immediately (Section 7).
5. **One accent color.** The accent identifies the primary action in a view. If everything is
   accented, nothing is.

## 3. Typography

| Token | Role | Family | Fallback order |
|-------|------|--------|----------------|
| `--ui-family` | UI | Helvetica | Helvetica Neue, Helvetica, Arial, Nimbus Sans, DejaVu Sans |
| `--mono-family` | Mono | Monaco | Monaco, Menlo, Consolas, Andale Mono, DejaVu Sans Mono |

QML's `font.family` takes a single name, so each list is resolved once at startup to the
first family installed on the machine. If none is installed, the last one is used.

Helvetica does not ship with Windows. On the lab machines and any standard Windows PC, the UI
face resolves to **Arial**, which is metric-compatible with Helvetica — line breaks and layout
are identical, letterforms differ slightly. On macOS it resolves to Helvetica Neue, and on Linux
to Nimbus Sans or DejaVu Sans. This is intentional and requires no font bundling or licensing.

The mono list is chosen to sit well beside a neo-grotesque UI face: Monaco/Menlo on macOS,
Consolas on Windows, DejaVu Sans Mono on Linux. No font is bundled with the application.

| Role | Size token | Size | Weight | Line height | Use |
|------|------------|------|--------|-------------|-----|
| Display | `--size-display` | 36 px | 700 | 1.15 | Application title, splash |
| H1 | `--size-h1` | 28 px | 700 | 1.2 | Module window title |
| H2 | `--size-h2` | 22 px | 700 | 1.25 | Section heading within a module |
| H3 | `--size-h3` | 18 px | 700 | 1.3 | Sub-section, panel title |
| Body | `--size-body` | 15 px | 400 | 1.55 | Default text |
| Small | `--size-small` | 13 px | 400 | 1.5 | Helper and secondary detail |
| Label | `--size-label` | 12 px | 700 | 1.4 | Field labels, uppercase, letter-spacing `--label-letter-spacing` (0.84 px) |
| Telemetry | `--size-telemetry` | 28 px | 700 | 1.4 | Telemetry readout values (Section 6.5) |
| Hero | `--size-hero` | 72 px | 700 | 1.15 | The Train Controller cab's primary readouts, read from a driving position (Section 6.5) |
| Mono | inherits | inherits | 400 or 700 | 1.4 | Telemetry values, IDs, timestamps |

**Rules**

- Only two weights exist: **400 (Regular, `--weight-regular`)** and **700 (Bold,
  `--weight-bold`)**. Helvetica and Arial ship no intermediate weights, so any request for
  500/600/650 is synthesized by the renderer and produces inconsistent results across
  platforms. Do not specify them.
- Size and weight carry the hierarchy. Where 700 is not enough separation, use size or
  `--text-muted`, not a fake semibold.
- Every ID (train, block, station), every timestamp, and all numeric telemetry **shall**
  render in the mono face.
- Field labels **shall** use the Label token in uppercase.
- Letter-spacing is given in pixels, because QML's `font.letterSpacing` is in pixels.
- Never use font size alone to convey state; pair with color and text.

## 4. Color

### 4.1 Surfaces and Borders

| Token | Hex | Use |
|-------|-----|-----|
| `--bg-app` | `#F4F6F8` | Window / desktop background |
| `--bg-surface` | `#FFFFFF` | Panels, cards, module chrome |
| `--bg-raised` | `#FFFFFF` | Hover rows, headers, secondary buttons |
| `--bg-sunken` | `#E8ECF0` | Input fields, readout wells |
| `--border` | `#D5DCE3` | Default 1 px separators |
| `--border-strong` | `#8795A3` | Input outlines, table header rule |

`--bg-raised` intentionally equals `--bg-surface`; there is no headroom above white, so
separation is carried by `--border` instead of by a lighter fill.

### 4.2 Text

| Token | Hex | Use |
|-------|-----|-----|
| `--text-primary` | `#16202A` | Body copy, headings, values |
| `--text-secondary` | `#4B5C6B` | Supporting text, descriptions |
| `--text-muted` | `#5F6B79` | Labels, units, disabled text |
| `--text-inverse` | `#FFFFFF` | Text on `--danger` / `--success` fills |

### 4.3 Accent

| Token | Hex | Use |
|-------|-----|-----|
| `--accent` | `#1D6FD0` | Primary button fill, active tab, selection |
| `--accent-hover` | `#1A5FB4` | Primary button hover |
| `--accent-active` | `#164E96` | Primary button pressed |
| `--accent-subtle` | `#E4EFFB` | Callout background, selected row tint |
| `--on-accent` | `#FFFFFF` | Text/icons on an accent fill |

### 4.4 Semantic Colors

| Token | Hex | Meaning |
|-------|-----|---------|
| `--success` | `#15803D` | Normal operation, on time, fault cleared |
| `--success-hover` | `#126832` | Success button hover |
| `--success-bg` | `#EDF7F0` | Success badge / banner background |
| `--warning` | `#B45309` | Caution, speed restriction, block closed, delayed |
| `--warning-bg` | `#FDF2E0` | Warning badge / banner background |
| `--danger` | `#C0272D` | Fault, broken rail, emergency brake, hard stop |
| `--danger-hover` | `#A81F25` | Danger button hover |
| `--danger-active` | `#8C1A1F` | Danger button pressed |
| `--danger-bg` | `#FBE8E9` | Danger badge / banner background |
| `--brake-service` | `#F2C037` | Train Controller service brake fill (Section 7) |
| `--brake-service-active` | `#D9A520` | Train Controller service brake, engaged or pressed |
| `--info` | `#4338CA` | Block occupied, informational state |
| `--info-bg` | `#EAE8FB` | Info badge / banner background |
| `--focus-ring` | `#1D6FD0` | Keyboard focus outline (2 px, 2 px offset) |

On a light background the semantic colors are deep and saturated rather than bright.
`--danger` is a true signal red dark enough to carry against white, and `--success` is a deep
green, so that "normal" and "fault" are separated by hue, not just by brightness.

### 4.5 Contrast Verification

Measured against `--bg-surface` (`#FFFFFF`) unless noted. WCAG 2.1 AA requires 4.5:1 for normal
text and 3:1 for large text and UI boundaries.

| Foreground | Background | Ratio | Result |
|------------|-----------|-------|--------|
| `--text-primary` | `--bg-surface` | 16.5:1 | Pass AAA |
| `--text-secondary` | `--bg-surface` | 6.9:1 | Pass AAA |
| `--text-muted` | `--bg-surface` | 5.4:1 | Pass AA |
| `--text-muted` | `--bg-sunken` | 4.6:1 | Pass AA |
| `--accent` | `--bg-surface` | 5.0:1 | Pass AA |
| `--success` | `--bg-surface` | 5.0:1 | Pass AA |
| `--warning` | `--bg-surface` | 5.0:1 | Pass AA |
| `--danger` | `--bg-surface` | 5.9:1 | Pass AA |
| `--info` | `--bg-surface` | 8.0:1 | Pass AAA |
| `--on-accent` | `--accent` | 5.0:1 | Pass AA |
| `--text-inverse` | `--danger` | 5.9:1 | Pass AA |
| `--text-inverse` | `--success` | 5.0:1 | Pass AA |
| `--danger` | `--danger-bg` | 5.0:1 | Pass AA |
| `--success` | `--success-bg` | 4.6:1 | Pass AA |
| `--warning` | `--warning-bg` | 4.5:1 | Pass AA |
| `--border-strong` | `--bg-surface` | 3.1:1 | Pass AA (non-text) |

Buttons filled with `--danger` or `--success` use **white** text (`--text-inverse`), because
the semantic colors are dark enough to support it.

### 4.6 Line Identity

Identifies which line a piece of track belongs to on a track map. Not a state color.

| Token | Hex | Use |
|-------|-----|-----|
| `--line-red` | `#B03A3A` | Red Line track, section letters |
| `--line-green` | `#2F7D4F` | Green Line track, section letters |

Contrast, as non-text graphics (3:1 required):

| Foreground | Background | Ratio | Result |
|------------|-----------|-------|--------|
| `--line-red` | `--bg-surface` | 6.0:1 | Pass |
| `--line-red` | `--bg-sunken` | 5.0:1 | Pass |
| `--line-green` | `--bg-surface` | 5.0:1 | Pass |
| `--line-green` | `--bg-sunken` | 4.2:1 | Pass |

**Rules**

- Line color is never the only signal: the two lines also differ by stroke pattern and
  carry a "Red line" / "Green line" label or legend entry.
- Block state (Section 6.4) overrides line color on the affected block. An occupied,
  closed, failed or maintenance block takes its state fill and label.
- `--line-red` and `--line-green` are close in hue to `--danger` and `--success`. They are
  used only for track strokes and section letters, never for buttons, badges or banners,
  so a red line does not read as a fault.

## 5. Spacing, Radius, and Elevation

Spacing uses a 4 px base scale.

| Token | Value | Typical use |
|-------|-------|-------------|
| `--space-1` | 4 px | Icon-to-label gap |
| `--space-2` | 8 px | Tight inline gaps |
| `--space-3` | 12 px | Control gaps, table cell padding |
| `--space-4` | 16 px | Button horizontal padding, panel gaps |
| `--space-5` | 24 px | Panel padding, page gutters |
| `--space-6` | 32 px | Major section separation |
| `--space-7` | 48 px | Top-of-section separation |

| Token | Value | Use |
|-------|-------|-----|
| `--radius-sm` | 3 px | Track block segments, chips |
| `--radius-md` | 6 px | Buttons, inputs |
| `--radius-lg` | 10 px | Panels, cards, dialogs |
| `--radius-pill` | 999 px | Status badges, toggle groups |

QML has no CSS box-shadow, so elevation is carried by borders:

| Surface | Border |
|---------|--------|
| Resting panels, cards, sticky headers | 1 px `--border` |
| Dialogs, popovers, menus | 1 px `--border-strong` |

Control heights: `--control-h-sm` 28 px, `--control-h-md` 36 px (default),
`--control-h-lg` 44 px.

## 6. Components

### 6.1 Buttons

| Variant | Fill | Text | Border | Use |
|---------|------|------|--------|-----|
| Primary | `--accent` | `--on-accent` | none | The one main action per view (Dispatch, Send) |
| Secondary | `--bg-raised` | `--text-primary` | `--border-strong` | Supporting actions |
| Ghost | transparent | `--text-secondary` | none | Cancel, dismiss, low-emphasis |
| Danger | `--danger` | `--text-inverse` | none | Emergency brake, force-close block |
| Success | `--success` | `--text-inverse` | none | Clear fault, acknowledge |

| Size | Height | Horizontal padding | Font size |
|------|--------|--------------------|-----------|
| Small | 28 px | 12 px | 13 px |
| Medium (default) | 36 px | 16 px | 15 px |
| Large | 44 px | 24 px | 18 px |

**Rules**

- Border radius `--radius-md`; font weight 700; label in sentence case except emergency controls.
- Hover, active, and disabled states are mandatory. Disabled = 40–45 % opacity, no pointer.
- Focus: 2 px `--focus-ring` outline with 2 px offset. Never remove the focus indicator.
- At most one Primary button is visible in a panel at a time.

### 6.2 Inputs and Selects

- Height `--control-h-md`, background `--bg-sunken`, border 1 px `--border-strong`,
  radius `--radius-md`, horizontal padding `--space-3`.
- Focus: border becomes `--accent` plus a 2 px `--focus-ring` outline.
- Every input has a visible Label-token label above it. Placeholder text is not a label.
- Numeric entry fields use the mono face.
- Invalid entry: border `--danger` plus an error message in `--danger` below the field.

### 6.3 Status Badges

Pill shape, 12 px uppercase bold text, 1 px border in the semantic color, 7 px dot, background
the matching `-bg` token.

| Badge | Color token | Example labels |
|-------|-------------|----------------|
| OK | `--success` | Operational, On Time, Clear |
| Warning | `--warning` | Speed Restricted, Delayed, Closed |
| Fault | `--danger` | Broken Rail, E-Brake, Power Failure |
| Info | `--info` | Occupied, En Route |
| Idle | `--text-muted` | Offline, Yard, Unassigned |

Idle has no `-bg` token of its own, so its background is `--bg-sunken`.

The text label is required. A bare colored dot is not an acceptable status indicator.

### 6.4 Track Block Occupancy

| State | Fill | Label |
|-------|------|-------|
| Free | `--bg-raised` + 1 px `--border-strong` | `FREE` |
| Occupied | `--info` | `OCCUPIED` |
| Closed | `--warning` | `CLOSED` |
| Failure | `--danger` | `FAILURE` |
| Maintenance | `--text-muted` | `MAINT` |

Blocks are 34 px tall minimum with a mono, 12 px, bold, centered label using `--text-inverse`
on filled states. Adjacent blocks are separated by at least 2 px.

### 6.5 Telemetry Readouts

- Container: `--bg-sunken`, 1 px `--border`, `--radius-md`, padding `--space-3 --space-4`.
- Label above in Label token, `--text-muted`.
- Value in mono, `--size-telemetry` (28 px), weight 700, `--text-primary`. The Train
  Controller cab's primary readouts use `--size-hero` (72 px) instead, so they read from a
  driving position; contrast is unchanged (`--text-primary` on `--bg-sunken`).
- Unit immediately after the value, mono, 13 px, `--text-muted`.
- Units **shall** match the UI display units table in [conventions/units.md](../conventions/units.md) exactly
  (`mph`, `ft`, `s`, `kW`, `F`, ...). That table is imperial, with power in kilowatts as
  the one exception; the metric values behind it are converted at the display layer and
  never rendered.
- Values update in place; the container does not resize as digits change.

### 6.6 Data Tables

- Header: Label token, `--text-muted`, 1 px `--border-strong` bottom rule.
- Rows: 13 px text, `--space-3` cell padding, 1 px `--border` bottom rule.
- Row hover: `--bg-raised`. Selected row: `--accent-subtle`.
- Numeric and ID columns are mono; numeric columns are right-aligned.
- Empty values render as an em dash (`—`), never a blank cell or `None`.

Because `--bg-raised` equals `--bg-surface`, row hover **shall** additionally
apply a 1 px `--border-strong` outline or an `--accent-subtle` tint so the hovered row stays
distinguishable.

### 6.7 Module Window Header

Every module window carries a header bar on `--bg-raised` with a bottom `--border` containing:

1. Module name and instance (e.g. `Train Controller — TRN-014`) at H3 weight.
2. Current mode badge (Automatic / Manual).
3. Simulation clock in mono, 13 px, `--text-muted`.

## 7. Safety-Critical Controls

Applies to Emergency Brake, Service Brake, Force Close Block, and any command that overrides
an automatic safety function.

- Minimum size 44 px tall by 200 px wide (`--control-h-lg`).
- Fill `--danger`, label uppercase with `--safety-letter-spacing` (0.75 px). The Train
  Controller service brake is the exception: it fills `--brake-service`, with
  `--text-primary` text (11.2:1), so it never reads as the emergency brake. It is a
  routine stop that only the Train Controller applies.
- Separated from routine controls by at least `--space-5`, and never adjacent to a Primary button.
- Require an explicit confirmation step, except the Train Controller emergency brake and
  service brake, which are immediate by design and are the only unconfirmed destructive
  controls in the system.
- Active emergency state is mirrored by a persistent Fault badge in the module header.

## 8. Accessibility Rules

- All text meets WCAG 2.1 AA contrast (see Section 4.5).
- Color is never the sole carrier of meaning — pair with label, icon, or fill pattern.
- The palette is checked against deuteranopia and protanopia: success and danger sit in
  distinct hue families and at similar weight against white (5.0:1 and 5.9:1), so neither
  state can be mistaken for the other on hue loss alone — the required text label carries it.
- All interactive controls are keyboard reachable in a logical tab order with a visible
  `--focus-ring`.
- Minimum interactive target is 28 px by 28 px; default is 36 px.
- Minimum body text size is 13 px. Nothing below 12 px ships.

## 9. Implementation Notes

- Tokens are defined once, in a single Python module (for example `ui/theme.py`), as named
  constants. No literal hex values appear in QML or view code.
- The UI is PySide6 with QML. The host exposes the tokens to QML as a `theme` context
  property before loading any QML, and every view reads its values from `theme`. QSS is
  not used.

## Supersedes

- `documents/UI_Style_Guide.md` v1.3 and its preview move here at Kevin's
  request; visual rules and D002's display-unit decision are retained.
- The v1.2 development guide's metric UI examples are superseded by D002;
  see [conventions/units.md](../conventions/units.md) for unresolved source conflicts.
- The optional dark theme (Section 10) is removed because dark mode will not be used, and the
  HTML review preview (Section 11) is removed at Kevin's request (2026-09-29).
- CSS-only values are replaced for QML: fallback stacks resolve at startup, letter-spacing is
  in pixels, and `--shadow-1` / `--shadow-2` give way to borders, following
  `UI-icon-standardization` (`3dc7a4d`).
- The Train Controller service brake no longer requires confirmation (Kevin 2026-09-29).
- Train Controller service brake fill: previously `--danger`, like every safety control;
  now `--brake-service` amber, to tell it apart from the emergency brake
  (Jonathan Tsang 2026-10-06).
- Hero readout size: previously unstated, with the cab's primary readouts held to
  `--size-telemetry`; now `--size-hero` 72 px for those readouts (Jonathan Tsang
  2026-10-07, Ivan Zheng's design).

## Conflict

**Resolution owner:** Kevin.

**Module window title — H1 vs. H3. Open.**

| Value | Provenance |
|-------|------------|
| H1, 28 px | Section 3 typography table: H1 is the "Module window title" |
| H3, 18 px | Section 6.7: module name and instance "at H3 weight"; `ui/ModuleHeader.qml` on `UI-icon-standardization` (`3dc7a4d`) renders the name at H3 |

**Mode badge in every module header. Open.**

| Value | Provenance |
|-------|------------|
| Every module window header carries an Automatic / Manual mode badge | Section 6.7 |
| Automatic / Manual modes exist only for CTC dispatch and for train speed regulation; no requirement gives the Track Model or Train Model a mode | `documents/srs-filled.md` REQ-FUNC-006–008 (CTC dispatch), REQ-FUNC-025–026 (train speed regulation), development `c058082` |

The SRS also has a maintenance mode (REQ-FUNC-012, REQ-FUNC-057), which Section 6.7 does not
mention. The badge's color is not specified; `ui/ModuleHeader.qml` renders it as an Info
badge and hides it when a module has no mode.
