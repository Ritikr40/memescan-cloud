#!/usr/bin/env python3
"""
site - builds the public Memescan website (GitHub Pages) into ./site

  index.html    Overview: live status, track record in numbers, best calls
  board.html    Live board: the coins on the board right now
  record.html   Track record: every call, its peak and where it is now
  method.html   How it works, the exit plan, and the honest limits

Reads board.json (last scan, written by newscan.py --site) and track.json
(tracker.py). Plain HTML + one CSS file. Everything is readable without JS;
JS only adds sorting and filters on the track record page.

  python site.py
"""

import html
import json
import math
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

HOME = Path(__file__).resolve().parent
OUT = HOME / "site"
IST = timezone(timedelta(hours=5, minutes=30))

CHAIN_NAME = {"solana": "Solana", "robinhood": "Robinhood Chain", "bsc": "BNB Chain", "base": "Base",
              "ethereum": "Ethereum", "arc": "Arc", "near": "NEAR"}
LANE_NAME = {"new": "New", "waking": "Waking up", "family": "Family"}


def esc(s):
    return html.escape(str(s if s is not None else ""), quote=True)


def money(v):
    v = float(v or 0)
    if v >= 1e9:
        return f"${v/1e9:.1f}B"
    if v >= 1e6:
        return f"${v/1e6:.1f}M"
    if v >= 1e3:
        return f"${v/1e3:.0f}K"
    return f"${v:.0f}"


def xfmt(x):
    if x is None:
        return "–"
    if x >= 10:
        return f"{x:.0f}x"
    return f"{x:.1f}x"


def pct(n, d):
    return f"{100 * n / d:.0f}%" if d else "–"


def ist(ts):
    """ISO string or unix seconds -> '26 Sep, 9:40 PM IST'"""
    if not ts:
        return ""
    t = datetime.fromisoformat(ts) if isinstance(ts, str) else datetime.fromtimestamp(ts, timezone.utc)
    t = t.astimezone(IST)
    return t.strftime("%d %b, ") + t.strftime("%I:%M %p").lstrip("0") + " IST"


MAX_X = 100                 # same rules as tracker.py
MAX_SIZE = 1_000_000_000


def clean(c):
    """Mark impossible numbers (broken price feeds) as bad data instead of showing them."""
    cm = c.get("call_mcap") or 0
    for k in ("peak_x", "now_x"):
        x = c.get(k)
        if x is not None and (x > MAX_X or (cm and cm * x > MAX_SIZE)):
            c["bad"] = True
    if c.get("bad"):
        c["peak_x"] = c["now_x"] = None
    return c


def load(name, default):
    try:
        return json.loads((HOME / name).read_text(encoding="utf-8"))
    except Exception:
        return default


def quiet_now():
    return subprocess.run([sys.executable, str(HOME / "quiet.py")]).returncode == 0


# ---------------------------------------------------------------- shared frame

FONTS = ('<link rel="preconnect" href="https://fonts.googleapis.com">'
         '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
         '<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700&'
         'family=IBM+Plex+Mono:wght@500;600&display=swap" rel="stylesheet">')

NAV = [("index.html", "Overview"), ("board.html", "Live board"),
       ("record.html", "Track record"), ("method.html", "How it works")]


def page(fname, title, body, updated, scripts=""):
    nav = "".join(f'<a href="{h}"{" aria-current=page" if h == fname else ""}>{t}</a>' for h, t in NAV)
    return f"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)} · Memescan</title>
<meta name="description" content="Memescan finds new memecoins early across Solana, Robinhood Chain, BNB Chain and Base, and publishes every call with its result.">
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Crect width='32' height='32' rx='8' fill='%232a78d6'/%3E%3Cpath d='M7 21l6-7 5 4 7-9' stroke='white' stroke-width='3' fill='none' stroke-linecap='round' stroke-linejoin='round'/%3E%3C/svg%3E">
<script>try{{var t=localStorage.getItem("ms-theme");if(t)document.documentElement.setAttribute("data-theme",t)}}catch(e){{}}</script>
{FONTS}
<link rel="stylesheet" href="style.css">
</head><body>
<header class="top"><div class="wrap topin">
  <a class="brand" href="index.html"><span class="logo" aria-hidden="true"></span>Memescan</a>
  <nav class="nav">{nav}</nav>
  <button class="theme" id="theme" type="button" aria-label="Switch dark or light mode" title="Dark / light">
    <svg class="i-moon" viewBox="0 0 24 24" aria-hidden="true"><path d="M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5z"/></svg>
    <svg class="i-sun" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/></svg>
  </button>
</div></header>
<main class="wrap">{body}</main>
<footer class="foot"><div class="wrap">
  <p>Updated {esc(updated)}. Scans every 10 minutes, 11 AM – 2 AM IST.</p>
  <p>Signals only. Not financial advice. Memecoins are extremely risky; most go to zero.</p>
