#!/bin/bash
# one suite at a time, as the handover describes
cd "$1"; out="$2"; export QT_QPA_PLATFORM=offscreen PYTHONDONTWRITEBYTECODE=1
for s in common/hw_link/tests TrainModel/tests CTC-Office/tests utils/tests common/harness/tests; do
  n=$(echo $s | tr '/' '_'); python3 -m pytest -p no:cacheprovider -q $s > $out/$n.log 2>&1
  echo "$s: $(tail -1 $out/$n.log)" >> $out/summary.txt
done
echo DONE >> $out/summary.txt
