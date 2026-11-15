# How to produce `results.md` for a Pi board

> Shorter step-by-step guides for installing and testing each board: `guide-track-controller-pi.md` and `guide-train-controller-pi.md`. `bench\pi_test_menu.cmd` runs the standard tests from a numbered menu. What this branch changed: `what-was-changed.md`.

A step-by-step runbook for building, installing and measuring one hardware Pi
(Train Controller HW or Track Controller HW) from a Windows host, then compiling
the measurements into `pi-results/results.md`.

Do the whole procedure once per board. Commands use the Train board; for the
Track board substitute as shown below.

| | Train Controller HW | Track Controller HW |
| --- | --- | --- |
| `<module>` | `train-controller-hw` | `track-controller-hw` |
| `<board>` | `train` | `track` |
| Bundle | `train-pi.tar.gz` | `track-pi.tar.gz` |

## 0. What you need

**Folder layout on Windows** (all inside your `trains` folder):

```
trains\
  Track-Overflow\           the repository; run every Windows command from here
  pi-results\               measurement JSON files and results.md
  compile_pi_results.py     builds results.md from pi-results
  train-pi.tar.gz           bundles, written by step 1
  track-pi.tar.gz
```

Create the results folder once: `mkdir ..\pi-results` (from `Track-Overflow`).

**Host:** Windows with the Python that has PySide6 installed (the one `bringup`
already runs with). Work from a committed revision: the results record it, and
the host and both bundles must come from the same source files.

**Pi:** Raspberry Pi 5 with Raspberry Pi OS, reachable over SSH (for example
`ssh <user>@<pi-address>`), connected to the laptop's USB-C port with a
**data** cable. The laptop port powers the board.

**Two rules that prevent most problems:**

- **Run `sync` on the Pi before every unplug.** Unplugging within a minute or so
  of writing files can leave them empty (0 bytes), and systemd then treats empty
  unit files as masked.
- **Paste Pi commands one line at a time** whenever one of them uses `sudo`.
  Lines pasted after a password prompt can be silently swallowed.

## 1. Build the bundles (Windows)

```powershell
git status                       # should be clean
python -m common.hw_link.provision --module train-controller-hw --output ..\train-pi.tar.gz
python -m common.hw_link.provision --module track-controller-hw --output ..\track-pi.tar.gz
tar -tzf ..\train-pi.tar.gz | Select-String '\\'
```

The last command must print **nothing** (no Windows backslash paths). Note the
`revision` and `sha256` each build prints. Rebuild whenever any source file
changes.

## 2. Install on the Pi

### First time only: boot overlay

```sh
sudo nano /boot/firmware/config.txt
```

Add at the end, then save (`Ctrl+O`, Enter, `Ctrl+X`):

```ini
[all]
dtoverlay=dwc2,dr_mode=peripheral
```

### Every install

Copy the bundle to the Pi's `~/Downloads` (VS Code Remote-SSH upload, or
`scp ..\train-pi.tar.gz <user>@<pi>:~/Downloads/` from Windows). Then on the
Pi, one line at a time:

```sh
sha256sum ~/Downloads/train-pi.tar.gz
```

It must match the `sha256` from step 1. If not, upload again.

```sh
mkdir -p ~/Documents/track-overflow-install && cd ~/Documents/track-overflow-install
```

```sh
rm -rf ./* && tar -xzf ~/Downloads/train-pi.tar.gz && wc -c install.sh
```

`install.sh` must be well above 0 bytes.

```sh
sudo ./install.sh
```

You should see `: OK` checksum lines and "Created symlink" messages. The script
ends with `sync`.

```sh
systemctl show track-overflow-gadget.service track-overflow-agent.service -p DefaultDependencies -p UnitFileState
```

Both units must show `DefaultDependencies=no` and `UnitFileState=enabled`.

**`install.sh` stops the agent but does not start it again.** Either reboot
(the first install needs one anyway for the overlay), or:

```sh
sudo systemctl start track-overflow-agent.service
```

## 3. Discovery and warm HELLO (Windows)

```powershell
python -m common.hw_link.bringup --list
python -m common.hw_link.bringup --module train-controller-hw --timeout 20 --output ..\pi-results\train-hello.json
```

`--list` must show the board as `found` on a COM port. The HELLO run must end
with `"error": null`.

## 4. Link echo tests

**Pi** - stop the normal agent and run the echo agent in the foreground. Leave
this terminal running:

```sh
sudo systemctl stop track-overflow-agent.service
```

```sh
cd /opt/track-overflow && sudo -u trackoverflow /usr/bin/python3 -m common.hw_link.agent --module train-controller-hw --device /dev/ttyGS0 --journal /tmp/train-echo.jsonl --echo-test
```

**Windows:**

```powershell
foreach ($kb in 1,10,20) {
  python -m common.hw_link.bringup --module train-controller-hw --echo-bytes ($kb*1024) --count 1000 --hz 100 --output "..\pi-results\echo-train-${kb}k.json"
}
```

