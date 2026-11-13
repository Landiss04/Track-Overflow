# Track Controller (SW) — PLC Language

Reference for the PLC programming language that every wayside of the software Track
Controller runs, with two sample programs (one valid, one invalid) for demonstrations.
Read with [track_ctrl_sw.md](track_ctrl_sw.md) (use cases UC-03 to UC-06 and UC-09).

The language and its checks are implemented in `TrackCtrlSW/track_ctrl/plc.py` (compiler and
scan), `controller.py` (the wayside's I/O and the checks against it) and `vital.py` (the
generated vital code). Everything below was read from that code, and the sample programs were
compiled and run against wayside GTC-01 to confirm the results quoted here.

> **Branch state.** The input names are HW's again (`FAIL_n`, `SWREV_s`, `MAINT`), restored on
> 2026-10-22 after the last merges had replaced them. HW's own language has since moved on
> (section 9), and the window still starts with the Green and Red lines already loaded
> (section 9, problem 2).

---

## 1. What the language is for

A wayside Track Controller does one job: given what is on its territory, decide which
outputs to drive. The decision logic is a **PLC program**, written by a person in a very
small Boolean language and loaded from a file.

- **Boolean only** (REQ-FUNC-051). Every value is a single bit, 0 or 1. There are no numbers,
  no timers, no loops and no functions. That is what makes a program checkable: it has no
  arithmetic to overflow and no hidden state.
- **A scan cycle.** Once per tick the wayside copies its inputs into a bit image, runs the
  program top to bottom exactly once, and reads the outputs back out.
- **Not trusted.** After the user's program, the wayside runs a second, generated PLC program,
  the *vital code*, which can only make an output more restrictive. Only its `OUT_` bits leave
  the wayside (section 7). A wrong program therefore stops a train; it cannot cause a
  collision.
- **The same language as the hardware variant** (REQ-INTF-009). The grammar below is shared.
  The set of *names* a program may use is set by the wayside (section 5), and that set has to
  be kept the same on both variants (section 9).

The wayside's OS wrapper decides nothing. It only turns inputs into bits before the program
and bits into commands after the vital code.

```
  Track Model, CTC Office          OS decode            user program            vital code             OS encode
  occupancy, closures, ...  --->  input image  --->  assigns AUTH_n, SW_s, ... ---> OUT_ bits  --->  commands
                                   (bits)             (the programmer's code)    (generated code)     (typed outputs)
```

---

## 2. Lexical rules

A program is plain text, one statement per line.

| Element | Rule |
|---|---|
| Comment | `//` to the end of the line. It may follow a statement. A line with only a comment, or a blank line, is ignored. |
| Statement | One per line. A statement cannot be split over two lines. |
| Names | A letter or `_`, then letters, digits or `_` (`OCC_12`, `ROUTE_R_12`, `x1`). |
| Case | **Names are case-sensitive**: `A` and `a` are two different names. The words `VAR_IN`, `VAR_OUT`, `AND`, `OR`, `XOR` and `NOT` may be written in any case (`var_in`, `and`). Write them in upper case by convention. |
| Literals | `0` and `1` only. Any other digit string (`2`) is an error. |
| Reserved words | `VAR_IN`, `VAR_OUT`, `AND`, `OR`, `NOT`, `XOR`. They cannot be used as names or values. |
| Operators | `:=` (assignment), `NOT`, `AND`, `XOR`, `OR`, and parentheses `(` `)`. |
| Range | `..` inside a declaration only (section 3). |

---

## 3. Declarations

A program starts by declaring the bits it reads and writes.

```
VAR_IN   NAME [NAME ...]      // bits the program reads, provided by the wayside
VAR_OUT  NAME [NAME ...]      // bits the program drives; the wayside reads them after the scan
```

- A `VAR_IN` or `VAR_OUT` line must declare at least one name.
- Several declarations of each kind are allowed, in any order. They need not come before the
  statements, but a name should be declared before it is read.
- A name declared twice (in either kind) gives a warning, and the second declaration is
  ignored.
- Only names the wayside owns may be declared (section 5). The compiler does not know the
  wayside; the check against it is made when the program is run or committed (section 8).

### Ranges

A declaration may write a run of names with `..`, so a wayside with 25 blocks need not list
`OCC_1` to `OCC_25` one by one. Both spellings are accepted:

