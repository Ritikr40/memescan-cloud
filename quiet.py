"""Exit 0 during quiet hours (2 AM to 11 AM IST), exit 1 otherwise.
Change QUIET_START / QUIET_END (IST, 24h, minutes allowed) to move the window."""
import sys
from datetime import datetime, timedelta, timezone

QUIET_START = (2, 0)   # 2:00 AM IST
QUIET_END = (11, 0)    # 11:00 AM IST

ist = datetime.now(timezone(timedelta(hours=5, minutes=30)))
now = ist.hour * 60 + ist.minute
start = QUIET_START[0] * 60 + QUIET_START[1]
end = QUIET_END[0] * 60 + QUIET_END[1]
sys.exit(0 if start <= now < end else 1)
