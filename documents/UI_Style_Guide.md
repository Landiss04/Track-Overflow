# UI Style Guide

## For ECE1140 Train Management System

Version 1.2
Prepared by Team 3
University of Pittsburgh
2026-09-11

## Table of Contents

<!-- TOC -->
* [1. Purpose and Scope](#1-purpose-and-scope)
* [2. Design Principles](#2-design-principles)
* [3. Typography](#3-typography)
* [4. Color — Light Theme (Normative)](#4-color--light-theme-normative)
  * [4.1 Surfaces and Borders](#41-surfaces-and-borders)
  * [4.2 Text](#42-text)
  * [4.3 Accent](#43-accent)
  * [4.4 Semantic Colors](#44-semantic-colors)
  * [4.5 Contrast Verification](#45-contrast-verification)
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
* [10. Optional Dark Theme (Not Committed)](#10-optional-dark-theme-not-committed)
  * [10.1 Dark Token Overrides](#101-dark-token-overrides)
  * [10.2 Theme Switch Requirements](#102-theme-switch-requirements)
* [11. Live Preview](#11-live-preview)
<!-- TOC -->

## Revision History

| Name   | Date       | Reason For Changes                                              | Version |
|--------|------------|-----------------------------------------------------------------|---------|
| Team 3 | 2026-09-11 | Initial style guide; dark theme locked as default               | 1.0     |
| Team 3 | 2026-09-11 | UI face changed to Helvetica/Arial; weight scale cut to 400/700 | 1.1     |
| Team 3 | 2026-09-11 | Light theme promoted to default; dark theme moved to optional   | 1.2     |

---

## 1. Purpose and Scope

This document defines the normative visual design tokens and component rules for all graphical
user interfaces in the ECE1140 Train Management System — CTC Office, Track Controller, Track
Model, Train Model, and Train Controller.

All modules **shall** use the tokens in Sections 3 through 6. Module authors **shall not**
introduce ad-hoc colors, font sizes, or spacing values. If a required token is missing, it is
added here first, then used.

**Daylight Ops** (light) is the committed default theme. Section 10 documents an optional dark
theme; it is a stretch goal and is not required for any sprint deliverable.

## 2. Design Principles

1. **Legibility over decoration.** This is an operator console, not a marketing page.
2. **Color is never the only signal.** Every colored state also carries a text label, an icon,
   or a pattern.
3. **Numbers do not jitter.** All telemetry uses a monospace face so digits stay column-aligned
   as values update at simulation tick rate.
4. **Destructive actions are hard to hit by accident.** Emergency and brake controls are
   oversized, isolated, and confirmed.
5. **One accent color.** The accent identifies the primary action in a view. If everything is
   accented, nothing is.

## 3. Typography

| Role | Family | Fallback stack |
|------|--------|----------------|
| UI   | Helvetica | `"Helvetica Neue", "Helvetica", "Arial", sans-serif` |
| Mono | Monaco | `"Monaco", "Menlo", "Consolas", "Andale Mono", monospace` |

Helvetica does not ship with Windows. On the lab machines and any standard Windows PC, the UI
face resolves to **Arial**, which is metric-compatible with Helvetica — line breaks and layout
are identical, letterforms differ slightly. On macOS it resolves to Helvetica Neue. This is
intentional and requires no font bundling or licensing.

The mono stack is chosen to sit well beside a neo-grotesque UI face: Monaco/Menlo on macOS,
Consolas on Windows. No font is bundled with the application.

| Token | Size | Weight | Line height | Use |
|-------|------|--------|-------------|-----|
| Display | 36 px | 700 | 1.15 | Application title, splash |
| H1 | 28 px | 700 | 1.2 | Module window title |
| H2 | 22 px | 700 | 1.25 | Section heading within a module |
| H3 | 18 px | 700 | 1.3 | Sub-section, panel title |
| Body | 15 px | 400 | 1.55 | Default text |
| Small | 13 px | 400 | 1.5 | Helper and secondary detail |
| Label | 12 px | 700 | 1.4 | Field labels, uppercase, letter-spacing `0.07em` |
| Mono | inherits | 400 or 700 | 1.4 | Telemetry values, IDs, timestamps |

**Rules**

- Only two weights exist: **400 (Regular)** and **700 (Bold)**. Helvetica and Arial ship no
  intermediate weights, so any request for 500/600/650 is synthesized by the renderer and
  produces inconsistent results across platforms. Do not specify them.
- Size and weight carry the hierarchy. Where 700 is not enough separation, use size or
  `--text-muted`, not a fake semibold.
- Train IDs, block IDs, timestamps, and all numeric telemetry **shall** render in the mono face.
- Field labels **shall** use the Label token in uppercase.
- Never use font size alone to convey state; pair with color and text.

## 4. Color — Light Theme (Normative)

### 4.1 Surfaces and Borders

| Token | Hex | Use |
|-------|-----|-----|
| `--bg-app` | `#F4F6F8` | Window / desktop background |
| `--bg-surface` | `#FFFFFF` | Panels, cards, module chrome |
| `--bg-raised` | `#FFFFFF` | Hover rows, headers, secondary buttons |
| `--bg-sunken` | `#E8ECF0` | Input fields, readout wells |
| `--border` | `#D5DCE3` | Default 1 px separators |
| `--border-strong` | `#8795A3` | Input outlines, table header rule |

`--bg-raised` intentionally equals `--bg-surface` in this theme; there is no headroom above
white, so separation is carried by `--border` and `--shadow-1` instead of by a lighter fill.

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

Buttons filled with `--danger` or `--success` use **white** text (`--text-inverse`) in this
theme, because the semantic colors are dark enough to support it. This inverts in the dark
theme — see Section 10.

## 5. Spacing, Radius, and Elevation

Spacing uses a 4 px base scale. These values are shared by both themes.

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

| Token | Value | Use |
|-------|-------|-----|
| `--shadow-1` | `0 1px 2px rgba(22,32,42,.08)` | Resting panels, sticky headers |
| `--shadow-2` | `0 4px 14px rgba(22,32,42,.12)` | Dialogs, popovers, menus |

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
- Value in mono, 28 px, weight 700, `--text-primary`.
- Unit immediately after the value, mono, 13 px, `--text-muted`.
- Units **shall** match `Project_Information/Units.md` exactly (`m/s`, `m`, `s`, `kW`, `C`, ...).
- Values update in place; the container does not resize as digits change.

### 6.6 Data Tables

- Header: Label token, `--text-muted`, 1 px `--border-strong` bottom rule.
- Rows: 13 px text, `--space-3` cell padding, 1 px `--border` bottom rule.
- Row hover: `--bg-raised`. Selected row: `--accent-subtle`.
- Numeric and ID columns are mono; numeric columns are right-aligned.
- Empty values render as an em dash (`—`), never a blank cell or `None`.

Because `--bg-raised` equals `--bg-surface` in the light theme, row hover **shall** additionally
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
- Fill `--danger`, label uppercase with `0.05em` letter-spacing.
- Separated from routine controls by at least `--space-5`, and never adjacent to a Primary button.
- Require an explicit confirmation step, except the Train Controller emergency brake, which is
  immediate by design and is the only unconfirmed destructive control in the system.
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

- Tokens are defined once in a single module (for example `ui/theme.py`) as named constants and
  imported by every view. No literal hex values appear in widget code.
- If PyQt is used, tokens are injected into a single application-wide QSS stylesheet built from
  those constants, so a theme change is a one-line swap of the token dictionary.
- Every token in Sections 4 and 10 uses the same key name, which is what makes the optional
  dark theme a drop-in replacement.
- The preview file in Section 11 is the visual source of truth for review; any token change
  **shall** be applied to both this document and the preview in the same commit.

## 10. Optional Dark Theme (Not Committed)

This section is **informative**. A dark theme and a light/dark switch are a stretch goal. No
sprint deliverable depends on it. It is specified here so that, if implemented, it requires no
design work — only a token swap.

Typography, spacing, radius, control heights, and all component rules in Sections 3, 5, 6, 7,
and 8 are unchanged. Only the color tokens below differ.

### 10.1 Dark Token Overrides

| Token | Light (normative) | Dark (optional) |
|-------|-------------------|-----------------|
| `--bg-app` | `#F4F6F8` | `#0F1419` |
| `--bg-surface` | `#FFFFFF` | `#161C24` |
| `--bg-raised` | `#FFFFFF` | `#1E2630` |
| `--bg-sunken` | `#E8ECF0` | `#0A0E12` |
| `--border` | `#D5DCE3` | `#2C3742` |
| `--border-strong` | `#8795A3` | `#3E4B59` |
| `--text-primary` | `#16202A` | `#E6EDF3` |
| `--text-secondary` | `#4B5C6B` | `#9FB0C0` |
| `--text-muted` | `#5F6B79` | `#6B7E90` |
| `--text-inverse` | `#FFFFFF` | `#0F1419` |
| `--accent` | `#1D6FD0` | `#38BDF8` |
| `--accent-hover` | `#1A5FB4` | `#7DD3FC` |
| `--accent-active` | `#164E96` | `#0EA5E9` |
| `--accent-subtle` | `#E4EFFB` | `#12303F` |
| `--on-accent` | `#FFFFFF` | `#041018` |
| `--success` | `#15803D` | `#2ECC71` |
| `--success-hover` | `#126832` | `#46D983` |
| `--success-bg` | `#EDF7F0` | `#0E2A1A` |
| `--warning` | `#B45309` | `#FBBF24` |
| `--warning-bg` | `#FDF2E0` | `#322505` |
| `--danger` | `#C0272D` | `#EF4444` |
| `--danger-hover` | `#A81F25` | `#F75C5C` |
| `--danger-active` | `#8C1A1F` | `#D93A3A` |
| `--danger-bg` | `#FBE8E9` | `#2E0F11` |
| `--info` | `#4338CA` | `#818CF8` |
| `--info-bg` | `#EAE8FB` | `#1B1D3A` |
| `--focus-ring` | `#1D6FD0` | `#FBBF24` |
| `--shadow-1` | `0 1px 2px rgba(22,32,42,.08)` | `0 1px 2px rgba(0,0,0,.5)` |
| `--shadow-2` | `0 4px 14px rgba(22,32,42,.12)` | `0 4px 12px rgba(0,0,0,.55)` |

Dark-theme contrast, measured against `--bg-app` (`#0F1419`):

| Foreground | Ratio | Result |
|------------|-------|--------|
| `--text-primary` | 15.9:1 | Pass AAA |
| `--text-secondary` | 8.5:1 | Pass AAA |
| `--text-muted` | 4.5:1 | Pass AA |
| `--accent` | 8.8:1 | Pass AAA |
| `--success` | 8.9:1 | Pass AAA |
| `--warning` | 11.3:1 | Pass AAA |
| `--danger` | 5.0:1 | Pass AA |
| `--info` | 6.3:1 | Pass AA |

Two behavioral differences apply if this theme is implemented:

1. **`--text-inverse` inverts.** Filled danger and success buttons use **dark** text in the dark
   theme, because white on `#EF4444` measures 3.8:1 and fails AA for normal text.
2. **`--bg-raised` separates from `--bg-surface`.** The extra row-hover rule in Section 6.6 is
   unnecessary in the dark theme, since `--bg-raised` is already a visibly distinct fill.

### 10.2 Theme Switch Requirements

If the switch is implemented:

1. The control lives in the application menu or settings panel, not in individual modules.
2. The selection persists across restarts.
3. Switching applies to every open module window without requiring a restart.
4. Light is the default on first run.
5. No screenshot, printed figure, or demo artifact is theme-dependent for its meaning.

## 11. Live Preview

An interactive rendering of both themes — typography scale, full palette, every button variant
and size, inputs, badges, block legend, telemetry readouts, table, spacing scale, and a sample
module window — is at:

`documents/ui-style-guide-preview.html`

Open it in a browser and use the switcher in the top bar to compare Light (default) against
Dark (optional).
