# Rubric section -> SRS requirement mapping

Point values below are transcribed directly from the saved screenshots in
`documents/rubrics/detailed-png/` (verified 2026-09-26), not from memory.
This just tracks which rubric line items the SRS already covers, so you don't
have to re-derive it by eye next time.

## Module functional rubric -> documents/srs-filled.md REQ-FUNC IDs

| Rubric section | Points | REQ-FUNC range | Notes |
|---|---|---|---|
| 1.2-1.4 Simulation control | 1+1+1 = 3 | 001-003 | real-time, >=10x fast-forward, pause |
| 2.0-2.8 CTC Office | 2+2+1+1+1+3+2+2+1 = 15 | 004-014 | dispatch, speed/authority, manual/auto mode, maintenance, occupancy, throughput |
| 3.0-3.9 Track Model | 1+2+1+2+2+2+1+1+2+1 = 15 | 015-024 | load model, properties, ticket sales, passengers, occupancy, signals, temp, heaters, switch/light, failure modes |
| 4.0-4.10 Train Controller | 2+2+1+1+1+2+2+1+1+1+1 = 15 | 025-038 | speed regulation (manual/auto split), temp, brakes, Kp/Ki, lights/doors, announce/stop, safety-critical, failure detection |
| 5.0-5.95 Train Model | 2+1+2+2+1+1+1+1+1+2 = 14 | 039-048 | physics calc, properties, crew/passengers, track-circuit signal, commanded temp/lights/doors, beacons, e-brake, failure modes |
| 6.0-6.9 Track Controller (Wayside) | 2+2+1+2+1+2+2+1+1+1 = 15 | 049-059 | speed/authority receive, PLC load/language/execution, occupancy, crossings, maintenance mode, safety-critical, failure detection |
| 7.0-7.9 Moving Block Overlay | 1+1+1+1+2+2+2+1+1 = 12 (not graded) | N/A | explicitly out of scope this term (srs-filled.md 3.2.7) |
| 8.0 Add for lack of full team | 0 | N/A | grading adjustment, not a requirement |
| 8.1 Observations - what did you learn | 10 | N/A | reflection, not a system requirement |
| 9.0 Each sub-system has a UI | 5 | REQ-INTF-001 | |
| 9.1 Runs on Windows | 1 | Product Constraints (2.4) | Windows 11 |
| 9.2 Advertisements | 1 | not implemented | dropped per Braden's decision |
| 9.3 OMET | 0 | N/A | end-of-term student evaluation survey, not a requirement |
| 9.4 Cost Analysis | 15 | REQ-DSN-007 | scope deferred to future customer discussion |
| 10.0-10.3 Hours/bugs/lessons/retro | 2+3+2+2 = 9 | REQ-COMP-008/009/010/011 | |

## Whole-semester rubric -> SRS section

| Rubric item | SRS section |
|---|---|
| SRS-GROUP (0, 1.x, 2.x, 3.x, 4) | documents/srs-filled.md, all of it |
| PROJECT SCHEDULE-GROUP | srs-filled.md 2.6 + 3.5.8 |
| CODING STANDARDS-GROUP | documents/PYTHON_STYLE_GUIDE.md |
| DEFECT TRACKING POLICY-GROUP | JIRA defect form (see meeting log 006 on `meeting-logs` branch); not yet its own doc |
| PERSONAS-GROUP | srs-filled.md 2.3 User Characteristics |
| System Architecture / UX Architecture / UI Design / Risk Assessment (Individual) | not tracked in srs-filled.md; likely separate per-person deliverables (check OneDrive per meeting 006) |

Update this file whenever new rubric line items get mapped to requirements, or when a rubric section moves to a different requirement range after a renumbering pass.
