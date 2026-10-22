# Pi bring-up: measurements and recovery checks

**Status:** 2026-10-22. Commands use the shared production `common.hw_link`
agent/transports and `common.harness.measure`; no alternate harness or
protocol implementation is supplied. Process and Linux pty results are
software evidence only. Real Pi USB timings and cold boot remain untested.

## Link echo, independent of core timing

Stop the normal agent on the board and run the same agent explicitly in
isolated echo-test mode, substituting the module on the Train Pi:

```sh
sudo systemctl stop track-overflow-agent.service
cd /opt/track-overflow
sudo -u trackoverflow /usr/bin/python3 -m common.hw_link.agent --module track-controller-hw --device /dev/ttyGS0 --journal /tmp/track-echo.jsonl --echo-test
```

On the host, run each payload size at 100 requests/second:

```sh
python -m common.hw_link.bringup --module track-controller-hw --echo-bytes 1024 --count 1000 --hz 100 --output /tmp/echo-1k.json
python -m common.hw_link.bringup --module track-controller-hw --echo-bytes 10240 --count 1000 --hz 100 --output /tmp/echo-10k.json
python -m common.hw_link.bringup --module track-controller-hw --echo-bytes 20480 --count 1000 --hz 100 --output /tmp/echo-20k.json
```

Repeat for `train-controller-hw`. Payload sizes are 1/10/20 KiB of ASCII,
excluding the envelope. The opt-in agent reflects a HELLO `echo` field;
normal mode does not reflect it. There is no new operation or clock. Each
reply must match the complete payload and request identity. The probe is
paced, with one outstanding request; RTT above 10 ms lowers achieved rate
instead of silently piling up requests. `late_sends` counts sends more than
1 ms behind their scheduled deadline. Report actual wire bytes, elapsed
time and RTT mean/p95/max; do not infer 100 Hz from the requested rate alone.
Terminate the foreground echo agent and restart the normal service afterward:

```sh
sudo systemctl start track-overflow-agent.service
```

For software-only checks add `--transport process` or `--transport pty` on
Linux. Those modes start the existing agent with `--echo-test` automatically.
They never stand in for serial mode without the explicit option.

## Recorded Red workload and agent step timing

Preserve each existing agent journal from a mixed Green/Red run. HW host
`--pi-log /tmp/track-pi.jsonl` also writes
`/tmp/track-pi.agent.jsonl`; the Train host uses the analogous path. Existing
`common/harness/tests/test_harness_hw_system.py::run_hw_system` produces these
logs while loading the canonical Red test territories/programs and dispatching
R1 to 16. Do not substitute empty inputs for a representative workload.

```sh
python -m common.hw_link.bringup --module track-controller-hw --recording /tmp/track-pi.agent.jsonl --hz 100 --output /tmp/track-core.json
python -m common.hw_link.bringup --module train-controller-hw --recording /tmp/train-pi.agent.jsonl --hz 100 --output /tmp/train-core.json
```

Run these against isolated agents: each probe creates a fresh session, which
resets the core/journal session. The tool preserves the journal's ordered
ACTION loads/gains and exact STEP payloads/IDs. It rejects failed requests,
reports core step mean/p95/max from existing OUTPUTS metrics and RTT including
transport, encoding and durable journal fsync. Core timing excludes those
other costs. VIEW traffic is counted in reply bytes. Add `--transport process`
or `--transport pty` for the same recorded workload in simulation.

## Full system, same measurement entry point

With both normally configured Pis connected and no isolated probe holding a
port, run the existing measurement tool (no `--test-pi`):

```sh
python -m common.harness.measure --system --speed 1 --seconds 15
python -m common.harness.measure --system --speed 10 --seconds 15
python -m common.harness.measure --system --speed 10 --seconds 15 --window
```

For simulations add `--test-pi process` or, on Linux, `--test-pi pty`.
Keep measurements sequential on an otherwise idle host. Use the Phase 4/5
comparison shape, including these columns:

| Host/Pi revision and hash | Link | Speed/window | Startup s | RTT mean/p95/max ms | Effective speed | Slipped ticks | Per-module bytes/tick | Core step mean/p95/max ms |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| pending hardware | USB CDC-ACM | 1x/headless | pending | pending | pending | pending | pending | pending |
| pending hardware | USB CDC-ACM | 10x/headless | pending | pending | pending | pending | pending | pending |
| pending hardware | USB CDC-ACM | 10x/window | pending | pending | pending | pending | pending | pending |

Keep isolated echo/core results alongside full system results: they answer
different cost questions. Use whole-system means and achieved speed for the
10 ms budget assessment, not just the isolated core scan.

## Scripted simulated faults

The development command reuses existing acceptance tests and launch helpers:

```sh
python -m common.hw_link.faultcheck --scenario all
```

