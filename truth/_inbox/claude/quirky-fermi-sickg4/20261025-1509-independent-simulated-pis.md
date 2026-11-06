**Target:** truth/decisions/independent-simulated-pis.md
**Action:** create
**Proposed by:** Codex on claude/quirky-fermi-sickg4
**Provenance:** Kevin Schillinger, 2026-10-25: "Add a config that allows the simulated pis to be toggled on and off independently so that I can test"; configuration format and precedence proposed by Codex to implement that request

---

# independent-simulated-pis

**Status:** current
**Owner:** Kevin Schillinger
**Provenance:** independent simulator selection requested by Kevin Schillinger 2026-10-25; startup format and precedence proposed by Codex 2026-10-25
**Aliases:** simulated Pi toggles, per-module Pi simulation, Pi test configuration
**Last updated:** 2026-10-25

## Decision

- Development and testing may explicitly select a simulated Pi independently
  for Track Controller HW and Train Controller HW.
- A simulator being off leaves its module on the physical USB Pi path under
  D021/D027. The module still participates in the shared readiness/clock barrier.
- With no explicit simulation selection, both modules use physical Pis.
  Missing hardware never causes an automatic simulator fallback.
- `--pi-config PATH` reads a JSON object whose optional
  `track-controller-hw` and `train-controller-hw` members are Booleans.
  `true` selects the existing process simulator; `false` or an omitted member
  selects the physical Pi. No configuration file is loaded implicitly.
- Explicit `--test-pi process|pty` selects that simulator transport for both
  hardware modules, overriding the file. Individual
  `--track-controller-pi physical|process|pty` and
  `--train-controller-pi physical|process|pty` options then override the selection
  for their respective modules.
- Invalid or unreadable configuration is rejected before modules start.
  Simulator selection is fixed for a run; changing it requires restarting.

## Scope

These are explicit test/development selections. Production variant/line
assignments, USB identity, module interfaces and physical-Pi requirements remain
those of D021/D027. Simulation does not establish physical USB acceptance.
