#!/bin/bash
# Scans every SCAN_EVERY seconds (default 10 minutes) for about 5.5 hours (GitHub stops a job at 6 hours),
# then the workflow starts the next job itself.
# Quiet hours: no scans from 2 AM to 11 AM IST (20:30 to 05:30 UTC). The job stops when quiet hours begin,
# and the daily cron at 05:30 UTC starts the chain again.
END=$(( $(date +%s) + ${LOOP_MINUTES:-330} * 60 ))
export PYTHONIOENCODING=utf-8
quiet() { python3 quiet.py; }
while [ "$(date +%s)" -lt "$END" ]; do
  if quiet; then echo "=== quiet hours (2 AM - 11 AM IST): stopping ==="; break; fi
  start=$(date +%s)
  echo "=== scan $(date -u '+%H:%M') UTC ==="
  timeout 480 python3 newscan.py --tg > latest.txt 2> scan_err.txt
  grep -E "^[0-9]+\. \$|coin\(s\) worth|Nothing worth" latest.txt || true
  grep -E "telegram|FATAL|researching" scan_err.txt || true
  grep -q Traceback scan_err.txt && tail -25 scan_err.txt
  wait_s=$(( ${SCAN_EVERY:-600} - ($(date +%s) - start) ))
  [ "$wait_s" -gt 0 ] && sleep "$wait_s"
done