| Written | Expands to |
|---|---|
| `OCC_1..25` | `OCC_1`, `OCC_2`, … `OCC_25` |
| `OCC_1 .. 25` or `OCC_1 .. OCC_25` | the same |
| `OCC_A .. OCC_C` | `OCC_A`, `OCC_B`, `OCC_C` (single letters, same case) |
| `SPEED_0..3` | `SPEED_0` … `SPEED_3` |

Rules: the range runs over the **trailing** number or single letter of the first name. It must
not run backwards (`OCC_5..2` is an error). Letters must be single and of the same case
(`A..z` is an error). A range can only be written in a declaration, never in an expression.

---

## 4. Statements and expressions

### Assignment

```
TARGET := expression
```

- The target is an output (`VAR_OUT`) or an **intermediate** name. An intermediate is any name
  that is neither declared nor an input: it is created by being assigned, and lives only for
  this scan (`AHEAD_12 := OCC_13 OR OCC_14`).
- **An input cannot be assigned** (`OCC_5 := 0` is an error).
- A name may be assigned more than once, but the compiler warns: the last assignment in the
  scan wins.
- A name must be a `VAR_IN`, or be assigned on an **earlier line**, before it is read.
  Reading any other name is a warning, and the name reads as 0.

### Expressions

```
expression := or_expr
or_expr    := xor_expr ( OR  xor_expr )*
xor_expr   := and_expr ( XOR and_expr )*
and_expr   := unary    ( AND unary    )*
unary      := NOT unary | primary
primary    := '(' expression ')' | NAME | 0 | 1
```

| Precedence | Operator | Meaning |
|---|---|---|
| 1 (binds tightest) | `NOT` | inverts one operand |
| 2 | `AND` | 1 only if both operands are 1 |
| 3 | `XOR` | 1 if the operands differ |
| 4 (binds loosest) | `OR` | 1 if either operand is 1 |

Binary operators group left to right. So `A OR B AND C` means `A OR (B AND C)`, and
`A XOR B XOR C` is 1 when an odd number of the three are 1. When in doubt, use parentheses.

| A | B | A AND B | A OR B | A XOR B | NOT A |
|---|---|---|---|---|---|
| 0 | 0 | 0 | 0 | 0 | 1 |
| 0 | 1 | 0 | 1 | 1 | 1 |
| 1 | 0 | 0 | 1 | 1 | 0 |
| 1 | 1 | 1 | 1 | 0 | 0 |

Both sides of every operator are always evaluated (there is no short-cut), so a warning for a
bad read does not depend on the input values.

---

## 5. The wayside's inputs and outputs

Which names a program may declare depends on the wayside it is loaded on. The names carry the
**block number** or the **switch or crossing ID**. For GTC-01 (Green Line, blocks 1 to 25,
switch 12 with its points at block 13, signal 12, crossing 19):

### Inputs (`VAR_IN`)

| Name | Meaning (1 when …) | Source |
|---|---|---|
| `OCC_n` | block *n* is occupied. A train and a failure (broken rail, dead track circuit, power loss) look the same. | Track Model |
| `CLOSED_n` | the CTC Office has closed block *n* | CTC Office |
| `FAIL_n` | always 0: this wayside is told of no failures, and a failed block reads occupied. It is kept so a hardware program that names it still loads. | — |
| `MAINT` | the CTC Office has a switch command in effect (maintenance) | CTC Office |
| `SWREV_s` | switch *s* is reported reverse | Track Model read-back |

### Outputs (`VAR_OUT`)

| Name | Meaning | Reaches |
|---|---|---|
| `AUTH_n` | 1: block *n* passes the CTC Office's suggested speed and authority to the train in it. 0: speed 0, authority 0. | Track Model, as a track-circuit command |
| `SW_s` | switch *s*: 1 reverse, 0 normal | Track Model |
| `SIG_s_R`, `SIG_s_Y`, `SIG_s_G`, `SIG_s_SG` | the four lights of signal *s*: red, yellow, green, super green. Exactly one should be 1. | Track Model |
| `XING_c` | crossing *c*: 1 lights on and gates down | Track Model |

Notes:

- **The speed and authority numbers never enter a user program.** The program decides only
  whether a block *passes* (`AUTH_n`) or stops. The suggested speed reaches only the vital code,
  as bits no program can declare (`SUGSPD_n_b`), and the vital code clamps it to the block's
  posted limit. The OS then sends that speed, halved under a yellow signal, with the CTC
  Office's authority, or 0.
- The vital-only bits the generated code reads (`CTCCMD_s`, `CTCREV_s`, `HAND_s`,
  `HANDREV_s`) cannot be declared by a program. That is what stops a program from
  overriding the CTC Office's switch command or the hand-set position.
- A program cannot tell which way a train is heading: that would need a suggestion bit, which
  HW's language does not have. The generated starter therefore takes a train on a switch's
  leg to be coming for the points.
- For the **hardware** variant, the same grammar applies with its own name list (section 9).

---

## 6. Execution model

One **scan** per tick of the shared clock:

1. **Decode.** The OS builds the bit image from the inputs above.
2. **User program.** Every statement runs once, top to bottom. An assignment writes its bit
   immediately, so a later line sees it and an earlier line cannot.
3. **Vital code.** The generated program runs on the image plus the user program's outputs,
   and writes the final `OUT_` bits.
4. **Encode.** The OS turns the `OUT_` bits into the Track Model's commands and the CTC
   Office's report.

The scan keeps **no memory** between ticks. A program that needs to remember something must
read it back from an input (for example `SWREV_12`, the position the Track Model reports).
Order matters inside a scan:

```
T := NOT A      // T is assigned here ...
Z := T          // ... so this line sees it                       : fine
```
```
Z := T          // T is read before it is assigned: warning, T reads 0
T := NOT A
```

An output that is declared but never assigned holds at 0. An undriven `AUTH_n` therefore
stops its block, and an undriven signal is forced red by the vital code.

---

## 7. What happens after the program: the vital code

The vital code is generated for each wayside from its own territory, attached after whatever
program is committed, and not editable (it can be read, as `vital.plc`, in the Program tab).
It reads the program's outputs and the inputs, and writes each final output with an `OUT_`
prefix. It can only make an output *more* restrictive:

| Rule | Effect |
|---|---|
| `closed_block` | a block the CTC Office closed gets `OUT_AUTH_n = 0` |
| `switch_moving` | a block whose switch is not where it was commanded gets no authority |
| switch priority | in maintenance, `OUT_SW_s` is the CTC Office's command, else the hand-set position, else the program's `SW_s` |
| `switch_locked_under_train` | a switch with a train on it stays where it actually is |
| signal | a signal lighting none or several aspects, or on an occupied or closed block, is forced red |
| `aspect_speed_cap` | a yellow signal halves its block's speed (`OUT_HALF_n = 1`) |
| `speed_clamped` | a suggested speed over the block's posted limit is clamped to it (`OUT_SPD_n_b`) |
| crossing | a train on a crossing's approach arms it, whatever `XING_c` says |

Run in the Program tab, each rule that changed an output is listed as an **override**, so a
programmer sees where the program and the vital code disagreed.

---

## 8. Checks, run, commit

A program passes three gates before it reaches the track (UC-04 to UC-06).

1. **Compile.** Every line is read, and parsing continues after a bad line so all the
   problems are listed at once. A bad line is skipped.
2. **Fit.** The compiled program is checked against *this* wayside's own inputs and outputs.
3. **Run, then commit.** **RUN** scans the program once in a sandbox, on a copy of the
   wayside's inputs, through the vital code. **COMMIT** is offered only after a clean run of
   exactly that text, and checks again. The live outputs and the track are untouched by RUN.

**Any diagnostic, warning or error, blocks the commit.** Each describes a program that would do
something other than what it says.

### Diagnostics