</div></footer>
<script>
(function(){{var b=document.getElementById("theme"),r=document.documentElement;
function dark(){{var t=r.getAttribute("data-theme");return t?t==="dark":matchMedia("(prefers-color-scheme: dark)").matches}}
b.addEventListener("click",function(){{var n=dark()?"light":"dark";r.setAttribute("data-theme",n);try{{localStorage.setItem("ms-theme",n)}}catch(e){{}}}});}})();
</script>
{scripts}
</body></html>"""


# ---------------------------------------------------------------- stats

def stats(calls):
    rows = [c for c in calls if c.get("peak_x") is not None]
    n = len(rows)          # calls with bad data are left out of every number
    s = {"n": n,
         "x2": sum(1 for c in rows if c["peak_x"] >= 2),
         "x5": sum(1 for c in rows if c["peak_x"] >= 5),
         "x10": sum(1 for c in rows if c["peak_x"] >= 10),
         "rug": sum(1 for c in rows if c.get("status") == "rugged"),
         "up": sum(1 for c in rows if c.get("status") != "rugged" and (c.get("now_x") or 0) > 1)}
    s["best"] = max(rows, key=lambda c: c["peak_x"]) if rows else None
    return s


def bucket_chart(calls):
    """Single-series bar chart: how high did calls go after we called them."""
    edges = [("Never above call", 0, 1.05), ("Up to 2x", 1.05, 2), ("2x – 5x", 2, 5),
             ("5x – 10x", 5, 10), ("10x or more", 10, 1e9)]
    counts = [(lab, sum(1 for c in calls if c.get("peak_x") is not None and lo <= c["peak_x"] < hi))
              for lab, lo, hi in edges]
    top = max([v for _, v in counts] + [1])
    total = sum(v for _, v in counts) or 1
    W, H, pad_l, pad_b, pad_t = 1000, 250, 8, 34, 28
    bw = (W - pad_l * 2) / len(counts)
    bars = []
    for i, (lab, v) in enumerate(counts):
        h = (H - pad_b - pad_t) * v / top
        x = pad_l + i * bw + 10
        y = H - pad_b - h
        w = bw - 20
        r = min(4, h)
        # rounded top only, anchored to the baseline
        d = (f"M{x:.1f},{H-pad_b} V{y+r:.1f} Q{x:.1f},{y:.1f} {x+r:.1f},{y:.1f} "
             f"H{x+w-r:.1f} Q{x+w:.1f},{y:.1f} {x+w:.1f},{y+r:.1f} V{H-pad_b} Z") if v else ""
        tip = f"{lab}: {v} calls ({100*v/total:.0f}%)"
        bars.append(f'<g class="bar"><title>{esc(tip)}</title>'
                    f'<rect x="{pad_l + i*bw:.1f}" y="{pad_t}" width="{bw:.1f}" height="{H-pad_t:.0f}" fill="transparent"/>'
                    f'{f"<path d=\"{d}\"/>" if d else ""}'
                    f'<text class="v" x="{x+w/2:.1f}" y="{y-8:.1f}" text-anchor="middle">{v}</text>'
                    f'<text class="l" x="{x+w/2:.1f}" y="{H-12}" text-anchor="middle">{esc(lab)}</text></g>')
    table = "".join(f"<tr><td>{esc(l)}</td><td>{v}</td><td>{100*v/total:.0f}%</td></tr>" for l, v in counts)
    return f"""
<figure class="chart">
  <svg viewBox="0 0 {W} {H}" role="img" aria-label="How high calls went after the call">
    <line class="base" x1="0" x2="{W}" y1="{H-pad_b}" y2="{H-pad_b}"/>
    {''.join(bars)}
  </svg>
  <details class="tableview"><summary>Show as table</summary>
    <table class="tbl small"><thead><tr><th>Highest price after the call</th><th>Calls</th><th>Share</th></tr></thead>
    <tbody>{table}</tbody></table></details>
</figure>"""


def coin_cell(c):
    img = f'<img src="{esc(c["img"])}" alt="" loading="lazy" width="28" height="28">' if c.get("img") else \
        f'<span class="ph" aria-hidden="true">{esc((c.get("sym") or "?")[:1])}</span>'
    name = f'<a href="{esc(c["url"])}" target="_blank" rel="noopener">${esc(c.get("sym"))}</a>' if c.get("url") \
        else f"${esc(c.get('sym'))}"
    return f'<div class="coin">{img}<div><b>{name}</b><small>{esc(CHAIN_NAME.get(c["chain"], c["chain"]))}</small></div></div>'


def chg_cell(v):
    if v is None:
        return '<td class=num data-v="-1e9">–</td>'
    cls = "up" if v > 0 else ("down" if v < 0 else "")
    return f'<td class="num {cls}" data-v="{v}">{v:+.0f}%</td>'


def status_chip(c):
    if c.get("bad"):
        return '<span class="st mid" title="The price feed for this coin is broken, so it is left out of every number.">? Bad data</span>'
    if c.get("status") == "rugged":
        return '<span class="st bad">✕ Rugged</span>'
    if (c.get("now_x") or 0) > 1:
        return '<span class="st good">▲ Up</span>'
    return '<span class="st mid">▼ Down</span>'


# ---------------------------------------------------------------- pages

def overview(board, calls, updated):
    s = stats(calls)
    quiet = quiet_now()
    live = ('<span class="pill quiet"><i></i>Resting (quiet hours 2 AM – 11 AM IST)</span>' if quiet
            else '<span class="pill live"><i></i>Live · scanning every 10 minutes</span>')
    best = s["best"]
    by_chain = {}
    for c in calls:
        if c.get("bad"):
            continue
        by_chain.setdefault(c["chain"], []).append(c)
    chain_rows = "".join(
        f"<tr><td>{esc(CHAIN_NAME.get(ch, ch))}</td><td class=num>{len(v)}</td>"
        f"<td class=num>{pct(sum(1 for c in v if (c.get('peak_x') or 0) >= 2), len(v))}</td>"
        f"<td class=num>{pct(sum(1 for c in v if (c.get('peak_x') or 0) >= 5), len(v))}</td>"
        f"<td class=num>{pct(sum(1 for c in v if c.get('status') == 'rugged'), len(v))}</td></tr>"
        for ch, v in sorted(by_chain.items(), key=lambda kv: -len(kv[1])) if len(v) >= 5)
    top = sorted([c for c in calls if c.get("peak_x")], key=lambda c: -c["peak_x"])[:6]
    top_rows = "".join(
        f"<tr><td>{coin_cell(c)}</td><td>{esc(ist(c['call_ts']))}</td><td class=num>{money(c.get('call_mcap'))}</td>"
        f"<td class='num em'>{xfmt(c['peak_x'])}</td><td class=num>{xfmt(c.get('now_x'))}</td><td>{status_chip(c)}</td></tr>"
        for c in top)
    first = min((c["call_ts"] for c in calls), default=None)
    days = (datetime.now(timezone.utc) - datetime.fromisoformat(first)).days + 1 if first else 0
    n_board = len(board.get("candidates") or [])
    body = f"""
