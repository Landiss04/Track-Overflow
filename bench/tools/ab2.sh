#!/bin/sh
cd "$1" && QT_QPA_PLATFORM=offscreen timeout 120 python3 bench/per_module.py --system --test-pi process --schedule utils/schedule_stress.json --seconds 40 2>&1 | grep -E "speed achieved|round trip \(ms\)|^ctc-office|^track-controller-hw" | sed "s/^/$2 | /" | cut -c1-118
