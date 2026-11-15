# Proposal for the owner of `plc.py`: run channel A as one expression per statement

**Status:** proposal only. `TrackCtrlHw/track_ctrl_hw/plc.py` is **not changed** on branch `10x-pi-speed`; the diff below was applied to a throwaway copy
of the repository to measure it. Whether to take it, and how it is reviewed, is the owner's decision: this is vital logic, and channels A and B
are deliberately two different implementations of the same statements.

## Why

On the Track Pi the core step is 4.7-5.6 ms of a 10 ms slot at 100 Hz (10x), and 95% of the core step is the PLC interpreter (profile in `10x-log.md`).
Channel A turns each statement's tree into nested Python functions (`_walker`), one call per tree node. On the Pi, in one agent process, channel A is also
the part that slows down most from one session to the next: 1.22, 1.50, 1.72, 1.93 ms per step over four sessions (+59%), against channel B 1.73 to 2.13 ms (+23%) and the rest of
the step flat (+3%). The cause of that slowdown is not found; the closure tree is its biggest single contributor.

## The change (47 lines of diff, no behavior intended to change)

`_walker` is kept. Channel A's trees are compiled, on the first scan as before, into one function per **statement** whose body is the same logic as one Python
expression; a tree too deep to compile falls back to `_walker`.

```diff
@@ -241,6 +241,35 @@
     return lambda values: left(values) != right(values)
 
 
+def _expression(node: Node) -> str:
+    # The same logic as _walker, written out as the text of one Python
+    # expression over the scan's values `v`: AND and OR still stop early,
+    # XOR is still `!=`, an undefined read is still 0.
+    if isinstance(node, Constant):
+        return repr(node.value)
+    if isinstance(node, Read):
+        return f"v.get({node.name!r}, False)"
+    if isinstance(node, Negate):
+        return f"(not {_expression(node.operand)})"
+    left = _expression(node.left)
+    right = _expression(node.right)
+    if node.operator == "AND":
+        return f"({left} and {right})"
+    if node.operator == "OR":
+        return f"({left} or {right})"
+    return f"({left} != {right})"
+
+
+def _flat_walker(node: Node) -> Walker:
+    # One function per statement instead of one per tree node, so a scan
+    # makes one call per statement and no calls between nodes. A tree too
+    # deep to compile keeps the nested functions of _walker.
+    try:
+        return eval("lambda v: " + _expression(node), {})
+    except (SyntaxError, RecursionError, MemoryError):
+        return _walker(node)
+
+
 def _tree_reads(node: Node) -> list[str]:
     if isinstance(node, Read):
         return [node.name]
@@ -401,7 +430,7 @@
     def _walkers(self) -> tuple[tuple[str, Walker], ...]:
         # Channel A's trees as functions, made on the first scan.
         return tuple(
-            (statement.target, _walker(statement.tree))
+            (statement.target, _flat_walker(statement.tree))
             for statement in self.statements
         )
 
```

Same semantics: `AND` and `OR` stop early (`and` / `or` on booleans), `XOR` is `!=`, `NOT` is `not`, an undefined read is 0 (`v.get(name, False)`), a constant is its value.
Programs still pickle the same (`__getstate__` drops `_walkers`), the program text, checksum and diagnostics are untouched, and channel B is untouched.

## Evidence

| Check | Result |
| --- | --- |
| `TrackCtrlHw/tests` on the patched copy | 116 passed, 54,633 subtests passed (the same as the unpatched copy) |
| 4,000 random trees (depth up to 7, constants, an undefined name) over all 64 input combinations of six names | 256,000 comparisons of `_walker` and the flat form, 0 differences |
| The real Red programs (6), random inputs | 18,000 scans of channel A old against new, 0 differences |
| The recorded Red workload, in a replay (sandbox and on the Pi) | 23,964 channel A scans compared in each, 0 differed |

Timing, Raspberry Pi 5, Python 3.13.5, `PYTHONOPTIMIZE=1`, the first 4,000 lines of the recorded Red workload replayed four times in one process (a new session each time), no USB and no service (`plcbench.py`, ms per step):

| Session | Core, now | Core, flat | Channel A, now | Channel A, flat | Channel B, now | Channel B, flat |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 4.241 | 3.839 | 1.218 | 0.876 | 1.726 | 1.742 |
| 2 | 4.791 | 4.155 | 1.501 | 0.919 | 1.973 | 1.986 |
| 3 | 5.117 | 4.431 | 1.718 | 1.018 | 2.073 | 2.143 |
| 4 | 5.401 | 4.481 | 1.932 | 1.025 | 2.127 | 2.180 |

- The core step is 0.40 ms lower in the first session and 0.92 ms lower in the fourth. Channel A's growth over the four sessions drops from +0.714 to +0.149 ms.
- Not changed by it: channel B (1.73 to 2.18 ms, +0.44) still grows, and so does the rest of the step (+0.055). Flat channel A does **not** remove the per-session slowdown; it removes about 80% of channel A's share of it
  and lowers the level. Measured only in this in-process benchmark, not yet through the service and the link.
- Same code on an x86 sandbox, Python 3.13.18: channel A 0.64-0.69 ms to 0.46-0.47 ms (about 30% lower).

## Points for the review

- **Generated code.** The only text put into the generated expression is `repr()` of a name that the tokenizer has already restricted to `[A-Za-z_][A-Za-z0-9_]*`, a constant's `repr`, and fixed operators; `eval` runs with empty globals.
  If the project does not allow `eval` in vital code at all, the same expression can be built as a nested function without `eval`, but that gives up most of the saving.
- **Diversity of the two channels.** A is still a recursive-descent tree evaluated with short-circuiting; B is still a postfix stack machine. What changes is how A's tree is executed. Whether that is diverse enough is for the owner.
- **Fallback.** A tree that raises `SyntaxError`, `RecursionError` or `MemoryError` when compiled keeps the nested functions, so a very deep statement behaves as today. None of the 1,151 statements in the six Red programs takes that path, and a 400-deep tree still compiles and evaluates correctly.
- **Not tried:** the same idea for channel B, or building the programs a different way; the Pi's Python is 3.13.5 and the sandbox's is 3.13.18, and the climb is seen only on the Pi.

## Reproduce

`plcbench.py` (kept outside the repository, with the recording slice `track-red-4k.jsonl`, the first 4,000 lines of the 180 s Red recording) runs sessions of the recording in one process on the Pi:
`cd /opt/track-overflow` then `PYTHONOPTIMIZE=1 PYTHONDONTWRITEBYTECODE=1 python3 plcbench.py track-red-4k.jsonl --sessions 4 [--variant flat] [--verify]`.