<section class="hero">
  {live}
  <h1>Finds new memecoins early,<br>then shows every result in public.</h1>
  <p class="lede">Memescan checks thousands of brand-new coins on Solana, Robinhood Chain, BNB Chain and Base
  every 10 minutes. It keeps only the ones where real money and real buyers are arriving fast,
  and it records every call, winners and losers, so the track record below cannot be cherry-picked.</p>
  <div class="cta"><a class="btn" href="board.html">See the live board ({n_board} coins)</a>
  <a class="btn ghost" href="record.html">Full track record</a></div>
</section>

<section class="tiles">
  <div class="tile"><span class="k">Coins called</span><span class="v">{s['n']:,}</span><span class="h">in {days} days</span></div>
  <div class="tile"><span class="k">Went 2x or more after the call</span><span class="v">{pct(s['x2'], s['n'])}</span><span class="h">{s['x2']} coins</span></div>
  <div class="tile"><span class="k">Went 5x or more</span><span class="v">{pct(s['x5'], s['n'])}</span><span class="h">{s['x5']} coins · {s['x10']} did 10x+</span></div>
  <div class="tile"><span class="k">Best call</span><span class="v">{xfmt(best['peak_x']) if best else '–'}</span><span class="h">{'$' + esc(best['sym']) + ' from ' + money(best.get('call_mcap')) if best else ''}</span></div>
  <div class="tile warn"><span class="k">Rugged or dead</span><span class="v">{pct(s['rug'], s['n'])}</span><span class="h">{s['rug']} coins · shown, not hidden</span></div>
</section>

<section class="panel">
  <div class="ph2"><h2>How high did coins go after we called them?</h2>
  <p class="sub">Highest price seen after the call, compared with the price at the call. All {s['n']:,} calls.</p></div>
  {bucket_chart(calls)}
  <p class="note">The money is made by selling into the run. Most memecoins give the gains back:
  that is why the scanner comes with a tested <a href="method.html#exit">exit plan</a>.</p>
</section>

<div class="two">
<section class="panel">
  <div class="ph2"><h2>Best calls</h2><p class="sub">Size at the call, highest multiple after it, and where it is now.</p></div>
  <div class="scroll"><table class="tbl"><thead><tr><th>Coin</th><th>Called</th><th class=num>Size at call</th><th class=num>Peak</th><th class=num>Now</th><th>Status</th></tr></thead>
  <tbody>{top_rows}</tbody></table></div>
</section>
<section class="panel">
  <div class="ph2"><h2>By chain</h2><p class="sub">Share of calls that reached each level. Chains with 5+ calls.</p></div>
  <div class="scroll"><table class="tbl"><thead><tr><th>Chain</th><th class=num>Calls</th><th class=num>2x+</th><th class=num>5x+</th><th class=num>Rugged</th></tr></thead>
  <tbody>{chain_rows}</tbody></table></div>
</section>
</div>"""
    return page("index.html", "Overview", body, updated)


def fact(k, v, cls=""):
    return f'<div class="fact"><span>{esc(k)}</span><b class="{cls}">{esc(v)}</b></div>'


def board_page(board, updated):
    cands = board.get("candidates") or []
    quiet = quiet_now()
    cards = []
    for i, c in enumerate(cands, 1):
        strong = c.get("score", 0) >= 60
        st = c.get("story") or {}
        verdict = (st.get("verdict") or "").split(" ")[0].strip(".,:;").lower() if st and not st.get("error") else ""
        story = ""
        if verdict:
            flags = "".join(f"<li>{esc(f)}</li>" for f in (st.get("red_flags") or [])[:4])
            story = (f'<div class="story"><span class="vchip {esc(verdict)}">Story: {esc(verdict)}</span>'
                     f'<p>{esc(st.get("story"))}</p>'
                     + (f'<p class="thesis"><b>Holders say:</b> {esc(st["thesis"])}</p>' if st.get("thesis") else "")
                     + (f'<ul class="flags">{flags}</ul>' if flags else "") + "</div>")
        links = "".join(f'<a href="{esc(u)}" target="_blank" rel="noopener">{esc(u.split("//")[-1].split("/")[0].replace("www.", ""))}</a>'
                        for u in (c.get("links") or [])[:4])
        chg = lambda v: "up" if v > 0 else ("down" if v < 0 else "")
        er = c.get("exit_ratio", 0)
        cards.append(f"""
