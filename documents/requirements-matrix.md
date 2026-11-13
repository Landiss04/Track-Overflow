# PAAC North Shore Extension — Module Requirements Matrix

Source: `Final Project vF.pdf` (course slide deck, 81 slides).
**Scope note:** The Moving Block Overlay (MBO) module — both the MBO Controller and the MBO Scheduler — is **out of scope** for this implementation. Every requirement that originally depended on the MBO is called out below in [Section 4](#4-scope-gaps-created-by-dropping-mbo), since dropping it removes some requirements outright and silently transfers others onto remaining modules.

Legend: 🔴 **VITAL** = safety-critical per the deck's definition ("in the railroad and transit industry 'vital' means 'safety critical'"). 🟡 = tension/conflict flagged in Section 3.

---

## 1. Configuration & Data Model (side by side)

This is pulled out as its own section, ahead of the general requirements, because **who configures what, and where that data lives, is the thing most likely to cause interface disagreements between modules** — several of the tensions in §4 trace directly back to two modules assuming they each own the same piece of configuration.

| | Track Model | Train Model | Track Controller (SW + HW) 🔴 | Train Controller (SW + HW) 🔴 | CTC Office |
|---|---|---|---|---|---|
| **Design-time / static config** | Track layout (topology, grade, elevation); allowable directions of travel; branching; per-segment speed limits; **configurable block size**; needs a **track layout input method** | Physical dimensions (length, height, width); mass; crew count; passenger capacity; car count (single or multi-car consist); accel/velocity limit parameters | **User-written PLC program**, required to be specifiable *separately* from the controller's own implementation | Control-law tuning constants: proportional gain `Kp`, integral gain `Ki`, sample period `T`, max engine power `Pmax` — deck states these "must be selected such that the system is stable" but gives no default values | Territory/section assignment per dispatcher; which track sections exist to be opened/closed for maintenance |
| **Runtime / dynamic data** | Live occupancy per block (from track circuits); live switch position; live signal aspect; crossing gate state | Live position, velocity, acceleration; door/light/temp state; current speed setpoint | Authority + speed limit currently in effect for its section; commanded switch position; crossing state | Current authority & speed limit (decoded from track signal); current setpoint from operator; velocity error `e_k` | Live authority/suggested-speed per train; live system-wide track state for the dispatcher display; throughput metrics |
| **Storage / format** | "Configurable, **possibly stored in a database**" per the Track Model requirement — see conflict in §4.6 | Not specified — likely per-train config object, not persisted centrally | Not specified — PLC program is a distinct artifact from the controller binary | Not specified | Track model "held in a database" per the CTC Office requirement — see conflict in §4.6 |
| **Who else depends on this data** | Train Model (terrain for dynamics); Track Controller (occupancy/switch truth) | Track Model (physical state to render) | Train Controller (authority passthrough — see §4.1); Track Model (switch/signal commands) | Train Model (setpoint, authority) | Track Controller (authority/speed limits it hands down); Track Model/Train Model indirectly via display |
| **Configuration-driven diversity impact** | — | — | 🟡 Diverse implementation requirement (§4.3) means the **same PLC-spec config must be consumed by two independently-built implementations** — config format must be implementation-agnostic | Same vital bar as Track Controller but diversity not explicitly required — open question, see §4.3 | — |

---

## 2. Module Requirements Overview

| Aspect | Track Model | Train Model | Track Controller (SW + HW) 🔴 | Train Controller (SW + HW) 🔴 | CTC Office |
|---|---|---|---|---|---|
| **Primary role** | Simulated physical model of the track layout | Simulated physical model of a train's dynamics | 🔴 Vital wayside controller that governs a section of track | 🔴 Vital onboard controller that governs a train | Dispatcher-facing central control point for the whole system |
| **Vital?** | No (physical sim, not a controller) | No (physical sim, not a controller) | 🔴 **Yes** — explicitly stated | 🔴 **Yes** — explicitly stated | Not stated vital, but issues authority that vital controllers rely on |
| **Configuration / data model** | See §1 | See §1 | See §1 | See §1 | See §1 |
| **Inputs it receives** | Switch position commands, signal/light commands from Track Controller | Authority (distance) from Wayside Controller; setpoint speed; brake command; speed/accel/decel limits; route info; temp control; door open/close; transponder input; track circuit input; tunnel light control; passenger e-brake | Authority & speed limits from CTC Office | Track signal (decoded for speed limit + authority); setpoint command from Transit Operator/driver | Dispatcher inputs (schedule, routing, section open/close, authority) |
| **Outputs it produces** | Track circuit signal (occupancy), signal/switch state, presence detection to Track Controller | Physical train state (position, velocity) consumed by Track Model | Commanded speed, authority, switch positions, lights → Track Model; switching of track; crossing lights/cross-bar; state of track/crossing/signals/trains reported back to CTC | Regulated speed to train; door/light control; station announcements; fault handling | Suggested speed & authority to controllers; throughput metrics; system-wide state display |
| **Failure modes to model** | Broken rail, track circuit failure, power failure | Train engine failure, signal pickup failure, brake failure (wheel slippage/power consumption optional) | Must **detect** broken rails and report track/crossing/train/signal state | Must **monitor for faults and act safely** | (not specified) |
| **Detection responsibilities** | Track circuits for **presence detection** (physical shorting of the circuit) | — | **Detects presence of trains**, detects broken rails (consumes Track Model's physical signal) | Decodes track signal for speed limit/authority | Monitors trains system-wide |
| **Diverse/redundant implementation** | Not required | Not required | 🟡 **Required** — "implementation must be diverse" for the PLC program vs. controller | Not explicitly required, but same vital bar applies | Not required |
| **Extra domain features** | Railway crossings; stations for loading/unloading; power limitations; track heater | Terrain-aware Newtonian point-mass dynamics; light controller for tunnels | Controls railway crossing gates + lights | Announces stations, opens/closes doors, on/off lights on schedule | Schedule trains, route trains, open/close sections for maintenance |
| **UI (NFR, all modules)** | Required | Required | Required (separately for HW and SW instances — see §4.3) | Required (separately for HW and SW instances — see §4.3) | Required — must display current state of entire system |

---

## 3. Cross-Cutting / Non-Functional Requirements (apply to every module)

- Executable on Windows 11; whole system submittable as one runnable executable; each subsystem also independently installable.
- Automatic demo mode with preset scenarios.
- System must run **≥10× wall-clock speed** and be pausable.
- Must use ≥1 architectural/design pattern from the course, documented.
- Any COTS components used must be identified.
- Vital aspects of the system and their effect on architecture/design must be explicitly described.
- 🔴 Train Controller and Track Controller specifically **must have a vital architecture**.
- Communications between office ↔ wayside ↔ train are **non-vital in the US** architecture the project follows (vital only in the European convention, per slide 30) — see tension in §3.1.

---

## 4. Points of Tension / Conflicts

### 4.1 🟡 Vital controllers riding on a non-vital communication channel
The deck states US-style rail comms (office↔wayside↔train) are **non-vital**, yet the Train Controller and Track Controller *themselves* are required to have a **vital architecture**. This is a direct tension: a safety-critical decision (speed/authority enforcement) is being made from data that may arrive corrupted, delayed, or duplicated over a non-vital link. The requirements don't specify who is responsible for closing this gap.
- **Affected modules:** Track Controller, Train Controller (consumers), CTC Office / Track Model (producers of the data being trusted).
- **Recommendation:** Decide explicitly whether "vital" here means the *controller logic* must fail safe even when its inputs are untrustworthy (checksums, staleness timeouts, fail-to-restrictive defaults), since you cannot make the wire itself vital without contradicting the slide's own non-vital-comms framing.

### 4.2 🟡 Overlapping ownership of presence/switch state between Track Model and Track Controller
- Track Model: "Should have track circuits for presence detection" and "need to show signals and switch machines."
- Track Controller: "Detects the presence of trains," "controls the switching of the track."

Both modules are described as owning detection/switch state. Read charitably, Track Model is the physical simulation (it *generates* the raw track-circuit short/open signal and *displays* switch position) while Track Controller *interprets* that signal and *commands* switch changes — but the deck never draws this boundary explicitly, and it's exactly the kind of ambiguity that caused past teams' "track traversal methods worked for train movement but not easy Wayside access" integration failure (peer retrospective, slide ~78).
- **Recommendation:** Pin down the interface contract early: Track Model exposes a physical/electrical-level signal; Track Controller is the only module allowed to interpret it and issue commands back. Don't let both sides implement "detection" logic independently.

### 4.3 🟡 "Diverse implementation" vital requirement vs. per-subsystem UI requirement
The Track Controller requirement explicitly demands the PLC program be "specifiable separately from the implementation" and that "implementation must be diverse" (i.e., N-version-style redundancy is implied for a vital component). Separately, the NFRs require **every subsystem to have its own UI** and be independently installable. Taken together this means you need **two independently-built, diverse HW/SW controller implementations, each with its own UI**, that must still agree/vote on a single safe outcome for the track. That's a materially larger scope than "one Track Controller module" and isn't costed anywhere else in the requirements (no mention of a voting/arbitration layer).
- **Affected modules:** Track Controller (HW), Track Controller (SW).
- **Recommendation:** Explicitly scope how much diversity is required (e.g., diverse PLC logic implementations behind a common interface vs. full diverse hardware/software stacks with voting), and decide if the Train Controller needs the same treatment — the deck only states diversity for the Track Controller, but both are marked vital.

### 4.4 🟡 10× real-time speed requirement vs. control-law timing assumptions
The Train Controller's control law is derived as a discrete-time PI controller with an explicit sample period `T` (trapezoidal integration, `u_k = u_k-1 + T/2(e_k + e_k-1)`), and the Track Model has time-based elements (crossing gate timing, track heater, PLC scan timing). Running the whole system at ≥10× wall-clock speed changes the effective `T` seen by every timed component. If Train Model/Controller, Track Controller PLC logic, and CTC scheduling don't all scale `T` consistently under fast-forward, you risk instability in the control loop or desynchronized crossing/signal timing that wasn't caught until integration — precisely the failure mode called out in the retrospective slides ("integration takes MUCH longer than expected").
- **Affected modules:** Train Model, Train Controller, Track Model, Track Controller.
- **Recommendation:** Define one shared simulation clock/tick contract up front (owned by whichever module drives time), and derive each module's control constants from it rather than hardcoding assumptions about wall-clock `T`.

### 4.5 🟡 Producer/consumer failure-mode pairs need a defined fault-injection contract
Track Model owns simulating failures (broken rail, track circuit failure, power failure) that Track Controller must *detect*; Train Model owns simulating failures (engine, signal pickup, brake) that Train Controller must *monitor and act on*. The architecture diagram's "Murphy" actor injecting faults directly into Track Model/Train Model reinforces this split, but no interface is specified for how a simulated fault becomes an observable signal to the corresponding controller.
- **Recommendation:** Define the fault-injection/fault-reporting interface as its own contract between each Model/Controller pair before implementation starts.

### 4.6 🟡 Two modules both claim to own "the database" for track layout
Track Model's requirement says the layout should be "configurable, possibly stored in a database." CTC Office's requirement separately says the "track model [is] held in a database." Both point at the same data (track layout/topology) as if their own module is the source of truth for it, and neither says the other module reads from it rather than owning its own copy.
- **Affected modules:** Track Model, CTC Office.
- **Recommendation:** Pick one owner for the canonical track layout store (Track Model is the natural owner, since it's the physical simulation) and have CTC Office treat it as a read/query dependency, not a second copy — otherwise the two can drift out of sync during a run.

---

## 5. Suggested Next Step

Before implementation, get explicit team sign-off on:
- The Track Model/Track Controller interface boundary (§4.2),
- What "diverse implementation" concretely means for the Track Controller (§4.3),
- Who owns the canonical track layout data store (§4.6),
- Default/starting values for the Train Controller's `Kp`, `Ki`, `T`, `Pmax` (§1) — the deck leaves these entirely to the team to derive and verify for stability.

These are the ones most likely to cause the "all at once integration failed" problem multiple past teams flagged in their retrospectives — they're all interface/ownership questions, not implementation questions, so they're cheap to resolve now and expensive to resolve after modules are half-built.