All three must finish with `"samples": 1000` and `"error": null`. Each run
takes about 11 s. If one run is clearly slower than the others (the host was
busy), rerun just that size.

**Pi** - press `Ctrl+C`, then restore the normal agent:

```sh
sudo systemctl start track-overflow-agent.service
```

## 5. Cold boot (repeat 2-3 times)

1. **Pi:** `sync`
2. Unplug the Pi's USB cable from the laptop.
3. **Windows:** start the probe:

   ```powershell
   python -m common.hw_link.bringup --module train-controller-hw --timeout 90 --output ..\pi-results\train-coldboot.json
   ```

4. Plug the Pi in immediately. Note roughly how many seconds after starting the
   command you plugged in.
5. When the probe prints its result, reconnect over SSH and record the Pi's own
   boot timeline:

   ```sh
   uptime
   journalctl -b -o short-monotonic -u track-overflow-gadget.service -u track-overflow-agent.service --no-pager
   ```

   `uptime` should show `up 0 min`. Expected: gadget bound around 6 s and agent
   started around 7.7 s after kernel start.

Save each repeat to its own file: `train-coldboot-2.json`, `train-coldboot-3.json`.
Cold boot time = `hello_s` minus the plug-in delay; the target is under 20 s.

## 6. Environment details (Pi and Windows)

Collect these for the environment table:

```sh
vcgencmd get_throttled              # 0x0 means no undervoltage
grep PRETTY_NAME /etc/os-release    # OS (Raspberry Pi OS reports Debian)
uname -r                            # kernel
```

On Windows, run `winver` for the Windows version.

## 7. Compile `results.md` (Windows)

Move any debugging files out of `pi-results` first, so only final results are
compiled (the script reads every `*.json` in the folder):

```powershell
mkdir ..\pi-results\debug -ErrorAction SilentlyContinue
python ..\compile_pi_results.py ..\pi-results --out ..\pi-results\results.md
```

The script recognizes these file names:

| File name | Table |
| --- | --- |
| `echo-<board>-<N>k.json` | Link echo |
| `<board>-coldboot*.json` | Cold boot |
| `<board>-core.json` | Recorded Red workload |
| anything else, e.g. `<board>-hello.json` | HELLO |

It warns if the results come from more than one agent bundle hash, which means
files from different builds are mixed together.

## 8. Fill in by hand

The script cannot know these. **It regenerates the whole file each run**, so keep
your hand-written sections in a separate copy and paste them back after
recompiling.

- **Environment table:** Pi model, OS / kernel, source revision, cable and
  power, `get_throttled`, host OS.
- **Cold boot:** plug-in delays (or "not timed") and the Pi-side gadget and agent
  times from step 5.
- **Recorded Red workload / Full system:** results, or "Not run yet".
- **Notes and open issues:** anything found during the run.

## 9. Before a measured run

- **Exactly one agent on the Pi.** `pgrep -af "common.hw_link.agent"` must list one agent: the service (journal under
  `/var/lib/track-overflow`, no `--echo-test`) for a replay, or the foreground echo agent for a link test. Two agents on
  `/dev/ttyGS0` split the bytes between them and every result is invalid. `sudo systemctl stop track-overflow-agent.service`
  before starting an echo agent.
- **Restart the Track agent before a run you will compare.** Each new session in one agent process runs the Track core slower than the
  last (core step mean 4.7, 5.2, 5.6 ms in three 180 s replays; not seen on the Train core). A restart resets it:
  `sudo systemctl restart track-overflow-agent.service`. Cause not found; see `10x-log.md`.
- **Link tests use `--strict`, replays do not.** By default `bringup` acts as the host relay does: a damaged VIEW is skipped and counted
  (`views_lost`), any other damaged line or a missing reply is sent again (`resends`). `--strict` stops at the first damaged line, which a
  link test needs. Report `lines_lost` and `resends` next to every round-trip number.
- **After moving a Pi between modules**, move `/var/lib/track-overflow/session.json` and `agent.log` aside first (for example to
  `session.train.json`): the agent refuses a journal from another module and the service restarts in a loop.
- **Read `get_throttled` after the run** (`vcgencmd get_throttled`). The high bits are sticky since boot, so 0x0 covers the whole run.

## 10. The 10x system run with one physical Pi

One board, so one hardware Pi is real and the other runs as a local process simulator on the host (an explicit test mode, never an automatic
fallback). The hardware Pis only run Red, so the default single Green train leaves them idle. Use the stress schedule (`--schedule utils\schedule_stress.json`:
14 Green trains 45 s apart and 4 Red trains 90 s apart, each Red run ending at block 60 and then returning to the yard, D020), or a single Red train with
`--dispatch R1:Red:60`. `measure` gives the engineer's gains to both Train Controllers, as the launcher does, so a Red train does not wait for them (D024).
Run from `Track-Overflow`:

