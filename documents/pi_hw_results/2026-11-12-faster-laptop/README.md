# Faster-laptop real-Pi test, 2026-11-12

Test notes only, not normative. Tests A and B from
`documents/handoff-pr56-faster-laptop-test.md` (§6), run on head `ac77a12`
(`cbafba0` plus the notes file).

## Machine
- Intel Core i7-12850HX, 31.7 GB RAM, Windows 11 Enterprise (ZZ-243142)
- Python 3.14.10, PySide6 6.11.2, PyInstaller 6.22.2 in `.venv`
- Mains power, Best performance overlay set
- Track Controller Pi on COM3 (`TO-TRACK-CTRL-HW-01`), agent hash `c5ffae7d…`;
  pre-flight `hello_s` 0.056 s, no error

## Results
| Run | Speed avg (range) | Round trip mean | `PI_SKIPPED_LINE` | Other | Exit |
|---|---|---|---|---|---|
| A: PC alone, Pis simulated, 4 min | 10.0x (10.0–10.0) | 5.4–8.1 ms | 0 | no dropped ticks | all 0 |
| B: real Track Controller Pi, 4 min | 8.52x (7.7–8.9) | 10.9–17.8 ms, typically about 11.2 ms | 1 (tick 0) | 1 `REPLY_SLOW` at tick 16800; `TIME_SLIPPING` throughout, about 3,400 ticks dropped | all 0 |
| Old laptop baseline, real Pi, 4 min | 7.5x (6.1–8.4) | 11.1–13.0 ms | 38 | | all 0 |

No `PI_HELLO_REJECTED` or `Traceback` in either run.

## Reading
- A fast and B below 10x: by the handoff's rule, the Pi or its link is now the limit.
  The round trip of about 11 ms is still over the 10 ms each tick has at 10x.
- B beat the old laptop by about 1x, so the old laptop was also costing speed.
- The damaged line was at tick 0, right after connecting; it was resent (`PI_RESENT`).
- `REPLY_SLOW` at tick 16800 (a multiple of 600) matches the checkpoint-write behaviour in
  §8; the round trip peaked at 1442 ms in that interval and the clock ran on.

## Files
- `console-A.txt`, `console-B.txt`: headless console output, converted to UTF-8
- `logs-A/`, `logs-B/`: harness event logs
