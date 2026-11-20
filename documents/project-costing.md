# Train System Project Costing

Manufacturing cost estimate for the deployed system (Green + Red lines), built from
the actual architecture in this repo rather than assumed figures. All inputs are now
filled in.

## Architecture facts used

| Item | Value | Source |
|---|---|---|
| Deployed lines | Green + Red only (Blue is a Train Model test fixture, not operational — D023) | `documents/sdd/track_model.md` |
| Wayside (Track) Controllers | 6 (Green, SW) + 5 (Red, HW) = **11** | D021, `documents/sdd/track_model.md` |
| Track circuits (1/block) | 150 (Green) + 76 (Red) = **226** | `Track_layout/green_line.json`, `Track_layout/red_line.json` |
| Railway crossings | 2 (Green) + 2 (Red) = **4** | `railway_crossing: true` entries |
| Total deployed track length | 14,552.6 m + 5,548.2 m = 20,100.8 m ≈ **65,948 ft** | summed `length_m` fields |
| Redundancy | None — diverse SW/HW implementation, not TMR/voting | `documents/sdd/system_concepts.md` |
| Train Controllers (fleet size) | **20** (10 trains/line × 2 lines) | team decision |

## Materials

| Item | Qty | Unit cost | Total |
|---|---|---|---|
| Track Controller | 11 | $5,000 | $55,000 |
| Train Controller | 20 | $5,000 | $100,000 |
| Windows PC (CTC workstation) | 1 | $3,000 | $3,000 |
| Track Circuits | 226 | $2,000 | $452,000 |
| Railway Crossing Gate & Lights | 4 | $10,000 | $40,000 |
| Cable | 65,948 ft | $10/ft | $659,480 |
| **Materials subtotal** | | | **$1,309,480** |

## Labor

| Item | Basis | Rate | Total |
|---|---|---|---|
| Installation (Track Ctrl + Train Ctrl + Track Circuits, 20 hr/device) | 257 devices × 20 hr = 5,140 hr | $75/hr | $385,500 |
| Cable Installation | 65,948 ft | $18/ft | $1,187,064 |
| Software Engineering | 980 hr — professor's course estimate: 10 hr/week/person × 7 people × 14 weeks | $125/hr | $122,500 |
| **Labor subtotal** | | | **$1,695,064** |

## Overhead

Software Engineering, Installation, and Cable Installation are marked **"fully
burdened"** rates — overhead is already included in those. That leaves only
Materials unburdened, so 200% overhead is applied to Materials only.

- Overhead = 200% × Materials = 200% × $1,309,480 = **$2,618,960**

## Total COGS

$$\text{COGS} = 3 \times \text{Materials} + \text{Labor}$$
$$\text{COGS} = 3 \times \$1,309,480 + \$1,695,064 = \$5,623,504$$

## Price at 30% COGS target

$$\text{Price} = \text{COGS} / 0.30 = \$5,623,504 / 0.30 = \$18,745,013$$

Offer price: **≈ $18,745,013**.

## Summary

Total COGS of **$5,623,504** breaks down as ~23% materials (parts), ~30% labor, and
~47% overhead (200% applied to materials only, since the labor rates are already
fully burdened). At a 30% COGS target, the offer price is **≈ $18,745,013**. Cable
and its installation are the single largest cost driver — together ~33% of COGS —
because the deployed Green+Red layout is ~65,948 ft of track.

### Risks

- **Fleet size (N = 20) is a team decision, not a specified requirement.** The SRS
  only guarantees "2+ trains per line" will run; if the customer's actual fleet
  differs, Materials and Installation Labor both scale by $6,500 per train.
- **Software Engineering hours (980) are the professor's planning estimate**
  (10 hr/week/person × 7 people × 14 weeks), not tracked actuals. Real engineering
  hours for a from-scratch build of this scope are routinely under-estimated by
  course-level planning formulas, and the labor rate here assumes the team's
  course effort maps 1:1 onto a real engineering team's billable hours.
- **Cable footage is modeled as equal to track length**, not actual conduit/trench
  routing distance (which is typically longer than the rail itself due to
  right-of-way obstacles, road crossings, and routing around structures). This is
  the largest single cost category, so it is also the most exposed to being wrong.
- **Overhead base is an assumption.** The source slide doesn't state what the 200%
  applies to; this estimate assumes it applies only to Materials because the three
  labor rates are explicitly marked "fully burdened." If overhead is meant to apply
  to total direct cost instead, COGS would be far higher (~$16.9M).
- **No contingency/spares included** — the parts counts are exactly what is needed
  to run the system, with no spare Track/Train Controllers for field replacement.
- **Switches (13 total) have no priced material line** — the cost table provided
  has no switch-hardware category, so switch cost is implicitly bundled into Track
  Circuits/Track Controller cost, which may understate real switch-machine cost.
