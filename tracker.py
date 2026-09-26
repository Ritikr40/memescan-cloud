#!/usr/bin/env python3
"""
tracker - the scanner's report card, kept up to date after every scan.

For every coin the scanner ever called (new_history.jsonl) it keeps:
  the call (first time on the board: time, price, size),
  the price now, the highest price seen since the call, and whether it rugged.

Prices come from DexScreener (free, no key). Coins called in the last 7 days
are checked every run (every 10 minutes); older ones every 3 hours.
The highest price is the highest we SAW (every 10 minutes), so a short spike
between two checks is missed. That makes the numbers careful, not flattering.

seed_track.json (in the repo) holds the coins called before the cloud
started (11-24 Sep, from the PC), with peaks from GeckoTerminal hourly closes.

  python tracker.py          update track.json
"""

import json
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

HOME = Path(__file__).resolve().parent
HISTORY_FILE = HOME / "new_history.jsonl"
TRACK_FILE = HOME / "track.json"
SEED_FILE = HOME / "seed_track.json"

HOT_DAYS = 7              # check every run while the call is this young
COLD_EVERY_S = 3 * 3600   # after that, every 3 hours
KEEP_DAYS = 45            # forget calls older than this
RUG_LIQ = 5_000           # money left in the pool below this = rugged
RUG_DROP = 0.10           # or the price is below 10% of the call price
PRICE_MIN_LIQ = 5_000     # prices from pools with less money than this are ignored (fake prices)
MAX_X = 100               # a jump above this many x is treated as bad data, not a run
MAX_SIZE = 1_000_000_000  # or a price that would make the coin worth more than $1B


def get(url, tries=3):
    for a in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "memescan/3.0", "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=25) as r:
                return json.loads(r.read().decode())
        except Exception:
            if a == tries - 1:
                return None
            time.sleep(4 * (a + 1))


def load(path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def calls_from_history():
    """First appearance of each coin on the board."""
    first = {}
    if not HISTORY_FILE.exists():
        return first
    for line in HISTORY_FILE.open(encoding="utf-8"):
        try:
            d = json.loads(line)
        except ValueError:
            continue
        for p in d.get("picks", []):
            a = p.get("addr")
            if not a or not p.get("price"):
                continue
            if a not in first:
                f = p.get("f") or {}
                first[a] = {"sym": p.get("sym"), "chain": p.get("chain"), "lane": p.get("lane"),
                            "score": p.get("score"), "call_ts": d["ts"], "call_price": p["price"],
                            "call_mcap": p.get("mcap"), "age_h": p.get("age_h"),
                            "family": f.get("family"), "story": f.get("story") or ""}
            first[a]["seen"] = first[a].get("seen", 0) + 1
            first[a]["max_score"] = max(first[a].get("max_score", 0), p.get("score") or 0)
    return first


def believable(t, price):
    """False for impossible prices: >100x the call, or a size over $1B."""
    cp, cm = t.get("call_price") or 0, t.get("call_mcap") or 0
    if not cp:
        return False
    x = price / cp
    return x <= MAX_X and (not cm or cm * x <= MAX_SIZE)


def status(t):
    if t.get("gone") or (t.get("liq") or 0) < RUG_LIQ or not t.get("now_price"):
        return "rugged"
    if t["now_price"] < t["call_price"] * RUG_DROP:
        return "rugged"
    return "alive"


def update(verbose=True):
    track = load(TRACK_FILE, {})
    for a, s in load(SEED_FILE, {}).items():
        track.setdefault(a, s)
    for a, c in calls_from_history().items():
        if a in track:
            track[a]["seen"] = max(track[a].get("seen", 0), c["seen"])
            track[a]["max_score"] = max(track[a].get("max_score", 0), c["max_score"])
        else:
            track[a] = c

    now = time.time()
    due = {}
    for a, t in list(track.items()):
        age_d = (now - datetime.fromisoformat(t["call_ts"]).timestamp()) / 86400
        if age_d > KEEP_DAYS:
            del track[a]
            continue
        if age_d <= HOT_DAYS or now - t.get("checked", 0) >= COLD_EVERY_S:
            due.setdefault(t["chain"], []).append(a)

    n_calls = 0
    for chain, addrs in due.items():
        for i in range(0, len(addrs), 30):
            grp = addrs[i:i + 30]
            pairs = get(f"https://api.dexscreener.com/tokens/v1/{chain}/" + ",".join(grp))
            n_calls += 1
            if pairs is None:            # API trouble: leave these as they were
                continue
            best = {}
            low = {g.lower(): g for g in grp}
            for p in pairs:
                a = low.get(((p.get("baseToken") or {}).get("address") or "").lower())
                if not a:
                    continue
                liq = float((p.get("liquidity") or {}).get("usd") or 0)
                if a not in best or liq > best[a][0]:
                    best[a] = (liq, p)
            for a in grp:
                t = track[a]
                t["checked"] = now
                if a not in best:
                    t["gone"] = True
                    t["now_price"] = 0
                    t["liq"] = 0
                else:
                    liq, p = best[a]
                    price = float(p.get("priceUsd") or 0)
                    if liq < PRICE_MIN_LIQ:
                        price = 0                # no trustworthy price: counts as dead
                    elif not believable(t, price):
                        t["bad_data"] = True     # broken price feed: keep the last good numbers
                        continue
                    chg = p.get("priceChange") or {}
                    t.update(gone=False, liq=liq, now_price=price,
                             now_mcap=p.get("marketCap") or p.get("fdv"),
                             chg1=chg.get("h1"), chg24=chg.get("h24"),
                             v24=(p.get("volume") or {}).get("h24"),
                             name=(p.get("baseToken") or {}).get("name") or t.get("name"),
                             url=p.get("url") or t.get("url"),
                             img=(p.get("info") or {}).get("imageUrl") or t.get("img"))
                    if price > t.get("peak_price", 0):
                        t["peak_price"] = price
                        t["peak_ts"] = now
                t["status"] = status(t)
            time.sleep(0.25)

    for t in track.values():
        cp = t.get("call_price") or 0
        t["now_x"] = round(t["now_price"] / cp, 3) if cp and t.get("now_price") is not None else None
        t["peak_x"] = round(max(t.get("peak_price", 0), cp) / cp, 3) if cp else None

    TRACK_FILE.write_text(json.dumps(track, ensure_ascii=False), encoding="utf-8")
    if verbose:
        print(f"tracker: {len(track)} calls, {sum(len(v) for v in due.values())} checked "
              f"({n_calls} requests)", file=sys.stderr)
    return track


if __name__ == "__main__":
    update()
