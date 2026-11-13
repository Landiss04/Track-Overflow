# Module owner review: Braden's answers

**From:** Braden Bosilovich (Track Controller HW owner) · **To:** Kevin Schillinger
**Date:** 2026-10-26 · **Answers:** [module-owner-review.md](module-owner-review.md)
**Branch:** `feature/TrackCtrl-HW-vital`, cut from `claude/quirky-fermi-sickg4` at
`74159e9`. Only `TrackCtrlHw/` and this file changed. Everything that needs a
change in someone else's code is listed under
[Changes requested of others](#changes-requested-of-others); none of it was made.

| Review | Answer | Who acts |
| --- | --- | --- |
| [HW-1](#hw-1-red-plc-programs) | The Red programs are now mine; a vital block runs after every program | Done (this branch); Kevin to merge |
| [CTC-1](#ctc-1-and-ctc-2-adjacent-trains) | The CTC Office keeps one empty block between trains | Landis |
| [CTC-2](#ctc-1-and-ctc-2-adjacent-trains) | Same decision | Landis; Harry for SW programs |
| [INPUT-1](#input-1-missing-occupancy) | A block the wayside expects and is not sent counts as occupied | Kevin (harness), then both variants |
| [SW-1](#sw-1-vital-code-in-both-variants) | Both variants append a generated read-only vital PLC block | Done in HW; SW is Harry's, already on `development` |
| [LAYOUT-1](#layout-1-red-block-9) | HW follows the Track Model's layout | Track Model owner |
| [TM-2](#tm-2-light-ahead) | Signals sit at switches | Track Model owner |
| [PI-1](#pi-1-physical-pi) | Plan below; I will run the Track Controller board | Braden; Train Controller HW owner |

---

## HW-1: Red PLC programs

**Answer.** I replaced the three Red test copies with my own programs. The file
names are unchanged (`TrackCtrlHw/data/plc/red_wayside_{1,2,3}_integration_test.plc`)
so the harness and its tests need no edit; renaming them is requested below.
The databases (`data/waysides/red_wayside_*_integration_test.json`) are your
exact cuts and are unchanged; I accept them.

Your copies were sound: no compile errors, every one of the 32 speeds capped
correctly on all 76 blocks on both channels, each `AUTH_n` reading exactly its
course-file neighbours, and every signal lighting exactly one aspect in every
input combination I tried (up to 11 of each signal's inputs). What changed
and why:

1. `AUTO_9 := FALSE` read an undeclared name `FALSE` (0, with a compiler
   warning). It is now `AUTO_9 := 0`. The yard leg stays the CTC Office's to
   select.
2. Separation at points counts only the leg the switch reports set. Before,
   a train on switch 52's points was held by a train on leg 66 even with the
   switch normal. A train on a leg is still held by a train on the points.
3. A moving switch still stops its points and both legs, as in your copies, but
   not the fixed-side block. I tried that, and `test_red_routing_loop` failed
   at tick 3798 on the return: R1's track circuit fell to speed 0 and
   authority 0 while it was running, and the Train Controller HW read that as a
   signal pickup failure and applied the emergency brake. Removing only the
   fixed-side hold made the test pass again. The likely moment is switch 52
   swinging back to normal just after R1 left its points for 51. See request 9
   below.
4. The speed is the CTC Office's, passed with authority; the per-block limit
   comparators moved to the vital block, which generates them from the
   database.
5. Every section is commented, in the style of the Green samples.

**The vital block.** Harry and I agreed that both variants append a generated,
read-only vital PLC block after the user's program. HW's is
`TrackCtrlHw/track_ctrl_hw/vital.py`: generated per wayside from its database,
compiled once, scanned on both channels after the program, reading the
program's outputs and writing the outputs the wayside drives (`OUT_*`). It can
only restrict:

- authority: none in a closed block, while a block a train there could move
  into is occupied (route-aware at points), or while a switch on that block is
  moving;
- speed: capped at the block's limit, 0 without authority;
- switches: the CTC Office's command wins; a train on the points or listed
  block locks the switch where it reports;
- signals: red unless exactly one aspect is lit and the points are clear;
- crossings: active for a train on or beside them.

A vital channel disagreement is a latched channel fault. The PLC details
window shows the vital checksum, source and last-scan overrides. HW and SW
differ on purpose (no hand-set switches and no yellow halving in HW; speed is
the HW program's, under the vital cap; names differ).

**Evidence.** On this branch, `TrackCtrlHw/tests`: see the test summary in the
branch's last commit message. `tests/test_vital.py` proves every rule against a
program that grants everything, and that the Red programs compile with no
warnings. Your `test_red_integration.py` and `test_red_routing_loop.py` pass
unchanged.

## CTC-1 and CTC-2: adjacent trains

**Decision (Braden and Harry, 2026-10-26).** The CTC Office keeps one empty
block between trains. A wayside cannot tell a leader from a follower on a
two-way block, because it has no direction and no memory between scans; Red is
two-way on every block. So it holds a train while a block it could move into is
occupied, and that stops a follower and its leader together. With one empty
block between them, R1 at 65 keeps its authority while R2 waits at 63. On
one-way Green blocks the HW vital block already holds only the train behind.

**Requested of Landis:** stop authority two blocks short of an occupied block
(today it stops one short), and supersede the truth entry
`arbitration/authority-stops-before-obstruction.md` accordingly. Head-on
moves on two-way sections stay the CTC Office's zone reservation; the wayside
stops two trains facing each other but cannot resolve them.

## INPUT-1: missing occupancy

**Decision.** A block the wayside expects (its own, or a declared neighbour)
that the inputs do not report counts as occupied, the usual fail-safe for a
failed track circuit. It is also reported to the CTC Office as occupied, which
the CTC already treats as an unexplained occupancy and routes around.

**Blocked on the harness.** Today absence *is* how clear is sent: the Track
Model reports every block, and the harness edge keeps only the occupied ones
(`common/harness/edges.py`, `hw_wayside_edges.py`). The HW change is a few lines
once the inputs carry every reported block; it is not made yet, because the
format is the harness's. Freshness is the harness's barrier: a late or down
module holds the clock. SW's cross-wayside question (150 to 28) is Harry's.

## SW-1: vital code in both variants

Agreed with Harry. Note that SW-1 describes SW's old Python `supervise()`,
which is what `claude/quirky-fermi-sickg4` still carries. Harry's current code
(`development`, `13d9d66`) already generates vital PLC code
(`TrackCtrlSW/track_ctrl/vital.py`, `vital_source`) and appends it the same way.
The integration branch should take Harry's version.

## LAYOUT-1: Red block 9

HW reads the Red line the way the Track Model does; your
`test_every_red_switch_agrees_in_all_readers` checks it. Landis ruled the Track
Model's layout is the master, so the switch 9 reading (points 9, normal 8,
reverse yard, fixed side 10) is the Track Model owner's to confirm. HW will
follow whatever is confirmed.

## TM-2: light ahead

Signals sit at switches, as the professor stated: one signal per switch, at the
switch, with the switch's ID. The Track Model should pick a train's next signal
from that.

## PI-1: physical Pi

I will bring up the Track Controller board from `pi-owner-setup.md` and
`pi-bringup-checks.md`: provision from the same source as the host, install,
check `/sys/class/udc` and the services, then `bringup --list`, the 20-second
HELLO probe and a cold-boot timing, the 1/10/20 KiB echo, the recorded Red
workload, and the real-board fault checklist. Two dependencies:

- The full-system measurements need both boards: the Train Controller HW owner
  is still not named.
- This branch changes the HW core, so the bundle hash changes and the vital
  block adds a second scan per wayside. I will re-run the recorded workload
  after this branch is merged.

---

## Changes requested of others

1. **Merge hazard on `development` (Kevin; Braden's PR #51).** Commit `70289dc`
   on `wp2/combined-sdd`, merged to `development` by PR #51 on 2026-10-26,
   brought this integration branch's history into `development` but returned
   its content to `development`'s version (264 paths, including `common/hw_link`
   and the Red territories and programs). Git now treats those integration
   commits as merged and their content as deliberately removed, so a normal
   merge of `claude/quirky-fermi-sickg4` into `development` silently drops
   them. The merge base is `f6ed1a1`; `common/hw_link` exists there and
   `development` deleted it. A correct merge needs the older base, for example
   `git merge-tree --write-tree --merge-base=f590f41 origin/development
   origin/claude/quirky-fermi-sickg4`, which leaves about 38 conflicts:
   TrackCtrlSW `controller.py`, `state.py`, `README.md`; TrackModel
   `interface.py`, `test_link/codec.py`, `INTEGRATION.md`,
   `knowledge/CODE_OVERVIEW.md`, `tests/helpers.py`; about 30 CTC SDD and UML
   files; and `TrackCtrlHw/track_ctrl_hw/wayside.py` (take this branch's).
2. **Harness, INPUT-1 (Kevin).** Carry every block the Track Model reports
   (a block-to-occupied map, or the reported set beside the occupied set) on
   the Track Controller edges and both variants' wire formats. Then HW reads an
   expected block that is absent as occupied; Harry decides SW's.
3. **CTC Office (Landis).** One empty block between trains, and the truth entry,
   as under CTC-1.
4. **Integration branch, SW (Kevin, with Harry).** Take Harry's `development`
   TrackCtrlSW (generated vital PLC code) in place of the old `supervise()`.
5. **Track Model owner.** TM-2 as above; confirm LAYOUT-1's switch 9.
6. **Red file names (Kevin).** Optional: rename
   `red_wayside_{n}_integration_test.{json,plc}` to `red_wayside_{n}.*`, drop
   `integration_test_only`, and update `common/hw_link/host.py`, the harness
   tests and `TrackCtrlHw/tests/test_red_integration.py`.
7. **Pi bundle.** Regenerate both bundles after merging this branch (the HW core
   changed).
8. **Owners still unnamed.** Train Controller HW (PI-1) and Track Model
   (LAYOUT-1, TM-1 to TM-3).
9. **Train Controller HW owner: a wayside stop reads as a failure.**
   `Train-Ctrl_HW/train_ctrl/control.py` (around line 297) declares a signal
   pickup failure, and so an emergency brake, whenever the track circuit goes
   from a moving speed and at least `PICKUP_DETECT_MIN_BLOCKS` of authority to
   exactly 0 and 0. That is also what a wayside sends when it legitimately
   withdraws authority: a block closed ahead, a train moving onto a
   neighbouring block, a switch starting to move. With the one-empty-block
   rule the first two should be rare, but they are not failures. The Train
   Controller owners should decide how to tell them apart.

### Truth entries to record (not written as proposals)

- Decision: both Track Controller variants append a generated read-only vital
  PLC block after the user's program; it can only restrict (Braden and Harry,
  2026-10-26). Withdraws proposal D019 ("no vital layer").
- Decision: signals sit only at switches, one per switch, with its ID (the
  professor, relayed by Braden 2026-10-26).
- Arbitration: the CTC Office keeps one empty block between trains; supersedes
  `authority-stops-before-obstruction` (Braden and Harry 2026-10-26; Landis to
  agree).
- Arbitration: an expected occupancy input that is not reported counts as
  occupied (Braden 2026-10-26; Harry to agree for SW).
- Track Controller HW variant: the PLC program decides speed under a vital cap;
  no hand-set switch control.