<article class="card{' strong' if strong else ''}">
  <header>
    <span class="rank">{i:02d}</span>
    <div class="t"><h3><a href="{esc(c.get('url'))}" target="_blank" rel="noopener">${esc(c.get('symbol'))}</a></h3>
    <small>{esc(c.get('name'))}</small></div>
    <span class="score" title="Score out of 100">{c.get('score', 0):.0f}</span>
  </header>
  <div class="chips"><span class="chip">{esc(CHAIN_NAME.get(c.get('chain'), c.get('chain')))}</span>
  <span class="chip lane">{esc(LANE_NAME.get(c.get('lane'), c.get('lane')))}</span>
  <span class="chip">{esc(age(c.get('age_h', 0)))} old</span>
  {'<span class="chip hot">Strong</span>' if strong else ''}{'<span class="chip good">Still here · ' + f"{c.get('board_h', 0):.0f}h" + '</span>' if c.get('still_here') else ''}{'<span class="chip">Early</span>' if c.get('early') else ''}{'<span class="chip">First scan</span>' if c.get('is_new') else ''}</div>
  <div class="facts">
    {fact('Size', money(c.get('mcap')))}{fact('Money in pool', money(c.get('liq')))}
    {fact('Volume 24h', money(c.get('v24')))}{fact('Price 1h', f"{c.get('chg1', 0):+.0f}%", chg(c.get('chg1', 0)))}
    {fact('Price 6h', f"{c.get('chg6', 0):+.0f}%", chg(c.get('chg6', 0)))}{fact('Buys this hour', f"{c.get('buy1', 0)*100:.0f}%")}
    {fact('Holders', f"{c['holders']:,}" if c.get('holders') else '–')}{fact('Sell risk', f"{er:.0f}:1", 'down' if er > 60 else '')}
  </div>
  {story}
  <div class="why"><ul>{''.join(f'<li>{esc(w)}</li>' for w in (c.get('why') or [])[:4])}</ul>
  {('<ul class="warn">' + ''.join(f'<li>{esc(w)}</li>' for w in c.get('warn')[:3]) + '</ul>') if c.get('warn') else ''}</div>
  <footer><code title="Contract address">{esc(c.get('addr'))}</code><div class="links">{links}</div></footer>
</article>""")
    empty = ('<div class="panel empty"><p>' + ("Quiet hours: the scanner rests from 2 AM to 11 AM IST. "
             "This is the last board before the break." if quiet else "Nothing passed the filters in the last scan.")
             + "</p></div>")
    body = f"""
<section class="pagehead">
  <h1>Live board</h1>
  <p class="lede">The coins that passed every filter in the latest scan ({esc(ist(board.get('ts')))}).
  Score 60+ is <b>Strong</b>. Each card shows why it is here and what to be careful about.</p>
  <p class="exit">Exit plan: sell half at 2x, sell the rest if it falls 30% from its high.</p>
</section>
{('<div class="grid">' + ''.join(cards) + '</div>') if cards else ''}
{empty if not cards or quiet else ''}"""
    return page("board.html", "Live board", body, updated)


def age(h):
    h = float(h or 0)
    if h < 1:
        return "under 1 hour"
    if h < 48:
        return f"{h:.0f} hours"
    return f"{h/24:.0f} days"


def record_page(calls, updated):
    s = stats(calls)
    rows = []
    for c in sorted(calls, key=lambda c: c["call_ts"], reverse=True):
        t = datetime.fromisoformat(c["call_ts"]).timestamp()
        live = c.get("status") != "rugged" and not c.get("bad")
        rows.append(
            f'<tr data-chain="{esc(c["chain"])}" data-st="{esc(c.get("status") or "")}" '
            f'data-sym="{esc((c.get("sym") or "").lower())}">'
            f'<td>{coin_cell(c)}</td><td data-v="{t:.0f}">{esc(ist(c["call_ts"]))}</td>'
            f'<td>{esc(LANE_NAME.get(c.get("lane"), c.get("lane") or ""))}</td>'
            f'<td class=num data-v="{c.get("call_mcap") or 0}">{money(c.get("call_mcap"))}</td>'
            f'<td class="num em" data-v="{c.get("peak_x") or 0}">{xfmt(c.get("peak_x"))}</td>'
            f'<td class=num data-v="{c.get("now_x") or 0}">{xfmt(c.get("now_x"))}</td>'
            f'<td class=num data-v="{c.get("now_mcap") or 0 if live else 0}">{money(c.get("now_mcap")) if live else "–"}</td>'
            f'{chg_cell(c.get("chg1") if live else None)}{chg_cell(c.get("chg24") if live else None)}'
            f'<td>{status_chip(c)}</td></tr>')
    chains = sorted({c["chain"] for c in calls}, key=lambda ch: -sum(1 for c in calls if c["chain"] == ch))
    opts = "".join(f'<option value="{esc(ch)}">{esc(CHAIN_NAME.get(ch, ch))}</option>' for ch in chains)
    body = f"""
<section class="pagehead">
  <h1>Track record</h1>
  <p class="lede">Every coin the scanner has called, the first time it reached the board. Nothing removed.
  <b>Peak</b> is the highest price seen after the call divided by the price at the call.
  <b>Now</b> is today's price the same way. <b>Size now</b>, <b>1h</b> and <b>24h</b> show what the coin is doing right now. <b>Rugged</b> means the trading pool was emptied or the price fell below 10% of the call.</p>