```powershell
# Run A: the Track Pi is real, the Train Controller is simulated
python bench\per_module.py --system --track-controller-pi physical --train-controller-pi process --schedule utils\schedule_stress.json --seconds 60 --per-tick-csv ..\trains_pi\tick-track-physical-60.csv
# Run B: the Train Pi is real, the Track Controller is simulated
python bench\per_module.py --system --track-controller-pi process --train-controller-pi physical --schedule utils\schedule_stress.json --seconds 60 --per-tick-csv ..\trains_pi\tick-train-physical-60.csv
```

Each prints the usual report (round trip, slipped ticks, late replies) and then each module's reply time and how often it was last to reply.
Run a 60 s check first, then `--seconds 600`. **Before each run** restart the agent and check there is exactly one (`pgrep -af "common.hw_link.agent"`),
since a Track core runs slower in each later session of one process. **After each run**, on the Pi: `sudo grep -c "SLOW_STEP\|SKIPPED_LINE" /var/lib/track-overflow/agent.log`
and `vcgencmd get_throttled`.

For a result with both Pis real, combine the two 600 s CSVs (an estimate, not a measurement of both together; it prints two variants):

```powershell
python bench\estimate_both.py --train-physical ..\trains_pi\tick-train-physical-600.csv --track-physical ..\trains_pi\tick-track-physical-600.csv
```

**Switching the board between modules needs a reboot.** The gadget script refuses to change a bound USB identity ("Existing gadget; reboot before identity change").
On the Pi: stop the agent, move the other module's journal and log aside, install the other bundle (steps 1 and 2), `sync`, reboot.

```sh
sudo systemctl stop track-overflow-agent.service
sudo mkdir -p /var/lib/track-overflow/old && sudo sh -c 'mv /var/lib/track-overflow/session.json* /var/lib/track-overflow/agent.log /var/lib/track-overflow/old/'
```

## Troubleshooting

| Symptom | Cause | Fix |
| --- | --- | --- |
| Echo fails at once with `echo payload mismatch`; reply about 1,078 bytes | The normal agent answered, not the echo agent | Stop the service and start the echo agent (step 4); rerun, since the failure overwrote the JSON |
| HELLO timeout right after an install | `install.sh` stopped the agent | `sudo systemctl start track-overflow-agent.service` |
| HELLO timeout although the board is up | An old probe process still holds the COM port | `Get-CimInstance Win32_Process -Filter "Name='python.exe'" \| Where-Object CommandLine -match 'hw_link.bringup' \| ForEach-Object { Stop-Process -Id $_.ProcessId }` |
| `HELLO ... bundle hash mismatch` | Pi bundle and host source differ | Rebuild (step 1) from the current source and reinstall (step 2) |
| Board never appears; units show `masked` | Unit files are empty after an unplug without `sync`, or a leftover mask link | `sudo rm -f /etc/systemd/system/track-overflow-gadget.service /etc/systemd/system/track-overflow-agent.service`, reinstall, `sync` |
| Files in the install folder are 0 bytes | The archive or extraction was cut off by an unplug or a partial upload | Check `sha256sum`, upload again, re-extract |
| Windows says "USB device not recognized" | Usually the gadget never started (see `masked` above) | Check `systemctl status track-overflow-gadget.service` on the Pi |
| `install.sh` prints nothing | `install.sh` is empty | Re-extract from a verified archive |
| Replay stops with `line checksum does not match` | A damaged line on the link (seen on VIEWs, about 41 KB) | Current `bringup` skips a damaged VIEW and resends anything else; use `--strict` only for link tests |
| Echo test fails at a random sample, or HELLO answers and the next line gets no reply | Two agents are reading `/dev/ttyGS0` | `pgrep -af "common.hw_link.agent"`; stop the service before starting an echo agent |
| Agent unit fails, journal says `journal module mismatch` | The Pi last ran the other module and its journal is still there | Move `/var/lib/track-overflow/session.json` and `agent.log` aside, then `systemctl reset-failed` and start the agent |
| Gadget works but the board is not found after a reboot | `config.txt` overlay line misspelled (`dr_mode=peripheralZ` was found once) | The line under `[all]` must read exactly `dtoverlay=dwc2,dr_mode=peripheral` |
| The second and later replays are slower than the first | Track core slows with each new session in one process (cause unknown) | Restart the agent before a run you will compare |
| Board shows the old module after installing the other bundle | The USB gadget is created at boot and not changed while it exists | Reboot after `install.sh` (and after moving the old journal aside) |
| `bringup --list` shows `missing` | Charge-only cable, or the gadget is not running | Use a data cable; check the gadget service and `ls /sys/class/udc` on the Pi |

To stop a running probe, close the terminal or use the `Stop-Process` command
above. `Ctrl+C` can leave it running in the background.
