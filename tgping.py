#!/usr/bin/env python3
"""
tgping - sends board coins to Ritik's Telegram.

Each coin is sent ONCE, the first time it reaches the board, and once more
if it later turns STRONG. Scans run every 5 minutes, so without this the same
coin would ping 12 times an hour.

Setup (one time):
  tg_token.txt  the bot token from @BotFather (never printed)
  tg_chat.txt   his chat id; found automatically after he sends the bot "hi"

  python tgping.py --test     find the chat id and send a test message
"""

import json
import os
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

HOME = Path(__file__).resolve().parent
TOKEN_FILE = HOME / "tg_token.txt"
CHAT_FILE = HOME / "tg_chat.txt"
SENT_FILE = HOME / "tg_sent.json"
SENT_KEEP_S = 7 * 86400       # forget coins after a week
STRONG = 60


def token():
    if os.environ.get("TG_TOKEN"):                # cloud: GitHub secret
        return os.environ["TG_TOKEN"].strip()
    return TOKEN_FILE.read_text(encoding="utf-8-sig").strip() if TOKEN_FILE.exists() else ""


def api(method, **params):
    url = f"https://api.telegram.org/bot{token()}/{method}"
    data = urllib.parse.urlencode(params).encode()
    try:
        with urllib.request.urlopen(urllib.request.Request(url, data=data), timeout=20) as r:
            return json.loads(r.read().decode())
    except Exception as e:                       # never let Telegram break a scan
        # the URL holds the token, so only the error type is printed
        print(f"  ! telegram {method} failed: {type(e).__name__}", file=sys.stderr)
        return None


def chat_id():
    if os.environ.get("TG_CHAT"):
        return os.environ["TG_CHAT"].strip()
    if CHAT_FILE.exists():
        return CHAT_FILE.read_text(encoding="utf-8-sig").strip()
    got = api("getUpdates") or {}
    for u in reversed(got.get("result") or []):
        chat = ((u.get("message") or {}).get("chat") or {})
        if chat.get("type") == "private" and chat.get("id"):
            CHAT_FILE.write_text(str(chat["id"]), encoding="utf-8")
            return str(chat["id"])
    return ""


def money(v):
    for unit, div in (("B", 1e9), ("M", 1e6), ("K", 1e3)):
        if abs(v) >= div:
            return f"${v/div:.1f}{unit}"
    return f"${v:.0f}"


def age(h):
    return f"{h:.0f}h old" if h < 48 else f"{h/24:.0f} days old"


def esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def social_lines(c):
    """The coin's own X/Twitter, Telegram and site, plus an X search for its
    contract address (shows what people post about it, newest first)."""
    out = []
    links = c.get("links") or []
    x = [u for u in links if "x.com/" in u or "twitter.com/" in u]
    tg = [u for u in links if "t.me/" in u]
    other = [u for u in links if u not in x and u not in tg]
    out.append(f"🐦 X: {esc(x[0])}" if x else "🐦 X: none listed")
    if len(x) > 1:
        out.append(f"🐦 also: {esc(x[1])}")
    if tg:
        out.append(f"💬 TG: {esc(tg[0])}")
    if other:
        out.append(f"🌐 Site: {esc(other[0])}")
    q = urllib.parse.quote(c["addr"])
    out.append(f"🔎 Posts about it: https://x.com/search?q={q}&amp;f=live")
    sym = urllib.parse.quote("$" + c["symbol"])
    out.append(f"🔎 ${esc(c['symbol'])} on X: https://x.com/search?q={sym}&amp;f=live")
    return out


def message(c, upgrade):
    band = "🟢 STRONG" if c["score"] >= STRONG else "👀 WATCH"
    lane = {"new": "NEW", "family": "FAMILY"}.get(c["lane"], "WAKING UP")
    head = "⬆️ NOW STRONG\n" if upgrade else ""
    lines = [f"{head}<b>${esc(c['symbol'])}</b> ({esc(c['name'][:40])})",
             f"{band} {c['score']:.0f}/100 · {lane} · {c['chain']}",
             f"Size {money(c['mcap'])} · pool {money(c['liq'])} · {age(c['age_h'])} · 6h {c['chg6']:+.0f}%"]
    if c.get("holders"):
        h = f"{c['holders']:,} holders"
        if c.get("holders_per_h") is not None:
            h += f" ({c['holders_per_h']:+,.0f}/hour)"
        lines.append(h)
    why = [w for w in c.get("why", []) if not w.startswith(("New coin:", "Family coin:", "Waking up:"))][:3]
    if why:
        lines.append("")
        lines += [f"✅ {esc(w)}" for w in why]
    if c.get("warn"):
        lines += [f"⚠️ {esc(w)}" for w in c["warn"][:2]]
    st = c.get("story") or {}
    if st and not st.get("error"):
        lines.append("")
        lines.append(f"📖 Story ({esc(st.get('verdict', '?'))}): {esc((st.get('story') or '')[:350])}")
        if st.get("thesis"):
            lines.append(f"💬 Holders say: {esc(st['thesis'][:200])}")
    lines.append("")
    lines.append(f"<code>{esc(c['addr'])}</code>")
    lines += social_lines(c)
    lines.append(esc(c["url"]))
    lines.append("Exit plan: sell half at 2x, rest if it drops 30% from its high. Not advice.")
    return "\n".join(lines)[:4000]


def ping(res):
    """Called by newscan.py after each scan with its result."""
    if not token():
        return 0
    chat = chat_id()
    if not chat:
        print("  ! telegram: no chat yet. Send your bot a message first.", file=sys.stderr)
        return 0
    sent = json.loads(SENT_FILE.read_text(encoding="utf-8")) if SENT_FILE.exists() else {}
    now = time.time()
    sent = {k: v for k, v in sent.items() if now - v.get("t", 0) < SENT_KEEP_S}
    n = 0
    for c in res.get("candidates") or []:
        key = f"{c['chain']}:{c['addr']}"
        strong = c["score"] >= STRONG
        was = sent.get(key)
        if was and (was.get("strong") or not strong):
            continue                              # already told him
        ok = api("sendMessage", chat_id=chat, text=message(c, upgrade=bool(was)),
                 parse_mode="HTML", disable_web_page_preview="true")
        if ok and ok.get("ok"):
            sent[key] = {"t": now, "strong": strong, "sym": c["symbol"]}
            n += 1
            time.sleep(1)
    SENT_FILE.write_text(json.dumps(sent, indent=1, ensure_ascii=False), encoding="utf-8")
    return n


if __name__ == "__main__":
    if "--test" in sys.argv:
        if not token():
            sys.exit("No tg_token.txt yet.")
        chat = chat_id()
        if not chat:
            sys.exit("Bot works, but no chat found. Open your bot in Telegram, send 'hi', then run again.")
        r = api("sendMessage", chat_id=chat, text="✅ Memescan is connected. Coins will arrive here.")
        print("sent" if r and r.get("ok") else "send failed")