| Severity | Message (abridged) | Raised when |
|---|---|---|
| Error | statement is not a declaration or an assignment | a line has no `:=` and does not start with `VAR_IN` or `VAR_OUT` |
| Error | `X` is not a valid assignment target | the left of `:=` is not a name |
| Error | `X` is an input and cannot be assigned | an assignment to a `VAR_IN` |
| Error | assignment has no expression / expression ended early | nothing, or an operator with no operand, on the right |
| Error | missing closing parenthesis | unbalanced `(` |
| Error | `AND` cannot be used as a value; unexpected / cannot read `'2'` | a reserved word or a stray character where a value belongs |
| Error | `VAR_IN` declares nothing; range … runs backwards / is not letters or digits | a bad declaration |
| Error | `X` is not an input / output of GTC-01 | a declared name this wayside does not have (fit) |
| Warning | `X` is declared more than once | a repeated declaration |
| Warning | `X` is assigned more than once; the last assignment wins | two assignments to one name |
| Warning | `X` is read before it is assigned and is not a `VAR_IN` | an undeclared or too-early read; it reads 0 |
| Warning | output `X` is declared but never assigned; it will hold at 0 | a `VAR_OUT` with no assignment (grouped into one line for several) |
| Warning | `AUTH` is not driven for block(s) … | the program does not declare `AUTH_n` for every block |
| Warning | `X` is not driven by this program | the wayside owns an output the program does not declare |

---

## 9. Where the language stands against the hardware variant

**Restored on 2026-10-22.** The merges of `origin/claude/quirky-fermi-sickg4` and
`origin/Train_Ctrl_integration` had replaced HW's input names (`FAIL_n`, `SWREV_s`, `MAINT`) with
`SUG_n`, `FAULT_s`, `MOVING_s` and `REV_s`, and left `build_scan_inputs` reading a field that
no longer existed, so no scan could run. The names are HW's again, the starter program uses
`SWREV_s`, and the layout folder is `Track_layout/`. The details are in
`TrackCtrlSW/CHANGELOG.md`.

**Two problems remain, neither in the language:**

1. **HW's language has moved on.** The hardware variant now feeds its programs the CTC Office's
   speed as five bits (`SPD_n_0` to `SPD_n_4`) and reads the commanded speed back as `CMD_n_0` to
   `CMD_n_4`. It also adds `CTCSW_s` and `CTCREV_s`, and has no `FAIL_n` or `MAINT`. A hardware
   program such as `green_wayside_1.plc` therefore fails the fit check on GTC-01 (`CTCSW_12 is not
   an input of GTC-01`), and three tests in `test_hw_language.py` fail. The grammar is still
   shared; the name sets are not, against REQ-INTF-009. This needs one language agreed with the
   hardware owner. It cannot be restored, because the earlier names no longer match HW, and
   matching HW now would put speed bits into the software PLC, which the vital design keeps out.
2. **The window starts with a track loaded.** The merge also took the earlier `state.py`, so
   `TrackControllerState()` loads Green and Red at start instead of starting with no track and
   an empty editor, and it lacks the `loadStarterPrograms` slot that `module_process.py`
   calls. Eight tests fail on it (see the test plan, section 7).

The two sample programs below use only `OCC_n`, `CLOSED_n` and `MAINT`, which are valid under
the restored names and under any earlier HW naming. They were compiled and checked against
GTC-01, and the valid one was run in a sandbox, after the restoration.

---

## 10. Sample programs

Both are for wayside **GTC-01**. Load GTC-01 (Green Line), then in the Program tab press
**Load .plc file**.

### 10.1 Valid: [`gtc01_valid.plc`](../../TrackCtrlSW/samples/gtc01_valid.plc)

A complete program of 67 lines for blocks 1 to 25, switch 12, signal 12 and crossing 19:

- **Declares** the inputs `OCC_1..25`, `CLOSED_1..25`, `MAINT`, and every output the wayside
  owns: `AUTH_1..25`, `SW_12`, the four `SIG_12_*`, `XING_19`.
- **Switch 12:** reverse for a train on block 1 (the reverse leg), normal otherwise and in
  maintenance. It uses an intermediate, `ROUTE_R_12`.
- **Signal 12:** red if its own block is occupied or closed; else yellow if block 13 or 14 is
  busy; else green. Exactly one light is lit, using the intermediate `AHEAD_12`.
- **Crossing 19:** armed while block 18, 19 or 20 is occupied.
- **Separation:** `AUTH_n := NOT (OCC_n AND (OCC_{n-1} OR OCC_{n+1}))`. An occupied block with
  an occupied neighbour is held; every other block passes the CTC Office's suggestion.

**Expected result.** RUN reports **no diagnostics**, the sandbox shows the outputs below, and
**COMMIT** is enabled. Committing it on all six waysides (each wayside needs its own program)
makes the Green Line ready.

Sandbox results, with a `(12 m/s, 4 blocks)` suggestion on blocks 5, 6, 7, 12, 13, 14 and 17 to
20 (taken on GTC-01):