</section>
<section class="tiles small">
  <div class="tile"><span class="k">Calls</span><span class="v">{s['n']:,}</span></div>
  <div class="tile"><span class="k">2x+ after call</span><span class="v">{s['x2']}</span><span class="h">{pct(s['x2'], s['n'])}</span></div>
  <div class="tile"><span class="k">5x+ after call</span><span class="v">{s['x5']}</span><span class="h">{pct(s['x5'], s['n'])}</span></div>
  <div class="tile"><span class="k">Still above call, not rugged</span><span class="v">{s['up']}</span><span class="h">{pct(s['up'], s['n'])}</span></div>
  <div class="tile warn"><span class="k">Rugged</span><span class="v">{s['rug']}</span><span class="h">{pct(s['rug'], s['n'])}</span></div>
</section>
<section class="panel">
  <form class="filters" onsubmit="return false">
    <label>Search <input id="q" type="search" placeholder="Ticker"></label>
    <label>Chain <select id="fc"><option value="">All chains</option>{opts}</select></label>
    <label>Result <select id="fr"><option value="">All</option><option value="x5">5x+ after call</option>
      <option value="x2">2x+ after call</option><option value="up">Still up</option><option value="rugged">Rugged</option></select></label>
    <span id="count" class="count">{len(rows)} calls</span>
  </form>
  <div class="scroll"><table class="tbl sortable" id="rec"><thead><tr>
    <th>Coin</th><th data-sort>Called</th><th>Lane</th><th class=num data-sort>Size at call</th>
    <th class=num data-sort>Peak</th><th class=num data-sort>Now</th><th class=num data-sort>Size now</th>
    <th class=num data-sort>1h</th><th class=num data-sort>24h</th><th>Status</th></tr></thead>
  <tbody>{''.join(rows)}</tbody></table></div>
</section>"""
    js = """<script>
(function(){
  var tb=document.querySelector('#rec tbody'), rows=[].slice.call(tb.rows);
  var q=document.getElementById('q'), fc=document.getElementById('fc'), fr=document.getElementById('fr'), cnt=document.getElementById('count');
  function num(td){return parseFloat(td.getAttribute('data-v'))||0}
  function apply(){
    var s=q.value.trim().toLowerCase().replace('$',''), c=fc.value, r=fr.value, n=0;
    rows.forEach(function(tr){
      var peak=num(tr.cells[4]), now=num(tr.cells[5]), st=tr.getAttribute('data-st');
      var ok=(!s||tr.getAttribute('data-sym').indexOf(s)>=0)&&(!c||tr.getAttribute('data-chain')===c)&&
        (!r||(r==='x5'&&peak>=5)||(r==='x2'&&peak>=2)||(r==='rugged'&&st==='rugged')||(r==='up'&&st!=='rugged'&&now>1));
      tr.hidden=!ok; if(ok)n++;
    });
    cnt.textContent=n+' calls';
  }
  [q,fc,fr].forEach(function(el){el.addEventListener('input',apply)});
  document.querySelectorAll('#rec th[data-sort]').forEach(function(th){
    th.tabIndex=0; th.setAttribute('role','button');
    function go(){
      var i=th.cellIndex, dir=th.getAttribute('aria-sort')==='descending'?1:-1;
      document.querySelectorAll('#rec th').forEach(function(h){h.removeAttribute('aria-sort')});
      th.setAttribute('aria-sort',dir<0?'descending':'ascending');
      rows.sort(function(a,b){return dir*(num(a.cells[i])-num(b.cells[i]))});
      rows.forEach(function(tr){tb.appendChild(tr)});
    }
    th.addEventListener('click',go); th.addEventListener('keydown',function(e){if(e.key==='Enter')go()});
  });
})();
</script>"""
    return page("record.html", "Track record", body, updated, js)


def method_page(calls, updated):
    body = """
<section class="pagehead"><h1>How it works</h1>
<p class="lede">Simple rules, all in code, run every 10 minutes. No paid data. Every call is saved before the result is known.</p></section>
<div class="steps">
  <div class="step"><span>1</span><h3>Collect</h3><p>Pull every fresh coin from DexScreener (new profiles, boosts,
  community takeovers) and GeckoTerminal trending lists on Solana, Robinhood Chain, BNB Chain and Base.</p></div>
  <div class="step"><span>2</span><h3>Filter</h3><p>Keep coins under 3 days old worth $250K – $20M with at least $50K in the pool,
  plus coins 3 – 14 days old that are suddenly waking up, plus "family" coins that have many child coins built on them.</p></div>
  <div class="step"><span>3</span><h3>Score</h3><p>0 – 100 from price direction, trading speed, buyers vs sellers, holder growth and sell risk
  (how big the coin is compared with the money in its pool). Copies of a hot name are removed; only the original is called.</p></div>
  <div class="step"><span>4</span><h3>Research</h3><p>Coins scoring 60+ get a short write-up by Claude from a web search: the story,
  where it started, who talks about it, and red flags. It is there to read; it does not change the score.</p></div>
  <div class="step"><span>5</span><h3>Alert &amp; record</h3><p>Each coin is sent to Telegram once, and saved with its price at that moment.
  After that, its price is checked every 10 minutes for 7 days to build the track record.</p></div>
