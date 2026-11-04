# How to produce `results.md` for a Pi board

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
`ssh paperbird@<tailscale-ip>`), connected to the laptop's USB-C port with a
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
| `bringup --list` shows `missing` | Charge-only cable, or the gadget is not running | Use a data cable; check the gadget service and `ls /sys/class/udc` on the Pi |

To stop a running probe, close the terminal or use the `Stop-Process` command
above. `Ctrl+C` can leave it running in the background.
