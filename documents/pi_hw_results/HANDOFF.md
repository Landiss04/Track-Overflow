# Handoff: 10x Pi speed work (read this first)

Published on GitHub as branch `hw_pi_test` (off `main` at `e3077ae`); worked on locally as `10x-pi-speed`. `Co-Authored-By` trailer for Claude. Step-by-step guides: `guide-track-controller-pi.md`, `guide-train-controller-pi.md`; test menu `bench\pi_test_menu.cmd`; what changed and the owner sections: `what-was-changed.md`. Latest report: `10x-final-report.md`; every number is in `10x-log.md`.
Scratch clone (container only, may disappear): `/tmp/claude-0/-home-user-Track-Overflow/47598598-f0c8-590b-bfc0-e5e8b4ac2081/scratchpad/work`; its bundles are in `../out/new/` next to it.
**The durable copy is `origin/hw_pi_test` on GitHub** (on the host: `git fetch origin hw_pi_test`). The scratch clone above can disappear.

## State (2026-11-15)
- Agent hash `0a7cf856` in every Pi bundle since `563b63f`; nothing on a Pi needs reinstalling for host-side changes.
- The board (Raspberry Pi 5) now runs the **Track** agent again (bundle with the flat channel A, sha256 df1bea35...d70c, agent hash 8d1c457a; the host must run the same code). The Train journal/logs are in `/var/lib/track-overflow/old-train/`. Switching module needs: stop the agent, move the journal and log aside, unpack the other bundle into a fresh folder and `sudo ./install.sh`, `sync`, **reboot** (the gadget refuses to change a bound USB identity). `measure`/`per_module` treat a Pi as physical unless told otherwise: for one real Pi always pass the other with `--...-controller-pi process`, or the harness waits forever for the missing Pi.
- Results (stress schedule `utils/schedule_stress.json`, Windows host, 10x, headless, 600 s): Track Pi real 8.45x before and **9.99x with the flat channel A (`97bdb75`, agent hash 8d1c457a, three runs 9.94/9.49/9.99x)**; Train Pi real 7.60x; both real estimated 7 to 8.5x (not measured). Track Controller is the slowest module in 85-93% of ticks.
- Done this stretch: `bringup` tolerant mode, `--strict`, `--trace-csv`; `measure --system` takes `--track-controller-pi`, `--train-controller-pi`, `--dispatch`, `--schedule`, gives gains to both Train Controllers, names workload and Pi modes in its report; `bench/per_module.py --per-tick-csv`, `bench/estimate_both.py`; Pi how-to sections 9 and 10; `plc-channel-a-flat-proposal.md` (a tested diff for the `plc.py` owner, not applied); `ctc-office-tail.md` (profile and A/B, nothing applied).
- Tests: `common/hw_link` 237 passed + the 2 `test_bundle_is_offline_stdlib_and_shell_parses` that need physical Pis (ignore); `common/harness/tests` 7 fail on this branch and on `main` alike (unrelated); `TrackCtrlHw/tests` 116 passed.

## Not done / open
- Clean all-simulated baseline, 600 s, twice, on a quiet PC (the 60 s one was disturbed by clipboard errors). Both Pis real together; the harness event log to confirm what changes at about 2,600-2,900 simulated seconds.
- CTC Office tail: the user chose to KEEP the experiment in this branch (commit `d660690`, `WINDOW_REFRESH_MS_AT_SPEEDUP = 1000` in `CTC-Office/ctc/module_process.py`; revert the commit or set the constant to 200 to undo). Sandbox: 9.8x -> 10.00x all-simulated; Track-Pi-physical 600 s: speed unchanged at 8.45x, tail smaller (see `10x-log.md`). The CTC Office owner (unassigned) still has to accept it, and the 1 s-old window at 10x is their UI call.
- Per-session slowdown of the Track core (4.7 -> 5.2 -> 5.6 ms): cause not found; restart the agent before a run you will compare. The flat channel A is applied as an experiment (`97bdb75`); the `plc.py` owner must decide (see `commits-for-owner-review.md`).
- Damaged VIEW lines on the link (0-3% per run, display-only): cause not found.
- All-windows run, GPU/WARP check, `QSG_INFO=1` line (need the target machine); original-versus-now on the Pi (`e3077ae` bundle); README section 5 mapping (that README is not in the repo; items are listed by the log's numbering); Green/Red on the HW Pi (`common/harness/edges.py` routes Red only).
- Left on the Pi: `~/.local/bin/py-spy`, files in `~/Downloads` and `/tmp`; confirm `/etc/systemd/system/track-overflow-agent.service.d/` has no `malloc.conf`.

## Rules in force
No push, no merge into the user's repo, no repo changes outside this branch; rebuild both bundles after every source change (`python -m common.hw_link.provision --module <m> --output <file>`); `sync` on the Pi before unplug; no `config.txt` edit or reboot without telling the user; ask before any wire-protocol change or any edit to another module's code (`plc.py`, `CTC-Office/`, `track_ctrl_hw`); one change at a time with before/after rows in `10x-log.md`.

## Practical lessons from this stretch
- `pgrep -af "common.hw_link.agent"` must list exactly one agent before any link test or run (two agents on `/dev/ttyGS0` invalidated a whole set of results).
- Clipboard history off, copy nothing for a minute before and during a run (a run with clipboard lines lost 0.45x); runs that began with `qt.qpa.mime: ... clipboard` messages were the noisy ones. Plugged in, nothing else heavy running.
- Never run `git checkout <file>` (or `ln -sf` over a real file) with uncommitted work in a clone: commit first. The harness blocked one such command and one real file was replaced with a broken link (restored).
- Bundles all share the file name `10x-pi-speed.bundle`: check the size and `git log --oneline -1` after merging, or you will measure with old code.
- The report header used to say "one train" whatever ran; it now names the workload.