</div>
<section class="panel"><div class="ph2"><h2>Rules learned from the track record</h2>
<p class="sub">From the first report card: 438 calls, 11 – 26 Sep 2026. Added on 27 Sep.</p></div>
<ul class="plain">
<li><b>Only the original.</b> Super Inu was called 10 times; only the 3 real coins won. Now a coin with the same name as a bigger coin is dropped.</li>
<li><b>Still here = stronger.</b> Winners stayed on the board for a median of 5 scans, losers 2. A coin still on the board after 2 hours gets a bonus and a "still here" alert.</li>
<li><b>Careful with brand-new coins and spikes.</b> Coins under 6 hours old won 12% of the time, older ones about 23%. A sudden 5x busier hour was more often a pump and dump.</li>
<li><b>Earlier on big news.</b> Very busy coins can now get in from $100K, a 5-minute trending list is read every scan, and fast holder growth counts more.</li>
<li><b>Stricter on Robinhood Chain.</b> 70% of its calls rugged, so it needs more money in the pool and more trades.</li>
<li><b>Stories are for reading.</b> Claude called the story "weak" for 22 of the 23 winners it checked, so the story no longer lowers the score.</li>
</ul></section>
<section class="panel" id="exit"><div class="ph2"><h2>The exit plan</h2></div>
<p>Tested on 26 past calls (24 Sep 2026): <b>sell half at 2x, then sell the rest if it falls 30% from its highest price.</b>
Holding without a plan lost more than half the money on 17 of 26 coins. With the plan, 5 of 26 did.
Most runners give back their whole run within days, so the exit matters more than the entry.</p></section>
<section class="panel"><div class="ph2"><h2>Honest limits</h2></div>
<ul class="plain">
<li><b>Peaks are sampled.</b> Prices are checked every 10 minutes (before 24 Sep: hourly candles). A spike between two checks is missed, so real peaks were a bit higher than shown.</li>
<li><b>Nobody sells exactly at the peak.</b> The Peak column shows what was possible, not what a trader made.</li>
<li><b>Copycats.</b> Popular names get copied many times. The scanner flags repeats, but some copies still reach the board, and they show up in the record as losers.</li>
<li><b>The score is still being tuned.</b> So far it separates good from bad coins only a little. Every call's details are saved so the score can be tested and improved.</li>
<li><b>Quiet hours.</b> No scans from 2 AM to 11 AM IST. Coins that start and finish in that window are missed.</li>
</ul></section>"""
    return page("method.html", "How it works", body, updated)


CSS = """
:root{--bg:#f6f7f9;--surface:#ffffff;--surface-2:#f0f2f5;--line:#e3e6eb;--ink:#0d1117;--ink-2:#4a5260;--ink-3:#7a8290;
--brand:#2a78d6;--brand-ink:#ffffff;--good:#0e8a4f;--good-bg:#e6f5ec;--bad:#c93434;--bad-bg:#fbeaea;--mid:#8a6a00;--mid-bg:#fbf3dc;
--hot:#b4531b;--shadow:0 1px 2px rgba(13,17,23,.05),0 4px 16px rgba(13,17,23,.04);color-scheme:light}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#0b0e13;--surface:#12161d;--surface-2:#181d26;--line:#232a35;
--ink:#eef1f5;--ink-2:#aab2bf;--ink-3:#7c8594;--brand:#3987e5;--good:#3ccf86;--good-bg:#0f2a1d;--bad:#ff7b7b;--bad-bg:#2d1416;
--mid:#e6b94a;--mid-bg:#2a2210;--hot:#ff9a5c;--shadow:none;--sun:block;--moon:none;color-scheme:dark}}
:root[data-theme="dark"]{--bg:#0b0e13;--surface:#12161d;--surface-2:#181d26;--line:#232a35;--ink:#eef1f5;--ink-2:#aab2bf;--ink-3:#7c8594;
--brand:#3987e5;--good:#3ccf86;--good-bg:#0f2a1d;--bad:#ff7b7b;--bad-bg:#2d1416;--mid:#e6b94a;--mid-bg:#2a2210;--hot:#ff9a5c;--shadow:none;--sun:block;--moon:none;color-scheme:dark}
*{box-sizing:border-box}html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.55 'IBM Plex Sans',system-ui,-apple-system,Segoe UI,sans-serif}
a{color:var(--brand);text-decoration:none}a:hover{text-decoration:underline}
.wrap{max-width:1160px;margin:0 auto;padding:0 16px}
.top{position:sticky;top:0;z-index:5;background:color-mix(in srgb,var(--bg) 88%,transparent);backdrop-filter:blur(10px);border-bottom:1px solid var(--line)}
.topin{display:flex;align-items:center;gap:24px;height:60px}
.brand{display:flex;align-items:center;gap:10px;font-weight:700;font-size:17px;color:var(--ink);letter-spacing:-.01em}
.brand:hover{text-decoration:none}
.logo{width:26px;height:26px;border-radius:7px;background:var(--brand) url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Cpath d='M7 21l6-7 5 4 7-9' stroke='white' stroke-width='3' fill='none' stroke-linecap='round' stroke-linejoin='round'/%3E%3C/svg%3E") center/100%}
.nav{display:flex;gap:4px;overflow-x:auto;scrollbar-width:none;margin-left:auto}
.nav a{color:var(--ink-2);padding:7px 12px;border-radius:8px;font-weight:500;font-size:14px;white-space:nowrap}
.nav a:hover{background:var(--surface-2);text-decoration:none;color:var(--ink)}
.nav a[aria-current]{color:var(--ink);background:var(--surface-2)}
.theme{flex:none;width:36px;height:36px;border-radius:9px;border:1px solid var(--line);background:var(--surface);color:var(--ink-2);display:grid;place-items:center;cursor:pointer;padding:0}
.theme:hover{color:var(--ink)}.theme:focus-visible,.btn:focus-visible,.nav a:focus-visible{outline:2px solid var(--brand);outline-offset:2px}
.theme svg{width:18px;height:18px;fill:none;stroke:currentColor;stroke-width:2;stroke-linecap:round}
.theme .i-sun{display:var(--sun,none)}.theme .i-moon{display:var(--moon,block)}
h1{font-size:clamp(28px,4.4vw,46px);line-height:1.1;letter-spacing:-.025em;margin:14px 0 14px;font-weight:700}
h2{font-size:18px;margin:0;letter-spacing:-.01em}h3{margin:0}
.lede{color:var(--ink-2);font-size:17px;max-width:760px;margin:0}
.hero{padding:56px 0 28px}.pagehead{padding:40px 0 20px}
.pill{display:inline-flex;align-items:center;gap:8px;font-size:13px;font-weight:500;padding:5px 12px;border-radius:99px;border:1px solid var(--line);background:var(--surface);color:var(--ink-2)}
.pill i{width:8px;height:8px;border-radius:50%;background:var(--good);box-shadow:0 0 0 3px var(--good-bg)}
.pill.quiet i{background:var(--mid);box-shadow:0 0 0 3px var(--mid-bg)}
.cta{display:flex;gap:10px;flex-wrap:wrap;margin-top:26px}
.btn{background:var(--brand);color:var(--brand-ink);padding:11px 18px;border-radius:10px;font-weight:600;font-size:15px}
.btn:hover{text-decoration:none;filter:brightness(1.08)}
.btn.ghost{background:var(--surface);color:var(--ink);border:1px solid var(--line)}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:12px;margin:20px 0}
.tile{background:var(--surface);border:1px solid var(--line);border-radius:14px;padding:16px 18px;box-shadow:var(--shadow);display:flex;flex-direction:column;gap:4px;min-width:0}
.tile .k{font-size:13px;color:var(--ink-2)}
.tile .v{font:600 30px/1.1 'IBM Plex Mono',ui-monospace,monospace;letter-spacing:-.02em}
.tile .h{font-size:13px;color:var(--ink-3)}
.tile.warn .v{color:var(--bad)}
.tiles.small .v{font-size:24px}
.panel{background:var(--surface);border:1px solid var(--line);border-radius:16px;padding:22px;box-shadow:var(--shadow);margin:16px 0}
.panel p{margin:10px 0 0}.ph2{margin-bottom:12px}.sub{color:var(--ink-3);font-size:14px;margin:4px 0 0!important}
.note{color:var(--ink-2);font-size:14px}
.two{display:grid;grid-template-columns:1.5fr 1fr;gap:16px}.two .panel{margin:0}
.chart{margin:8px 0 0}.chart svg{width:100%;height:auto;display:block}
.chart .bar path{fill:var(--brand)}.chart .bar:hover path{filter:brightness(1.15)}
.chart .v{font:600 14px 'IBM Plex Mono',monospace;fill:var(--ink)}.chart .l{font-size:12.5px;fill:var(--ink-2)}
.chart .base{stroke:var(--line);stroke-width:1}
.tableview{margin-top:8px;font-size:13px;color:var(--ink-3)}.tableview summary{cursor:pointer}
.scroll{overflow-x:auto;-webkit-overflow-scrolling:touch}
.tbl{width:100%;border-collapse:collapse;font-size:14px}
.tbl th{text-align:left;font-weight:500;color:var(--ink-3);font-size:12.5px;padding:8px 10px;border-bottom:1px solid var(--line);white-space:nowrap}
.tbl td{padding:10px;border-bottom:1px solid var(--line);white-space:nowrap;vertical-align:middle}
.tbl tr:last-child td{border-bottom:0}.tbl th.num{font-family:inherit;font-size:12.5px}.tbl .num{text-align:right;font-family:'IBM Plex Mono',monospace;font-size:13.5px}
.tbl .em{font-weight:600}.tbl td.up{color:var(--good)}.tbl td.down{color:var(--bad)}.tbl.small td,.tbl.small th{padding:6px 8px}
.tbl th[data-sort]{cursor:pointer}.tbl th[data-sort]::after{content:" ↕";opacity:.4}
.tbl th[aria-sort=descending]::after{content:" ↓";opacity:1}.tbl th[aria-sort=ascending]::after{content:" ↑";opacity:1}
.coin{display:flex;align-items:center;gap:10px}.coin img,.coin .ph{width:28px;height:28px;border-radius:50%;flex:none;object-fit:cover;background:var(--surface-2)}
.coin .ph{display:grid;place-items:center;font-size:12px;font-weight:600;color:var(--ink-2)}
.coin b{display:block;font-weight:600}.coin b a{color:var(--ink)}.coin small{display:block;color:var(--ink-3);font-size:12px;line-height:1.2}
.st{display:inline-block;font-size:12.5px;font-weight:600;padding:3px 9px;border-radius:99px}
.st.good{color:var(--good);background:var(--good-bg)}.st.bad{color:var(--bad);background:var(--bad-bg)}.st.mid{color:var(--mid);background:var(--mid-bg)}
.filters{display:flex;flex-wrap:wrap;gap:12px;align-items:flex-end;margin-bottom:12px}
.filters label{display:flex;flex-direction:column;gap:4px;font-size:12.5px;color:var(--ink-3)}
.filters input,.filters select{font:inherit;font-size:14px;color:var(--ink);background:var(--surface-2);border:1px solid var(--line);border-radius:8px;padding:8px 10px;min-width:150px}
.count{margin-left:auto;color:var(--ink-3);font-size:13px}
.exit{margin-top:14px;display:inline-block;background:var(--mid-bg);color:var(--mid);font-weight:600;font-size:14px;padding:8px 14px;border-radius:10px}
.grid{display:grid;grid-template-columns:repeat(2,1fr);gap:16px;margin:10px 0 30px}
.card{background:var(--surface);border:1px solid var(--line);border-radius:16px;padding:18px;box-shadow:var(--shadow);display:flex;flex-direction:column;gap:14px;min-width:0}
.card.strong{border-color:color-mix(in srgb,var(--hot) 55%,var(--line))}
.card header{display:flex;align-items:center;gap:12px}
.card .rank{font:600 13px 'IBM Plex Mono',monospace;color:var(--ink-3)}
.card .t{min-width:0;flex:1}.card h3{font-size:20px;letter-spacing:-.01em}.card h3 a{color:var(--ink)}
.card .t small{color:var(--ink-3);display:block;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.card .score{font:600 22px 'IBM Plex Mono',monospace;background:var(--surface-2);border-radius:10px;padding:6px 10px}
.card.strong .score{color:var(--hot)}
.chips{display:flex;flex-wrap:wrap;gap:6px}
.chip{font-size:12px;font-weight:500;padding:3px 9px;border-radius:99px;background:var(--surface-2);color:var(--ink-2)}
.chip.lane{color:var(--brand)}.chip.good{color:var(--good);background:var(--good-bg)}.chip.hot{color:var(--hot);background:color-mix(in srgb,var(--hot) 14%,transparent)}
.facts{display:grid;grid-template-columns:repeat(4,1fr);gap:10px 12px;background:var(--surface-2);border-radius:12px;padding:12px}
.fact{display:flex;flex-direction:column;min-width:0}.fact span{font-size:11.5px;color:var(--ink-3)}
.fact b{font:600 14px 'IBM Plex Mono',monospace}.fact b.up{color:var(--good)}.fact b.down{color:var(--bad)}
.story{border-left:3px solid var(--brand);padding-left:12px;font-size:14px;color:var(--ink-2)}.story p{margin:6px 0}
.vchip{font-size:12px;font-weight:600;text-transform:capitalize;color:var(--ink-2)}
.vchip.strong{color:var(--good)}.vchip.weak{color:var(--bad)}
.flags,.why ul{margin:0;padding-left:18px;font-size:14px;color:var(--ink-2)}.flags li,.warn li{color:var(--bad)}
.why .warn{margin-top:6px}
.card footer{display:flex;flex-wrap:wrap;gap:8px 14px;align-items:center;border-top:1px solid var(--line);padding-top:12px;margin-top:auto}
.card code{font-size:11.5px;color:var(--ink-3);overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:100%;user-select:all}
.links{display:flex;gap:10px;flex-wrap:wrap;font-size:13px}
.empty{text-align:center;color:var(--ink-2)}
.steps{display:grid;grid-template-columns:repeat(5,1fr);gap:12px;margin:10px 0}
.step{background:var(--surface);border:1px solid var(--line);border-radius:14px;padding:18px;box-shadow:var(--shadow)}
.step span{display:inline-grid;place-items:center;width:28px;height:28px;border-radius:8px;background:var(--brand);color:#fff;font-weight:700;font-size:14px}
.step h3{margin:12px 0 6px;font-size:16px}.step p{margin:0;font-size:14px;color:var(--ink-2)}
.plain{margin:0;padding-left:18px;color:var(--ink-2)}.plain li{margin:8px 0}.plain b{color:var(--ink)}
.foot{border-top:1px solid var(--line);margin-top:40px;padding:22px 0 34px;color:var(--ink-3);font-size:13px}.foot p{margin:4px 0}
@media (max-width:960px){.two,.grid{grid-template-columns:1fr}.steps{grid-template-columns:1fr 1fr}}
@media (max-width:560px){.tiles{grid-template-columns:1fr 1fr}.tile{padding:14px}.tile .v{font-size:24px}.facts{grid-template-columns:repeat(2,1fr)}
.steps{grid-template-columns:1fr}.hero{padding-top:32px}.topin{flex-wrap:wrap;height:auto;gap:8px;padding-top:10px}.theme{margin-left:auto}.nav{order:3;width:100%;margin:0 0 0 -8px;padding-bottom:8px}.nav a{padding:6px 8px;font-size:13.5px}.count{margin-left:0}}
"""


def build():
    board = load("board.json", {})
    track = load("track.json", {})
    calls = [clean(dict(v, addr=a)) for a, v in track.items() if v.get("call_price")]
    updated = ist(board.get("ts") or datetime.now(timezone.utc).isoformat())
    OUT.mkdir(exist_ok=True)
    files = {"index.html": overview(board, calls, updated),
             "board.html": board_page(board, updated),
             "record.html": record_page(calls, updated),
             "method.html": method_page(calls, updated),
             "style.css": CSS,
             ".nojekyll": ""}
    for name, text in files.items():
        (OUT / name).write_text(text, encoding="utf-8")
    print(f"site: {len(calls)} calls, {len(board.get('candidates') or [])} on board -> {OUT}", file=sys.stderr)


if __name__ == "__main__":
    build()
