# Handoff: 10x Pi speed work (read this first)

Branch `10x-pi-speed`, local only, nothing pushed. Author paperbird, `Co-Authored-By` trailer for Claude. Latest report: `10x-final-report.md`; every number is in `10x-log.md`.
Scratch clone (container only, may disappear): `/tmp/claude-0/-home-user-Track-Overflow/47598598-f0c8-590b-bfc0-e5e8b4ac2081/scratchpad/work`; its bundles are in `../out/new/` next to it.
**The durable copy is the bundle on the host** (`..\trains_pi\10x-pi-speed.bundle`, then `git fetch <bundle> 10x-pi-speed` and `git merge --ff-only FETCH_HEAD`). The host was last merged at `77d5bf7`; later commits are docs and a report-header change in `measure.py`.

## State (2026-11-15)
- Agent hash `0a7cf856` in every Pi bundle since `563b63f`; nothing on a Pi needs reinstalling for host-side changes.
- The board (Raspberry Pi 5 "ivz11") now runs the **Train** agent (bundle built at `5d19539`, sha256 558c57b2...). The Track journal/log are in `/var/lib/track-overflow/old/`. Switching module needs: stop the agent, move the journal and log aside, install the other bundle, `sync`, **reboot** (the gadget refuses to change a bound USB identity).
- Results (stress schedule `utils/schedule_stress.json`, Windows host, 10x, headless, 600 s): Track Pi real 8.45x; Train Pi real 7.60x; both real estimated 7 to 8.5x (not measured). Track Controller is the slowest module in 85-93% of ticks.
- Done this stretch: `bringup` tolerant mode, `--strict`, `--trace-csv`; `measure --system` takes `--track-controller-pi`, `--train-controller-pi`, `--dispatch`, `--schedule`, gives gains to both Train Controllers, names workload and Pi modes in its report; `bench/per_module.py --per-tick-csv`, `bench/estimate_both.py`; Pi how-to sections 9 and 10; `plc-channel-a-flat-proposal.md` (a tested diff for the `plc.py` owner, not applied); `ctc-office-tail.md` (profile and A/B, nothing applied).
- Tests: `common/hw_link` 237 passed + the 2 `test_bundle_is_offline_stdlib_and_shell_parses` that need physical Pis (ignore); `common/harness/tests` 7 fail on this branch and on `main` alike (unrelated); `TrackCtrlHw/tests` 116 passed.

## Not done / open
- Clean all-simulated baseline, 600 s, twice, on a quiet PC (the 60 s one was disturbed by clipboard errors). Both Pis real together; the harness event log to confirm what changes at about 2,600-2,900 simulated seconds.
- CTC Office tail (owner unassigned): refresh costs about 27 ms five times a second; refresh off reaches 10.00x in the sandbox. Waiting for a decision whether to try the cheapest mitigation in this branch.
- Per-session slowdown of the Track core (4.7 -> 5.2 -> 5.6 ms): cause not found; restart the agent before a run you will compare. A flat channel A is the owner's call.
- Damaged VIEW lines on the link (0-3% per run, display-only): cause not found.
- All-windows run, GPU/WARP check, `QSG_INFO=1` line (need the target machine); original-versus-now on the Pi (`e3077ae` bundle); README section 5 mapping (that README is not in the repo; items are listed by the log's numbering); Green/Red on the HW Pi (`common/harness/edges.py` routes Red only).
- Left on the Pi: `~/.local/bin/py-spy`, files in `~/Downloads` and `/tmp`; confirm `/etc/systemd/system/track-overflow-agent.service.d/` has no `malloc.conf`.

## Rules in force
No push, no merge into the user's repo, no repo changes outside this branch; rebuild both bundles after every source change (`python -m common.hw_link.provision --module <m> --output <file>`); `sync` on the Pi before unplug; no `config.txt` edit or reboot without telling the user; ask before any wire-protocol change or any edit to another module's code (`plc.py`, `CTC-Office/`, `track_ctrl_hw`); one change at a time with before/after rows in `10x-log.md`.

## Practical lessons from this stretch
- `pgrep -af "common.hw_link.agent"` must list exactly one agent before any link test or run (two agents on `/dev/ttyGS0` invalidated a whole set of results).
- Do not touch the keyboard or clipboard during a run; runs that began with `qt.qpa.mime: ... clipboard` messages were the noisy ones. Plugged in, nothing else heavy running.
- Never run `git checkout <file>` (or `ln -sf` over a real file) with uncommitted work in a clone: commit first. The harness blocked one such command and one real file was replaced with a broken link (restored).
- Bundles all share the file name `10x-pi-speed.bundle`: check the size and `git log --oneline -1` after merging, or you will measure with old code.
- The report header used to say "one train" whatever ran; it now names the workload.
