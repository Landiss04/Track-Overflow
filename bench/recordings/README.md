# Recorded Red workloads for the hardware Pi replay tests

`python -m common.hw_link.bringup --recording FILE` replays these through the real host transport and framing at a fixed rate (`--hz 100` is the 10x rate). It reads **uncompressed** `.jsonl`, so unpack first; `bench\pi_test_menu.cmd` does this the first time you use a replay.

| File (compressed here) | Module | Contents | Requests | Replay length at 100 Hz |
| --- | --- | --- | --- | --- |
| `track-red-180s.jsonl.gz` | Track Controller | 6 `ACTION` (load the six Red wayside territories and their PLC programs) then 18,000 `STEP` | 18,006 | 180 s |
| `train-red-600s.jsonl.gz` | Train Controller | 1 `ACTION` (engineer gains 400000 / 8000) then 60,000 `STEP` | 60,001 | 600 s |

sha256 of the compressed files:

```
eb58ad820df6905a7f6b7db29ee47eee17fed3bb8bfb6a30342b4b9ec4bfc844  track-red-180s.jsonl.gz
0ffb892f2198b36f06aef701a4f69c1a976957190d67c1a173f731e8cace8042  train-red-600s.jsonl.gz
```

sha256 of the unpacked files, to check an unpacked copy:

```
91e06985fd9ad885276a3781a53e5dcaa70c594f0187085eacb561945e285729  track-red-180s.jsonl
727646734f00104131b196c03d69c0eaa025d66df89523be05448781ce5728ae  train-red-600s.jsonl
```

## Unpack by hand (Windows PowerShell, from the repository root)

```powershell
python -c "import gzip,shutil,sys; shutil.copyfileobj(gzip.open(sys.argv[1]), open(sys.argv[2],'wb'))" bench\recordings\track-red-180s.jsonl.gz ..\trains_pi\track-red-180s.jsonl
```
```powershell
python -c "import gzip,shutil,sys; shutil.copyfileobj(gzip.open(sys.argv[1]), open(sys.argv[2],'wb'))" bench\recordings\train-red-600s.jsonl.gz ..\trains_pi\train-red-600s.jsonl
```

## Where they came from

These are synthetic replays of one Red-train workload, built for the Pi link tests; they are not a recording of a live system run. The Track file loads the six Red wayside territories and PLC programs from `TrackCtrlHw/data` and then repeats a captured sequence of per-step inputs (`dt`, inputs) for 18,000 steps. The Train file is a 600 s workload with one Red train and the engineer's gains set. The scripts that wrote them are in `bench/tools/` (`capture.py` records the step inputs of a real Red run, `make_track_recording.py` writes the Track file from that capture); the capture file itself is not kept. The numbers in `10x-log.md` were measured with exactly these files (checksums above). The territories and programs inside the Track file are copies from the data of the commit they were built from: if `TrackCtrlHw/data` changes, the recording does not follow it.
