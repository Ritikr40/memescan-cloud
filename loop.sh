#!/bin/bash
# Scans every SCAN_EVERY seconds (default 10 minutes) for about 5.5 hours (GitHub stops a job at 6 hours),
# then the workflow starts the next job itself.
END=$(( $(date +%s) + ${LOOP_MINUTES:-330} * 60 ))
export PYTHONIOENCODING=utf-8
while [ "$(date +%s)" -lt "$END" ]; do
  start=$(date +%s)
  echo "=== scan $(date -u '+%H:%M') UTC ==="
  timeout 480 python3 newscan.py --tg > latest.txt 2> scan_err.txt
  grep -E "^[0-9]+\. \$|coin\(s\) worth|Nothing worth" latest.txt || true
  grep -E "telegram|FATAL|Traceback" scan_err.txt || true
  wait_s=$(( ${SCAN_EVERY:-600} - ($(date +%s) - start) ))
  [ "$wait_s" -gt 0 ] && sleep "$wait_s"
done
