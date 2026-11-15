# Scratch tools used while measuring the Pis

**Status:** working scratch scripts, kept so the measurements can be repeated or checked. They are **not** reviewed, not style-checked and not covered by tests, and most take positional arguments and write to the current directory. Run them from the repository root. The ones that import `common.hw_link` need no Pi; the ones marked "Pi" are meant to be run on the Pi from `/opt/track-overflow`. Paths in the `.sh` files are the ones used in the Linux sandbox.

The four link tools `linkcheck.py`, `qtcheck.py`, `bringup_trace.py` and `sizes2.py` were used on the Windows host, but are **not** here: the copies in the working area were lost when the session context was cleared. The user's copies are in `..\trains_pi\`.

| Tool | What it does |
| --- | --- |
| `capture.py` | Records the STEP inputs a real Red run sends to both Pi cores (a JSON capture). |
| `make_track_recording.py` | Writes the Track replay file (`bench/recordings/track-red-180s.jsonl`) from a capture. |
| `bench_agent.py` | Runs the real agent over a pty with STEPs paced at 10 ms; sandbox numbers only. |
| `inproc.py`, `micro_train.py` | In-process timing of the cores without the link. |
| `green_on_hw.py` | Runs a real Green train through the software controller, replays its inputs on the HW core. |
| `ckpt_split.py`, `ckpt_verify.py`, `ckptgrow.py`, `ckptsplit.py` | Size and cost of the Track core's checkpoint, and that the lean checkpoint restores the same. |
| `growth.py`, `passes.py`, `gcpasses.py` | The Track core getting slower in each later session of one process (memory growth, per-pass timing, garbage collection). |
| `viewcost.py`, `viewdecode.py` | What the display (VIEW) lines cost the agent. |
| `plcbench.py` | PLC benchmark: several sessions of one recording in one process, `--variant baseline\|collect\|flat`, `--verify` for the flat form. **Pi.** |
| `flat_equiv.py` | The flat channel A against the nested form on random trees and the real programs. |
| `spytop.py`, `ctc_analyze.py` | Summaries of `py-spy` profiles (Pi agent; CTC Office process in speedscope format). |
| `tracestats.py` | What the round trips over 10 ms have in common, from `bringup --trace-csv`. |
| `ab.sh`, `ab2.sh` | Alternate two copies of the repository on the same all-simulated 40 s run (A/B). |
| `run_suites.sh` | Runs the test suites one at a time. |

The tools actually used for the headline numbers are in `bench/` itself: `per_module.py`, `estimate_both.py`, `tickstats.py` and `pi_test_menu.cmd`.
