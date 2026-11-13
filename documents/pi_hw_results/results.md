# Pi bring-up results

Generated 2026-11-04 16:52 from `pi-results` (5 result files), with hand-added notes.

## Environment

| Item | Track Controller HW | Train Controller HW |
| --- | --- | --- |
| Pi model | pending | Raspberry Pi 5 |
| OS / kernel | pending | Raspberry Pi OS (Debian 13 "trixie") / Linux 6.18.50+rpt-rpi-2712 |
| Source revision | pending | `1d53b5d` |
| Agent bundle hash | pending | `37fa5446d0fe…` |
| Cable / power | pending | Powered and connected through the laptop's USB-C port, USB-C data cable |
| `vcgencmd get_throttled` | pending | `0x0` (no undervoltage) |
| Host OS | Windows 11 26H2 (build 26300.9818), Python 3.14 | Windows 11 26H2 (build 26300.9818), Python 3.14 |

## HELLO (warm connect)

| File | Module | hello_s | Result |
| --- | --- | --- | --- |
| (console output, not saved to a file) | train-controller-hw | 0.044 | ok |

Warm connect to an already-booted board at revision `1d53b5d`: identity, version and bundle hash `37fa5446…` accepted. This measures connection latency only, not boot time.

## Cold boot

Cold boot = `hello_s` minus the delay between starting the probe and powering the board.

| File | Module | hello_s | Elapsed s | Plug-in delay s | Cold boot s | Result |
| --- | --- | --- | --- | --- | --- | --- |
| train-coldboot-2.json | train-controller-hw | 16.99 | 16.99 | not timed | < 17.0 | ok |
| train-coldboot.json | train-controller-hw | 13.93 | 13.93 | not timed | < 13.9 | ok |

Both runs meet the under-20 s target even before subtracting the plug-in delay. Pi side (seconds after kernel start): gadget bound at 6.0–6.3 s, agent started at 7.7–7.9 s. The spread in `hello_s` comes from the plug-in delay and Windows device setup, not from the Pi.

## Link echo (USB CDC-ACM)

Requested rate 100 Hz, one request outstanding. Bytes/request includes the HELLO exchange.

| Module | Payload KiB | Samples | Elapsed s | Achieved Hz | late_sends | RTT mean/p95/max ms | Bytes/request req/reply | Result |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| train-controller-hw | 1 | 1000 | 10.98 | 91.1 | 448 (45%) | 0.752 / 1.318 / 3.607 | 1,205 / 1,313 | ok |
| train-controller-hw | 10 | 1000 | 10.93 | 91.5 | 401 (40%) | 1.689 / 2.203 / 3.244 | 10,421 / 10,529 | ok |
| train-controller-hw | 20 | 1000 | 10.90 | 91.8 | 403 (40%) | 2.775 / 3.647 / 8.310 | 20,661 / 20,769 | ok |

Every round trip stayed under the 10 ms budget; the closest was the 20 KiB maximum at 8.3 ms.

## Recorded Red workload

_Not run yet: needs the recorded Green/Red agent journals._

## Full system

_Not run yet: needs both boards connected._

| Host/Pi revision and hash | Link | Speed/window | Startup s | RTT mean/p95/max ms | Effective speed | Slipped ticks | Per-module bytes/tick | Core step mean/p95/max ms |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| pending | USB CDC-ACM | 1x/headless | pending | pending | pending | pending | pending | pending |
| pending | USB CDC-ACM | 10x/headless | pending | pending | pending | pending | pending | pending |
| pending | USB CDC-ACM | 10x/window | pending | pending | pending | pending | pending | pending |

## Notes and open issues

- **Windows-built bundles had broken paths.** `manifest.py` produced backslash file names, so the core packages extracted as flat files on the Pi. Fixed with `as_posix()`.
- **20 KiB replies lost data on Windows.** The `usbser.sys` driver's default receive buffer overflowed and dropped whole 512-byte USB packets. strace showed the Pi sent every byte, and USBPcap showed every byte reaching Windows' USB stack. pyserial and Qt both lost data with the default buffer and none with 1 MiB. Fixed in `transport.py` (`SetupComm`).
- **Cold boot echoed the first HELLO back.** A HELLO arriving before the agent opened `ttyGS0` was echoed under the port's default settings. Fixed by setting the port raw in the gadget script before the USB bind; the host also clears stale bytes when it opens the port.
- **Slow boot ordering.** The gadget and agent waited for `basic.target`. Both now start in early boot, moving the gadget from 9.6 s to 6.0 s and the agent from 9.9 s to 7.7 s after kernel start.
- **Unplugging right after an install left empty files.** Power loss before writes reached the SD card left the unit files at 0 bytes, which systemd treats as masked. `install.sh` now ends with `sync`.
- **Probe pacing.** The achieved echo rate is about 91 Hz at every payload size, limited by Windows timer resolution in the probe, not by the link.
- **Open:** `install.sh` stops the agent but doesn't restart it; add `systemctl try-restart`. The Track Controller board, recorded workload, full-system and fault checks are still pending.
