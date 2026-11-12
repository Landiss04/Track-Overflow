# Handoff: real-Pi test of the merged PR 56 branch on a faster laptop

Written 2026-11-12. Read `AGENTS.md` first; its rules apply. Nothing here is a normative fact
for the `truth` branch. These are test notes and observations only.

## 0. Goal
Repeat the 2026-11-12 tests on a faster PC to see whether it gets closer to **10x**. The old laptop (Ryzen 7 7730U) averaged **about 7x**, and the evidence points to the PC, not the Pi:
- The Pi's agent ran at about 15% CPU.
- Each round trip took about 12.5 ms, and 10x leaves only 10 ms per tick.

## 1. Exact code under test
- This branch, `handoff/pr56-faster-laptop-test`, is the merged head **`cbafba03641ab20e505f728c305397d6075a6c6a`** (`integrate/harness-into-development`) **plus only this notes file**.
- The Track Controller Pi runs the agent built from `cbafba0` (hash `c5ffae7d…`). This file is outside the Pi bundle, so the hash is unchanged. If you test a newer commit and any file in the bundle changed (`common/hw_link`, `utils`, `TrackCtrlHw/track_ctrl_hw`, `Train-Ctrl_HW/train_ctrl`), the harness will reject the Pi (`PI_HELLO_REJECTED`) until the agent is reinstalled.
- Use a **separate clone**, not your main working copy:

```powershell
git clone https://github.com/Landiss04/Track-Overflow.git C:\Dev\trains-test
git -C C:\Dev\trains-test checkout handoff/pr56-faster-laptop-test
```

## 2. Setup
- Python **3.14** (the old laptop used 3.14.2) and `requirements.txt` (PySide6 6.11.2, pyinstaller 6.22.2):

