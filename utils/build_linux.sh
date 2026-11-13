#!/usr/bin/env bash
# Build the shared executable, keeping generated artifacts outside the checkout.
set -euo pipefail
repo=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
output=${1:-/tmp/track-overflow-build}
python_bin=${PYTHON:-python}
mkdir -p "$output"
output=$(cd -- "$output" && pwd)
case "$output/" in "$repo/"*) echo "Build output must be outside the checkout" >&2; exit 2;; esac
export PYINSTALLER_CONFIG_DIR="$output/cache"
cd "$repo"
"$python_bin" -m common.hw_link.manifest --output "$output/pi-bundle.json"
exec "$python_bin" -m PyInstaller --noconfirm --clean --onedir --name track-overflow \
  --distpath "$output/dist" --workpath "$output/work" --specpath "$output" \
  --paths "$repo/TrackModel" --paths "$repo/TrainModel" \
  --paths "$repo/Train-Ctrl_HW" --paths "$repo/TrackCtrlSW" \
  --paths "$repo/TrackCtrlHw" --paths "$repo/CTC-Office" \
  --collect-submodules common.hw_link --collect-submodules track_ctrl_hw \
  --add-data "$repo/common/harness/ui:common/harness/ui" \
  --add-data "$output/pi-bundle.json:." \
  --add-data "$repo/ui:ui" \
  --add-data "$repo/TrackModel/ui:TrackModel/ui" \
  --add-data "$repo/TrackModel/green_line.json:TrackModel" \
  --add-data "$repo/TrackModel/red_line.json:TrackModel" \
  --add-data "$repo/TrackCtrlSW/ui:TrackCtrlSW/ui" \
  --add-data "$repo/TrackCtrlHw/ui:TrackCtrlHw/ui" \
  --add-data "$repo/TrackCtrlHw/data:TrackCtrlHw/data" \
  --add-data "$repo/CTC-Office/ctc_ui/ui:CTC-Office/ctc_ui/ui" \
  --add-data "$repo/TrainModel/ui:TrainModel/ui" \
  --add-data "$repo/TrainModel/pics:TrainModel/pics" \
  --add-data "$repo/Train-Ctrl_HW/ui_parts:Train-Ctrl_HW/ui_parts" \
  --add-data "$repo/Train-Ctrl_HW/train_ctrl:Train-Ctrl_HW/train_ctrl" \
  --add-data "$repo/Train-Ctrl_HW/check.py:Train-Ctrl_HW" \
  --add-data "$repo/utils/Track_Overlow_Logo.png:utils" track_overflow.py
