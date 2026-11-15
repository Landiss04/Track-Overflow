# Track Controller Pi: install and run, step by step

**Status:** a runbook written from the commands that worked on this branch. Every command was run on the real board except where a step says "not run". If a result differs from what a step says to expect, stop there and see "If something goes wrong" at the end.

The same board runs either the Track Controller or the Train Controller, one at a time. For the Train Controller use `guide-train-controller-pi.md`. The menu `bench\pi_test_menu.cmd` runs the tests below from a numbered list once the Pi is installed.

**What you need**

- A Raspberry Pi 5 with Raspberry Pi OS, reachable over SSH, connected to the Windows host's USB-C port with a **data** cable (the host port also powers it).
- The Windows host with the Python that has PySide6 installed, and this repository checked out at the commit you are testing. Open PowerShell in the repository root (`Track-Overflow`).
- A folder next to the repository for results, `..\trains_pi` (the menu and the commands below write there). Create it once: `mkdir ..\trains_pi`.
- The recordings used by the replay tests, in `..\trains_pi`: `track-red-180s.jsonl` (the Track Controller's recorded Red workload). They are not in the repository.

**Three rules that prevent most trouble**

1. Run `sync` on the Pi before every unplug or reboot, and paste Pi commands one line at a time when one uses `sudo`.
2. Exactly one agent may run on the Pi. Two agents on the same USB device split the bytes and every result is invalid.
3. The host and the Pi bundle must come from the same commit. The host refuses a Pi whose agent hash differs (`bundle hash mismatch`).

---

## Part 1. Build the Track bundle (Windows host)

```powershell
git status
```
It should say the working tree is clean. Then build, and note the `sha256` it prints:
```powershell
python -m common.hw_link.provision --module track-controller-hw --output ..\track-pi.tar.gz
```
```powershell
tar -tzf ..\track-pi.tar.gz | Select-String '\\'
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
Save with Ctrl+O, Enter, Ctrl+X. The reboot in step 2.8 applies it.

### Every install

1. Copy `track-pi.tar.gz` to `~/Downloads` on the Pi (VS Code remote upload, or `scp ..\track-pi.tar.gz <user>@<pi-address>:~/Downloads/`).
2. Check it is the file you built:
```sh
sha256sum ~/Downloads/track-pi.tar.gz
```
It must equal the `sha256` from Part 1. If not, upload again.
3. If the board last ran the **Train** Controller, stop its agent and move its journal and log aside, otherwise the Track agent refuses the journal (`journal module mismatch`) and the service restarts in a loop:
```sh
sudo systemctl stop track-overflow-agent
```
```sh
sudo mkdir -p /var/lib/track-overflow/old-train && sudo sh -c 'mv /var/lib/track-overflow/session.json* /var/lib/track-overflow/agent.log /var/lib/track-overflow/old-train/ 2>/dev/null'; ls /var/lib/track-overflow/
```
4. Unpack into a fresh folder and install:
```sh
rm -rf ~/Documents/track-install && mkdir -p ~/Documents/track-install && tar xzf ~/Downloads/track-pi.tar.gz -C ~/Documents/track-install
```
```sh
cd ~/Documents/track-install && sudo ./install.sh
```
Every line should end in `: OK`. The script's last three lines are a reminder about the overlay; it does not change `config.txt`.
5. Check the service will start the Track module:
```sh
grep -- "--module" /etc/systemd/system/track-overflow-agent.service
```
It must say `--module track-controller-hw`.
6. `sync`
7. If the board **last ran the Train Controller, reboot**: the USB gadget is created at boot, and it refuses to change its identity while it exists ("Existing gadget; reboot before identity change"). After the first install ever, a reboot is also needed for the overlay.
```sh
sudo reboot
```
8. After it is back, check there is exactly one agent, and that it runs the code you installed:
```sh
pgrep -af "hw_link.agent|agent.py"
```
It must show one line with `--module track-controller-hw`.
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
The Track controller must say `status: found` with a COM port, and the Train controller `missing` (the other board is not connected).
```powershell
python -m common.hw_link.bringup --module track-controller-hw --timeout 20 --output ..\trains_pi\track-hello.json
```
It must finish with `"error": null`.

## Part 4. The tests

Always do these first, before **every** measured run:

- Restart the agent and start with a fresh journal. A Track core runs a little slower in each later session of the same agent process, so a run you want to compare must start from a fresh process:
```sh
sudo systemctl stop track-overflow-agent
```
```sh
sudo mkdir -p /var/lib/track-overflow/old-track && sudo sh -c 'mv /var/lib/track-overflow/session.json* /var/lib/track-overflow/agent.log /var/lib/track-overflow/old-track/ 2>/dev/null'
```
```sh
sudo systemctl start track-overflow-agent
```
- Check `pgrep -af "hw_link.agent|agent.py"` shows exactly one agent.
- On the host, check no Python is left over from an earlier run: `Get-Process python -ErrorAction SilentlyContinue` prints nothing.
- **Turn off Windows clipboard history** (Settings, System, Clipboard), copy nothing from a minute before the run until it ends, and keep other programs closed. A run that starts with `qt.qpa.mime: ... clipboard` lines stalls several modules at once and loses about 0.45x of speed.

### Test A. Replay on the link (180 s)

Replays the recorded Red workload at 100 steps a second (the 10x rate) through the same host transport and framing the system uses:
```powershell
python -m common.hw_link.bringup --module track-controller-hw --recording ..\trains_pi\track-red-180s.jsonl --hz 100 --timeout 300 --output ..\trains_pi\replay-track.json
```
Expect `"error": null`, the round-trip percentiles, `lines_lost` (damaged lines the probe skipped or resent; 0 to 3% of the display lines is seen) and `rtt_over_10ms`. A damaged display line (VIEW) is skipped and counted, as the host relay does. Add `--strict` only for link tests that must stop at the first damaged line.

### Test B. The whole system at 10x with the Track Pi real

The Train Controller is simulated on the host (`--train-controller-pi process`). **Always give the other Pi's mode explicitly**: without it the harness treats both Pis as real and waits forever for the one that is not connected (the clock stays at 05:00:00).

60 s check first:
```powershell
python bench\per_module.py --system --track-controller-pi physical --train-controller-pi process --schedule utils\schedule_stress.json --seconds 60 --per-tick-csv ..\trains_pi\tick-track-physical-60s.csv
```
Then the 600 s run (about 10 minutes, hands off):
```powershell
python bench\per_module.py --system --track-controller-pi physical --train-controller-pi process --schedule utils\schedule_stress.json --seconds 600 --per-tick-csv ..\trains_pi\tick-track-physical-600s.csv
```
Summarise it:
```powershell
python bench\tickstats.py ..\trains_pi\tick-track-physical-600s.csv
```
What the numbers mean: `speed achieved` is 10.00x when every tick fits in its 10 ms slot; `ticks slipped` counts ticks the harness fell behind; the table lists each module's reply time from the tick start, and the last column how often it was the last to reply. The Track Controller is the slowest module in about 97% of ticks, so its reply mean decides the speed (under 10 ms is needed for 10x).

The last results measured on this branch: 8.45x before the PLC change, 9.99x with it (host quiet), see `10x-log.md`.

### Test C. All simulated (no Pi), the baseline for comparison

```powershell
python bench\per_module.py --system --test-pi process --schedule utils\schedule_stress.json --seconds 600 --per-tick-csv ..\trains_pi\tick-sim-600s.csv
```
Expect 10.00x on this branch. The difference from Test B is the Pi's cost.

### After every run (on the Pi)

```sh
grep -c SLOW_STEP /var/lib/track-overflow/agent.log
```
The number of steps that took the Pi more than 10 ms (a few at startup is normal).
```sh
vcgencmd get_throttled
```
`throttled=0x0` means no undervoltage or throttling since boot.

## Part 5. Switching the board to the Train Controller

Follow `guide-train-controller-pi.md` Part 2, step 3 onwards: stop the agent, move this agent's journal and log aside (to `old-track`), unpack the Train bundle, install, `sync`, **reboot**.

## If something goes wrong

| What you see | Cause | Fix |
| --- | --- | --- |
| The clock sits at 05:00:00 and nothing moves | The harness waits for a module that is not ready, almost always the other Pi mode was left out | Add `--train-controller-pi process` to the command |
| `Waiting for the assigned USB Pi(s): ...` | A Pi named there is not connected | Check `bringup --list`, the cable and `pgrep` on the Pi, or simulate it |
| `HELLO ... bundle hash mismatch` | Pi bundle and host checkout are from different commits | Rebuild (Part 1) from the current checkout and reinstall (Part 2) |
| `bringup --list` shows `missing` | Charge-only cable, gadget not running, or the board still shows the other module | Use a data cable; `systemctl status track-overflow-gadget`; reboot after switching module |
| Agent restarts in a loop, journal says `journal module mismatch` | The Pi last ran the other module | Part 2 step 3, then `sudo systemctl reset-failed track-overflow-agent` and start it |
| Round trips fail at random, HELLO answers but the next line gets no reply | Two agents on the USB device | `pgrep -af "hw_link.agent"`; stop the service before starting any other agent |
| A run starts with `qt.qpa.mime: ... clipboard` lines | Something is using the Windows clipboard; the Qt modules wait for it | Part 4: clipboard history off, copy nothing; repeat the run |
| Ctrl+C does not stop a run | The harness process is busy | `Get-Process python -ErrorAction SilentlyContinue \| Stop-Process -Force` (this stops every Python on the host) |
| Replays after the first are slower | Track core slows with each new session in one agent process (cause not found) | Restart the agent with a fresh journal before a run you will compare |

More causes and the full history: `pi_setup_how_to.md` (troubleshooting) and `10x-log.md`.