```powershell
Set-Location C:\Dev\trains-test; py -3.14 -m venv .venv; .\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

- Check the hash the code expects. It must print `c5ffae7df449107e20eab848d06cce4287e190066068e230530ec90129f851ec`:

```powershell
.\.venv\Scripts\python.exe -c "from common.hw_link.manifest import expected_hash; print(expected_hash())"
```

- **Power:** plugged into mains, with Windows power mode set to **Best performance**.

```powershell
(Get-CimInstance -Namespace root/wmi BatteryStatus).PowerOnline   # should print True
powercfg /overlaysetactive ded574b5-45a0-4f42-8737-46345c09c238  # sets Best performance
```

  The command to read the mode back fails on some Windows builds; that doesn't matter.

## 3. Pi hardware
- **Track Controller Pi** (Pi 5): USB-C to the PC. On the old laptop it was on a mains-powered USB 3.0 hub.
  - The harness finds it by USB serial `TO-TRACK-CTRL-HW-01`, so the COM port number doesn't matter.
  - Agent hash: `c5ffae7df449107e20eab848d06cce4287e190066068e230530ec90129f851ec`.
  - SSH: `brade@192.168.1.16` on the home network, or Tailscale `track-pi` (100.83.179.34) if the laptop is on Braden's tailnet.
  - SSH is **optional**. It's only for health readings; the tests themselves need only the USB link.
- **Power warning:** booting the **second** Pi on the same hub dropped the Track Controller Pi's voltage for about 40 s (14:02:25–14:03:08). If you use a hub, boot both Pis first, or power the second Pi separately.
- **Train Controller Pi:** **not usable yet.** Its agent is an old build (`578597bf…`), so the harness rejects it. It needs the merged agent, which means SSH access: Ethernet to the router, or Wi-Fi. Get the Train Controller owner's OK before reinstalling it. Until then, use `--train-controller-pi process`. To install:

```powershell
.\.venv\Scripts\python.exe -m common.hw_link.provision --module train-controller-hw --output $env:TEMP\trainhw.tar.gz
# copy the archive to the Pi, then on the Pi: extract it and run `sudo ./install.sh` in the extracted folder
# sudo systemctl restart track-overflow-agent.service
# check the hash: cd /opt/track-overflow && python3 -c 'from common.hw_link.manifest import expected_hash; print(expected_hash())'
```

## 4. Pre-flight
1. Check the USB identities and the Pi's hash. The second command should report `hello_s` around 0.1 s with no error. Don't add `--echo-bytes`; the installed agent doesn't have the echo test enabled.

```powershell
.\.venv\Scripts\python.exe -m common.hw_link.bringup --list
.\.venv\Scripts\python.exe -m common.hw_link.bringup --module track-controller-hw --transport serial --count 50 --hz 100
```

2. Optional, with SSH: `vcgencmd get_throttled` should read `0x0`, or `0x50000` if the voltage has dropped since boot. Count drops with `journalctl -k -b | grep -c Undervoltage`.

## 5. Optional switch probe (logs request → command → track per switch)
This runs outside the repo and changes no files. Save it as `C:\probe\sitecustomize.py`:

```python
import os, sys, time
if sys.argv and sys.argv[0].endswith("track_overflow.py") and "--module" not in sys.argv:
    from common.harness import hw_wayside_edges as _hw
    _log = open(os.path.join(os.path.dirname(__file__), "route.log"), "a", encoding="utf-8", buffering=1)
    _t0, _last = time.monotonic(), {}
    def _note(kind, line, sw, value):
        if _last.get((kind, line, sw)) != value:
            _last[(kind, line, sw)] = value
            _log.write(f"{time.monotonic() - _t0:9.2f}s {kind:<8} {line:<5} sw{sw:<3} {value}\n")
    _o1, _o2, _o3 = _hw.ctc_to_track_controller, _hw.track_model_to_track_controller, _hw.track_controller_to_track_model
    def ctc_to_track_controller(outputs, line):
        r = _o1(outputs, line); seen = set()
        for e in r["route_requests"]:
            seen.add(e["switch_id"]); _note("REQUEST", e["line"], e["switch_id"], e["position"])
        for (k, ln, sw), v in list(_last.items()):
            if k == "REQUEST" and ln == line and sw not in seen and v is not None: _note("REQUEST", line, sw, None)
        return r
    def track_model_to_track_controller(outputs, line, names, devices):
        r = _o2(outputs, line, names, devices)
        for e in r["switch_positions"]: _note("TRACK", e["block"]["line"], e["block"]["block_id"], e["position"])
        return r
    def track_controller_to_track_model(outputs, names, devices):
        for e in outputs["track_model"]["switch_commands"]: _note("HW-CMD", e["block"]["line"], e["block"]["block_id"], e["position"])
        return _o3(outputs, names, devices)
    _hw.ctc_to_track_controller, _hw.track_model_to_track_controller, _hw.track_controller_to_track_model = ctc_to_track_controller, track_model_to_track_controller, track_controller_to_track_model