It requires the project's pytest/Qt environment. Select `reboot-drop`, `pty`,
`gains` or `missing` to run one group. `reboot-drop` runs the existing seven
real-module processes with the agent's post-journal exit injection: both
reboot-at-tick and drop-after cases must produce one `REPLY_LATE`, followed
by `LATE_REPLY_RECEIVED`, naming Track Controller HW. The pending tick occurs
once in its durable journal; replay is a cache hit; both trains finish their
outbound route; all seven processes exit zero with empty stderr.

`pty` closes the actual raw pty pair mid-frame and replaces the stable gadget
pathname with a new pty; HELLO resumes the same boot/session and a repeated
STEP returns the identical cached reply. `gains` checks running and paused
losses, reboot reconstruction and same-boot reconnection: gains are resent
after running loss; paused reboot waits for the engineer; paused unplug
does not auto-apply gains. `missing` checks named identity diagnostics,
missing/ambiguous matches, and no automatic fallback or readiness.

## Real board fault checklist (pending)

1. Start a mixed G1/R1 run, record both journals, event logs and HELLO hashes.
2. While running, `sudo systemctl kill --signal=SIGKILL track-overflow-agent.service`.
   Its restart policy must restart the agent. Confirm the missing module is
   named, clock holds, pending reply completes once, and gains are resent.
   If restart/recovery takes less than the one second late threshold, inject
   a longer controlled outage to demonstrate the late events explicitly.
3. Stop the service for over one second, then start it. Confirm
   `REPLY_LATE` precedes `LATE_REPLY_RECEIVED` for that module and each STEP
   tick appears only once in the durable journal. Repeat for each board.
4. Unplug/replug the USB data cable and reboot each board independently.
   Confirm rediscovery by identity despite COM/path changes, HELLO hash,
   loads replay, cache replay and no duplicate step. Record power stability.
5. Repeat running loss and paused loss for Train Controller HW. Compare
   `GAINS_RESENT`, `GAINS_WAIT_ENGINEER` or `GAINS_NOT_RESENT` to the actual
   loss state, including loss between ticks. A paused reboot requires the
   engineer to reapply gains before movement.
6. Launch with one board absent, then with duplicate identity candidates.
   The clock must wait and the events must identify the missing/ambiguous
   module, expected serial and VID/PID. No simulation fallback is allowed.

These commands and checks are prepared; none establishes real Pi, Windows,
USB power-loss durability or cold-boot timing without hardware execution.

## Software evidence from this session

On 2026-10-22, each combination below completed 100 payload-checked echo
transactions at a requested 100 Hz with no error. These are short diagnostic
samples, not a hardware throughput qualification or an idle-host benchmark.
Mean/p95/maximum are in milliseconds; 1/10/20 KiB exclude envelopes.

| Link | Payload KiB | Track mean/p95/max ms | Train mean/p95/max ms |
| --- | --- | --- | --- |
| process | 1 | 0.276 / 0.449 / 0.660 | 0.326 / 0.531 / 0.698 |
| process | 10 | 0.462 / 0.632 / 0.924 | 0.382 / 0.662 / 0.997 |
| process | 20 | 0.597 / 0.869 / 1.041 | 0.654 / 0.873 / 1.241 |
| pty | 1 | 0.343 / 0.527 / 0.905 | 0.315 / 0.496 / 0.652 |
| pty | 10 | 0.710 / 1.609 / 1.867 | 0.984 / 1.750 / 1.819 |
| pty | 20 | 1.909 / 2.111 / 3.077 | 2.096 / 3.141 / 3.335 |

Eleven focused tooling tests pass locally: both offline bundles launch with
`python -S` (no site packages), checksums verify and generated shell parses;
echo and recorded-frame CLI paths run through process and pty; source hash
changes when either core or protocol changes; wrong HELLO hash/version is
refused; both missing/ambiguous identities are named; generated USB fields follow
the shared identity table for both modules. The full Pi/recovery
suites and recorded Red workload results are reported by the session handover.
These checks do not install systemd/configfs services or exercise real USB.

The recorded mixed Red outbound journal from the existing seven-process
fault acceptance run was replayed through both development transports. Each
case contains 658 STEP requests; Track includes six territory/program loads
(664 total transactions), Train includes the engineer-gains action (659 total).
All replies matched identity and none was rejected. These sequential diagnostic
runs include durable journal writes and were not isolated from all other
session work. RTT statistics include ACTIONs; core statistics contain STEP
metrics only. Original journals and JSON reports were retained for this session
under `/tmp/pi-bringup-evidence/` (temporary evidence, not shipped fixtures).

| Module | Link | RTT mean/p95/max ms | Core mean/p95/max ms |
| --- | --- | --- | --- |
| track-controller-hw | process | 4.160 / 5.154 / 18.338 | 2.098 / 2.665 / 2.918 |
| track-controller-hw | pty | 3.092 / 4.482 / 9.219 | 1.429 / 2.296 / 2.804 |
| train-controller-hw | process | 0.639 / 0.938 / 1.318 | 0.146 / 0.210 / 0.307 |
| train-controller-hw | pty | 0.610 / 0.861 / 1.091 | 0.118 / 0.183 / 0.302 |
