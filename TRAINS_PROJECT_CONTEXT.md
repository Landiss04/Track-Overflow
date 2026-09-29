# ECE 1140 Trains — Project Context

Multi-module train control system: I/O specs, UX wireframes, diagrams, and SCM documentation.

---

## Overview

### Scope and modules

- Multi-module train control system project for ECE 1140 (group course project)
- Five core modules: CTC (Central Traffic Control) Office, Track/Wayside Controller, Train Controller, Track Model, and Train Model
- Jonathan's assigned module is the **Train Controller** (software); groupmates own other modules (e.g. Track Controller)
- MBO (Moving Block Overlay) is explicitly **NOT** an included module — outputs or documentation referencing it should be scrubbed
- Work spans systems engineering documentation, interaction design, and UX wireframing

### Domain terminology in use

Authority (permitted travel distance), track circuit, cab pickup coil, PI control law, beacon/transponder, PLC ladder logic, vital vs. non-vital signaling, block occupancy, service vs. emergency braking

### Current state — active workstreams

- **Train Controller key inputs:** track signal struct (commanded speed, authority, beacon), current speed feedback, speed setpoint, and emergency brake
- **Train Controller key outputs:** power command, service brake, and emergency brake command to the Train Model
- **Secondary I/Os:** door commands, cabin/head lights, temperature setpoint, acceleration, and failure status
- UX wireframes are authored in HTML and imported to Figma via the html.to.design plugin
- Page 4 is the Train Controller cab interface for driver T-214 on the Green Line, iterated through multiple versions and targeting a low-technical-proficiency older driver persona
- Page 4b is a companion signal reference page listing all Train Controller inputs and outputs in tabular Layout B format
- Resolved wireframe issues: stray SVG geometry, overlapping speed bar labels, and authority-limit arrow trimming
- Two interaction design deliverables produced as SVG/PDF: a detailed dispatch flow diagram and a top-level module map, both conforming to the Jesse James Garrett IA Visual Vocabulary; final state is clean and minimal
- SCM Plan: IEEE Std 828-2005-conformant template generated in both .docx and Markdown, with all six required classes of information, subsections, tables, and a conformance checklist

### Open questions and next steps

- Whether lights, doors, and announcements are driver-initiated inputs or controller-driven outputs
- Station announcements appear in whiteboard notes but are missing from the spreadsheet; needs consistent representation across both sources
- Potential additional wireframe pages for modules beyond the Train Controller

---

## Design Principles

### UI and architecture

- Vital vs. non-vital signal distinction is architecturally meaningful and should be preserved in I/O categorization
- The Kp/Ki engineer tuning panel should be rendered visible but disabled (38% opacity), not hidden
- Driver-facing UI should use plain language over rail-systems jargon, with single-column control stacking for simplicity
- All physical train model controls remain on screen regardless of simplification passes

### Diagram style

- Minimalism: no color fills, no extra annotation labels, black text only
- Use spacing and bold headers for grouping rather than enclosing shapes
- Diagrams conform to the Jesse James Garrett IA Visual Vocabulary

---

## Ways of Working

### Working pattern

- Source materials (photos, spreadsheets, whiteboard notes, PDFs) are synthesized, structured, or rendered into deliverables
- Corrections tend to be specific and visual — precise removal of artifacts, layout fixes, or terminology cleanup rather than broad redesigns
- Iterative refinement: initial full version, then targeted corrections, then confirmation
- Deliverables should be self-contained where possible — e.g. embedded CSS for Figma-importable HTML files

### Tools

- Figma with the html.to.design plugin for wireframe import
- SVG/PDF export via cairosvg (Python); the reliable pattern uses the `url=` parameter with a plain filename string
- SVGs are generated via pure Python string construction, with coordinates computed analytically before the draw phase
- PDF inspection: `pdftoppm` for per-page JPEG rasterization, `PIL.Image` for cropping high-res renders
- Document generation: the `docx` Node.js library for .docx output

### Reference standards

- Jesse James Garrett IA Visual Vocabulary
- IEEE Std 828-2005 (software configuration management plans)
