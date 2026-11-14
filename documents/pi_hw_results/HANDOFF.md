# Handoff: 10x Pi speed work (read this first)

Branch `10x-pi-speed`, HEAD in the scratch clone. Local only, nothing pushed. Author paperbird, Co-authored-by trailer for Claude.
Scratch clone: `/tmp/claude-0/-home-user-Track-Overflow/47598598-f0c8-590b-bfc0-e5e8b4ac2081/scratchpad/work`
Bundles on the host side: `..\trains_pi\` (git bundle `10x-pi-speed.bundle`, `train-pi.tar.gz`, `track-pi.tar.gz`, recordings `train-red-*.jsonl`, `track-red-*.jsonl.gz`).
The host is on `main`/the branch via `git fetch <bundle> 10x-pi-speed` then `git merge --ff-only FETCH_HEAD`.

## State
- Train Pi: installed build `563b63f`, agent hash 0a7cf856 (matches the host). 600 s run: p99 2.55 ms, max 5.21 ms, 0 over 10 ms, 0 slow steps.
- Done: TrainCore no deepcopy (rollback test), journal handle kept open, checkpoint swap off the reply path, journal thread + queue (MAX_UNSYNCED 300),
  governor `performance` (pinning A/B: no difference, so no pinning), Nice/PYTHONOPTIMIZE, install.sh restart, slow-step log, bringup p99/progress/connected line/`rtt_over_10ms`,
  render check and frame caps (Phase 3 code), lean Track checkpoint (compiled programs rebuilt on restore; 459 KB -> 66 KB, 6 ms -> 1 ms in the sandbox).
- Measured: all rows are in `documents/pi_hw_results/10x-log.md`. `measure --system --test-pi process` at 1x/10x: 0 slipped; 10x p95 about 13 ms vs a 10 ms budget.
  Per-module at 10x: track-controller-hw is last to reply in 91% of ticks (mean 6.1 ms in the sandbox).
- Host pacing tops out near 92 Hz, not 100.

## Not done
- Track Pi on hardware: never run. Install `track-pi.tar.gz`, `bringup --list`, then `bringup --module track-controller-hw --recording ..\track-red-180s.jsonl --hz 100 --timeout 300`.
  This is the run that exercises the lean checkpoint and the 3 ms PLC step.
- 600 s run with every window open; GPU/WARP check and the `QSG_INFO=1` adapter line (needs the target machine); `measure --system` against real Pis.
- Original-versus-now comparison on the Pi (build the `e3077ae` bundle).
- PLC step cost (`plc.py`, owned by someone else, untouched).
- Any train on Green or Red on the HW Pi: the source still routes Red only (`common/harness/edges.py`); a Green-train replay test exists.
- Final report: branch name, the 10x-log.md table, README section-5 items done/not done, anything surprising.

## Known test state
- `common/hw_link`: 229 passed, plus 2 `test_bundle_is_offline_stdlib_and_shell_parses` that need physical Pis (ignore).
- `common/harness/tests`: 7 fail on this branch and on `main` alike (unrelated, not investigated).

## Rules in force
No push, no merge, no repo changes in the user's repo; rebuild both bundles after every source change (`python -m common.hw_link.provision --module <m> --output <file>`);
`sync` on the Pi before unplug; no config.txt edit or reboot without telling the user; ask before any wire-protocol change; one change at a time with before/after rows in `10x-log.md`.