| Situation | Outputs |
|---|---|
| Nothing occupied | signal 12 GREEN; switch normal; crossing off; every circuit passes `(12, 4)` |
| Block 14 occupied | signal 12 **YELLOW**; block 12's speed halved to `(6, 4)`; override `aspect_speed_cap` |
| Block 12 occupied | signal 12 **RED** |
| Block 18 occupied | crossing 19 **active** |
| Block 7 closed | block 7's circuit `(0, 0)`; override `closed_block` |
| Block 1 occupied | switch 12 commanded **reverse**; block 12 held `(0, 0)` until the read-back agrees; override `switch_moving` |
| Block 1 occupied, maintenance | switch stays normal (the CTC Office's command or a hand-set position governs) |

**To see the vital code override a program** (optional): on a copy, change the crossing line to
`XING_19 := 0`, RUN with block 18 occupied in the test UI. The program says "off", the sandbox
shows the crossing **active**, and the override list shows the vital code arming it.

### 10.2 Invalid: [`gtc01_invalid.plc`](../../TrackCtrlSW/samples/gtc01_invalid.plc)

The same program with ten deliberate faults, each marked `FAULT n` in a comment. RUN lists the
diagnostics below and **COMMIT stays disabled**. Fix them one at a time and RUN again; the
valid file is the corrected version.

| Fault | Where | What is wrong | Severity |
|---|---|---|---|
| 1 | `SIG_12_R = …` | `=` instead of `:=` | Error: *statement is not a declaration or an assignment* |
| 2 | `OCC_5 := 0` | assigns an input | Error: *OCC_5 is an input and cannot be assigned* |
| 3 | `AUTH_2 := NOT (…` | the closing `)` is missing | Error: *missing closing parenthesis* |
| 4 | second `VAR_IN OCC_20` | a name declared twice | Warning: *OCC_20 is declared more than once* |
| 5 | second `XING_19 := …` | assigned twice | Warning: *XING_19 is assigned more than once* |
| 6 | `SIG_12_SG` | declared, never assigned | Warning: *… outputs are declared but never assigned* |
| 7 | `… OR NEARBY` | a name never declared | Warning: *NEARBY is read before it is assigned and is not a VAR_IN* |
| 8 | `VAR_OUT AUTH_1..20` | `AUTH_21..25` not declared | Warning: *AUTH is not driven for block(s) 21 … 25* |
| 9 | `VAR_OUT SW_30` | another wayside's switch | Error: *SW_30 is not an output of GTC-01* |
| 10 | `VAR_IN OCC_99` | block 99 is not GTC-01's | Error: *OCC_99 is not an input of GTC-01* |

The parser pane shows 11 diagnostics, in this order (verified):

```
WARNING line  12  OCC_20 is declared more than once
ERROR   line  27  statement is not a declaration or an assignment
WARNING line  28  SIG_12_R is read before it is assigned and is not a VAR_IN; it reads as 0
ERROR   line  31  OCC_5 is an input and cannot be assigned
WARNING line  34  XING_19 is assigned more than once; the last assignment in the scan wins
WARNING line  34  NEARBY is read before it is assigned and is not a VAR_IN; it reads as 0
ERROR   line  37  missing closing parenthesis
WARNING line  17  4 outputs are declared but never assigned (AUTH_2, SIG_12_R, SIG_12_SG, SW_30); they will hold at 0
ERROR   line  15  OCC_99 is not an input of GTC-01
ERROR   line  21  SW_30 is not an output of GTC-01
WARNING line   0  AUTH is not driven for block(s) 21, 22, 23, 24, 25; they will always send speed 0 and authority 0
```

Four of the eleven are consequences of the first faults. Fault 1's skipped line leaves `SIG_12_R`
unassigned, which also makes the next line's read of it a warning. Fault 3's skipped line leaves
`AUTH_2` unassigned. Fault 9's `SW_30` is also never assigned. Fixing the cause clears them too.

**What the demonstration shows.** The same module accepts the first program and refuses the
second, for two different reasons: the *compiler* refuses lines it cannot read (faults 1 to 3),
and the *fit and safety checks* refuse a program that compiles but would not do what it says
(faults 4 to 10). A program that did reach the track would still be limited by the vital code
(section 7).
