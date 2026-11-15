# Train Controller Pi: install and run, step by step

**Status:** a runbook written from the commands that worked on this branch. The Train bundle was run on the real board at an earlier commit; the Train bundle built at the head `33160a8` was also run on the board (10.00x, see Test C); the agent hash changed with the PLC change, so the host and the Pi must both be at the same commit. If a result differs from what a step says to expect, stop there and see "If something goes wrong" at the end.

The same board runs either the Train Controller or the Track Controller, one at a time. For the Track Controller use `guide-track-controller-pi.md`. The menu `bench\pi_test_menu.cmd` runs the tests below from a numbered list once the Pi is installed.

**What you need**

- A Raspberry Pi 5 with Raspberry Pi OS, reachable over SSH, connected to the Windows host's USB-C port with a **data** cable (the host port also powers it).
- The Windows host with the Python that has PySide6 installed, and this repository checked out at the commit you are testing. Open PowerShell in the repository root (`Track-Overflow`).
- A folder next to the repository for results, `..\trains_pi`. Create it once: `mkdir ..\trains_pi`.
- The recording used by the replay test: `bench\recordings\train-red-600s.jsonl.gz` is in the repository (see `bench\recordings\README.md`). `bringup` reads only unpacked files, so unpack it into `..\trains_pi` first; the menu does this for you the first time, or use the command in that README.

**Three rules that prevent most trouble**

1. Run `sync` on the Pi before every unplug or reboot, and paste Pi commands one line at a time when one uses `sudo`.
2. Exactly one agent may run on the Pi. Two agents on the same USB device split the bytes and every result is invalid.
3. The host and the Pi bundle must come from the same commit. The host refuses a Pi whose agent hash differs (`bundle hash mismatch`).

---

## Part 1. Build the Train bundle (Windows host)

```powershell
git status
```
It should say the working tree is clean. Then build, and note the `sha256` it prints:
```powershell
python -m common.hw_link.provision --module train-controller-hw --output ..\train-pi.tar.gz
```
```powershell
tar -tzf ..\train-pi.tar.gz | Select-String '\\'
```
The second command must print nothing (no Windows-style paths). Rebuild the bundle whenever any source file changes. Each build has a different sha256 (the archive records times), so always compare against the one you just built.

## Part 2. Install on the Pi

### First time only: the USB gadget overlay

```sh
sudo nano /boot/firmware/config.txt
```
Under `[all]` the file must contain exactly this line (a stray letter on it once stopped the board from appearing):
```ini
dtoverlay=dwc2,dr_mode=peripheral
```
Save with Ctrl+O, Enter, Ctrl+X. The reboot in step 7 applies it.

### Every install

1. Copy `train-pi.tar.gz` to `~/Downloads` on the Pi (VS Code remote upload, or `scp ..\train-pi.tar.gz <user>@<pi-address>:~/Downloads/`).
2. Check it is the file you built:
```sh
sha256sum ~/Downloads/train-pi.tar.gz
```
It must equal the `sha256` from Part 1. If not, upload again.
3. If the board last ran the **Track** Controller, stop its agent and move its journal and log aside, otherwise the Train agent refuses the journal (`journal module mismatch`) and the service restarts in a loop:
```sh
sudo systemctl stop track-overflow-agent
```
```sh
sudo mkdir -p /var/lib/track-overflow/old-track && sudo sh -c 'mv /var/lib/track-overflow/session.json* /var/lib/track-overflow/agent.log /var/lib/track-overflow/old-track/ 2>/dev/null'; ls /var/lib/track-overflow/
```
4. Unpack into a fresh folder and install:
```sh
rm -rf ~/Documents/train-install && mkdir -p ~/Documents/train-install && tar xzf ~/Downloads/train-pi.tar.gz -C ~/Documents/train-install
```
```sh
cd ~/Documents/train-install && sudo ./install.sh
```
Every line should end in `: OK`. The script's last three lines are a reminder about the overlay; it does not change `config.txt`.
5. Check the service will start the Train module:
```sh
grep -- "--module" /etc/systemd/system/track-overflow-agent.service
```
It must say `--module train-controller-hw`.
6. `sync`
7. If the board **last ran the Track Controller, reboot**: the USB gadget is created at boot, and it refuses to change its identity while it exists ("Existing gadget; reboot before identity change"). After the first install ever, a reboot is also needed for the overlay.
```sh
sudo reboot
```
8. After it is back, check there is exactly one agent, and that it runs the code you installed:
```sh
pgrep -af "hw_link.agent|agent.py"
```
It must show one line with `--module train-controller-hw`.
```sh
cd /opt/track-overflow && python3 -c "from common.hw_link import agent; print(agent.AGENT_HASH[:8])"
```
The host computes the same hash from its checkout:
```powershell
python -c "from common.hw_link import agent; print(agent.AGENT_HASH[:8])"
```
The two must match.

## Part 3. Check the link (Windows host)

```powershell
python -m common.hw_link.bringup --list
```
The Train controller must say `status: found` with a COM port, and the Track controller `missing` (the other board is not connected).
```powershell
python -m common.hw_link.bringup --module train-controller-hw --timeout 20 --output ..\trains_pi\train-hello.json
```
It must finish with `"error": null`.

## Part 4. The tests

Before **every** measured run:

- Restart the agent with a fresh journal:
```sh
sudo systemctl stop track-overflow-agent
```
```sh
sudo mkdir -p /var/lib/track-overflow/old-train && sudo sh -c 'mv /var/lib/track-overflow/session.json* /var/lib/track-overflow/agent.log /var/lib/track-overflow/old-train/ 2>/dev/null'
```
```sh
sudo systemctl start track-overflow-agent
```
- Check `pgrep -af "hw_link.agent|agent.py"` shows exactly one agent.
- On the host, check no Python is left over: `Get-Process python -ErrorAction SilentlyContinue` prints nothing.
- **Turn off Windows clipboard history** (Settings, System, Clipboard), copy nothing from a minute before the run until it ends, and keep other programs closed. A run that starts with `qt.qpa.mime: ... clipboard` lines stalls several modules at once and loses speed.

### Test A. Link echo (optional, shows the raw link)

Stop the normal agent and run the echo agent on the Pi in the foreground, leaving that terminal open:
```sh
sudo systemctl stop track-overflow-agent
```
```sh
cd /opt/track-overflow && sudo -u trackoverflow /usr/bin/python3 -m common.hw_link.agent --module train-controller-hw --device /dev/ttyGS0 --journal /tmp/train-echo.jsonl --echo-test
```
On the host, one size at a time (1, 10 and 20 KiB):
```powershell
python -m common.hw_link.bringup --module train-controller-hw --echo-bytes 10240 --count 1000 --hz 100 --strict --output ..\trains_pi\echo-train-10k.json
```
Each must end `"samples": 1000` and `"error": null`. Then press Ctrl+C in the Pi terminal and start the normal agent again (`sudo systemctl start track-overflow-agent`).

### Test B. Replay on the link (600 s)

```powershell
python -m common.hw_link.bringup --module train-controller-hw --recording ..\trains_pi\train-red-600s.jsonl --hz 100 --timeout 700 --output ..\trains_pi\replay-train.json
```
Expect `"error": null`, round-trip p99 about 2.5 ms and no round trip over 10 ms on this branch (see `10x-log.md`: the Train Pi was brought from p99 18 ms to 2.5 ms by moving the journal write off the reply path).

### Test C. The whole system at 10x with the Train Pi real

The Track Controller is simulated on the host (`--track-controller-pi process`). **Always give the other Pi's mode explicitly**: without it the harness treats both Pis as real and waits forever for the one that is not connected (the clock stays at 05:00:00).

60 s check first:
```powershell
python bench\per_module.py --system --track-controller-pi process --train-controller-pi physical --schedule utils\schedule_stress.json --seconds 60 --per-tick-csv ..\trains_pi\tick-train-physical-60s.csv
```
Then the 600 s run (about 10 minutes, hands off):
```powershell
python bench\per_module.py --system --track-controller-pi process --train-controller-pi physical --schedule utils\schedule_stress.json --seconds 600 --per-tick-csv ..\trains_pi\tick-train-physical-600s.csv
```
Summarise it:
```powershell
python bench\tickstats.py ..\trains_pi\tick-train-physical-600s.csv
```
`speed achieved` is 10.00x when every tick fits its 10 ms slot. The real Train Pi adds about 2 ms to its own reply (3.6 to 5.8 ms) and is rarely the slowest module, so it does not limit the system. The last Train-Pi system run on this branch (current code, clean host, Track Controller simulated) was **10.00x** with no slipped ticks, a Train Pi reply mean of 4.5 ms (p99 11 ms) and no slow steps on the Pi; an earlier run of older code on a noisier host was 7.60x. The result is mostly set by the simulated Track Controller and the host's noise, not the Train Pi (`10x-log.md`).

### Test D. Both Pis real, estimated

There is one board, so both Pis real at once is an estimate from one run each:
```powershell
python bench\estimate_both.py --train-physical ..\trains_pi\tick-train-physical-600s.csv --track-physical ..\trains_pi\tick-track-physical-600s.csv
```

### After every run (on the Pi)

```sh
grep -c SLOW_STEP /var/lib/track-overflow/agent.log
```
```sh
vcgencmd get_throttled
```
`throttled=0x0` means no undervoltage or throttling since boot.

## Part 5. Switching the board to the Track Controller

Follow `guide-track-controller-pi.md` Part 2, step 3 onwards: stop the agent, move this agent's journal and log aside (to `old-train`), unpack the Track bundle, install, `sync`, **reboot**.

## If something goes wrong

| What you see | Cause | Fix |
| --- | --- | --- |
| The clock sits at 05:00:00 and nothing moves | The harness waits for a module that is not ready, almost always the other Pi mode was left out | Add `--track-controller-pi process` to the command |
| `Waiting for the assigned USB Pi(s): ...` | A Pi named there is not connected | Check `bringup --list`, the cable and `pgrep` on the Pi, or simulate it |
| `HELLO ... bundle hash mismatch` | Pi bundle and host checkout are from different commits | Rebuild (Part 1) from the current checkout and reinstall (Part 2) |
| `bringup --list` shows `missing` | Charge-only cable, gadget not running, or the board still shows the other module | Use a data cable; `systemctl status track-overflow-gadget`; reboot after switching module |
| Agent restarts in a loop, journal says `journal module mismatch` | The Pi last ran the other module | Part 2 step 3, then `sudo systemctl reset-failed track-overflow-agent` and start it |
| Echo fails at once with `echo payload mismatch`, or fails at a random sample | The normal agent answered instead of the echo agent, or two agents are reading the USB device | `pgrep -af "hw_link.agent"`; stop the service before starting the echo agent |
| A run starts with `qt.qpa.mime: ... clipboard` lines | Something is using the Windows clipboard; the Qt modules wait for it | Part 4: clipboard history off, copy nothing; repeat the run |
| Ctrl+C does not stop a run | The harness process is busy | `Get-Process python -ErrorAction SilentlyContinue \| Stop-Process -Force` (this stops every Python on the host) |

More causes and the full history: `pi_setup_how_to.md` (troubleshooting) and `10x-log.md`.
