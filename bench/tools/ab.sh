#!/bin/sh
# usage: ab.sh <repo dir> <label>
cd "$1" && QT_QPA_PLATFORM=offscreen timeout 120 python3 bench/per_module.py --system --track-controller-pi process --train-controller-pi process --schedule utils/schedule_stress.json --seconds 40 2>&1 | grep -E "speed achieved|round trip \(ms\)|^track-controller-hw|^ctc-office" | sed "s/^/$2 | /" | cut -c1-120