```

Turn it on before a run and off afterwards. Delete `route.log` between runs, because the probe appends to it.

```powershell
$env:PYTHONPATH = 'C:\probe;C:\Dev\trains-test'   # on
Remove-Item Env:PYTHONPATH                        # off
```

## 6. Tests (run them from `C:\Dev\trains-test`)

**A — Speed: PC alone, both Pis simulated, 4 min**
```powershell
.\.venv\Scripts\python.exe track_overflow.py --headless --test-pi process --speedup --load-starters --engineer-gains 400000 8000 --dispatch G1:Green:65 --dispatch R1:Red:3 --dispatch R2:Red:70 --run-seconds 240 --log-dir C:\probe\logs-A *> C:\probe\console-A.txt
```

**B — Speed with the real Pi, 4 min**
```powershell
.\.venv\Scripts\python.exe track_overflow.py --headless --speedup --load-starters --engineer-gains 400000 8000 --dispatch G1:Green:65 --dispatch R1:Red:3 --dispatch R2:Red:70 --track-controller-pi physical --train-controller-pi process --run-seconds 240 --log-dir C:\probe\logs-B *> C:\probe\console-B.txt
```

**C — Stability, 25 min (optional):** B with `--run-seconds 1500` and `-C` file names.

**D — Windowed (optional):** press Run in the CTC window, dispatch a Red train to block 3, set 10x, and watch switch 15.
```powershell
.\.venv\Scripts\python.exe track_overflow.py --load-starters --engineer-gains 400000 8000 --track-controller-pi physical --train-controller-pi process
```

**A vs B is the key comparison:**
- **A** fast but **B** about 7x → the Pi or its link is the limit.
- **Both** about 7x → the PC is still the limit.
- **Both** faster than the old laptop → the old laptop was the limit.

**Reading the results** (headless runs print a status line every few seconds):
```powershell
$c = Get-Content C:\probe\console-B.txt
$c | Select-String 'RUNNING' | Select-Object -Last 3        # "actual N.Nx", "round trip mean N ms"
($c | Select-String 'PI_SKIPPED_LINE').Count                 # damaged lines caught by the checksum
$c | Select-String 'REPLY_SLOW|PI_HELLO_REJECTED|Traceback'  # problems
$c | Select-Object -Last 1                                    # HARNESS_STOPPED ... all exit code 0
```

## 7. Baselines from 2026-11-12 (old laptop, mains power, Best performance)
| Run | Speed avg (range) | Round trip | Damaged lines | Other |
|---|---|---|---|---|
| Real Pi 4 min, about 3 min after a Pi reboot | 7.5x (6.1–8.4) | 11.1–13.0 ms | **38** | all exit 0 |
| Windowed, 38 min (about 4 min at 10x) | 7.5x (6.5–8.2) | — | 2 | 4 reverse requests followed in 20–30 ms |
| Real Pi 25 min | 7.05x (4.5–8.0) | 12.8 ms | 2 | 4 `REPLY_SLOW` (see §8) |
| Pi during the 25 min | agent 30.2 → 31.2 MB | journal cycles 0.4–7.9 MB | no new voltage drops | 52–59 °C |

## 8. Known behaviour, not regressions
- **Damaged lines cluster right after a Pi reboot** (38 in the first run, 2 per run later). The checksum catches each one and nothing is lost. The root cause is still open.
- **`REPLY_SLOW` on ticks that are multiples of 600** most likely comes from the agent's checkpoint write. It happened 2 times in about 175 checkpoints, and the clock keeps running.
- **Don't run heavy monitoring during a speed run.** A per-process WMI query (`Get-CimInstance Win32_Process` in a loop) cut the speed to 4.5x and coincided with a damaged line. Use Task Manager or `Get-Process` only.
- **Known failing tests, not from the merge:**
  - 3 harness tests that also fail on #57's tip: `test_green_follower` and `test_review_red_trains_go_out_together[2]` and `[3]`.
  - 7 that fail only because the PC runs Windows: `sha256sum`, `/tmp` paths, and a missing Qt font folder.
  - Kevin's 2 `ids=` errors.
  - 21 failing Train Controller HW tests. Run that suite with `$env:PYTHONPATH='<clone>\TrainModel;<clone>'`.
- The test runs rewrite two tracked files, `ui/__pycache__/aspect_lock.cpython-314.pyc` and `ui/__pycache__/theme.cpython-314.pyc`. Don't commit them.

## 9. PowerShell gotchas
- Chain commands with `;`, not `&&`.
- Avoid `\"` inside double-quoted strings.
- `>` writes UTF-16; use `*> file` or `| Out-File -Encoding utf8`.
- Git's progress messages show in red; that's not a failure.

## 10. Report back
Send Braden the **A** and **B** console files, plus the speed and round trip from `RUNNING` lines,
the `PI_SKIPPED_LINE` count, and any `REPLY_SLOW`, `PI_HELLO_REJECTED` or `Traceback` lines.
