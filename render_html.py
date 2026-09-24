#!/usr/bin/env python3
"""Builds the memescan dashboard page from a scan result.

One generator feeds both outputs -- the local dashboard.html written every
hour by the scheduled task, and the hosted artifact -- so the two can never
drift apart.
"""

import html
from datetime import datetime, timezone

# Score component ceilings, mirrored from scan.py's score().
# Used to draw the stacked meter that shows *which* signal earned the points.
PART_MAX = {
    "acceleration": 30,
    "turnover": 20,
    "buy_pressure": 20,
    "story": 20,
    "crowd": 10,
}
PART_LABEL = {
    "acceleration": "Speeding up",
    "turnover": "Attention",
    "buy_pressure": "Buying",
    "story": "Story",
    "crowd": "Crowd",
}

CSS = """
:root {
  --ground:      #EEF0F3;
  --surface:     #FFFFFF;
  --surface-2:   #E4E8ED;
  --line:        #D3D9E0;
  --line-strong: #B4BDC7;
  --ink:         #14181D;
  --ink-2:       #495563;
  --ink-3:       #77828F;
  --accent:      #B45309;
  --accent-soft: #F2E3D0;
  --rise:        #0E7C5A;
  --fall:        #B4232B;
  --rise-soft:   #D8EDE4;
  --fall-soft:   #F6DDDE;
  --p-accel:     #B45309;
  --p-turn:      #8C6A1F;
  --p-buy:       #0E7C5A;
  --p-story:     #2E5A8F;
  --p-crowd:     #6B5B8F;
  --shadow:      0 1px 2px rgba(20,24,29,.06), 0 8px 24px -12px rgba(20,24,29,.14);
}

@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    --ground:      #0E1216;
    --surface:     #161B21;
    --surface-2:   #1E242B;
    --line:        #2A323B;
    --line-strong: #3C4652;
    --ink:         #E7ECF2;
    --ink-2:       #A3AEBB;
    --ink-3:       #737F8C;
    --accent:      #E8A33D;
    --accent-soft: #3A2C15;
    --rise:        #3FBF90;
    --fall:        #F06A70;
    --rise-soft:   #123227;
    --fall-soft:   #351A1D;
    --p-accel:     #E8A33D;
    --p-turn:      #C9A94E;
    --p-buy:       #3FBF90;
    --p-story:     #6BA3E0;
    --p-crowd:     #A48FD1;
    --shadow:      0 1px 2px rgba(0,0,0,.4), 0 8px 24px -12px rgba(0,0,0,.6);
  }
}
:root[data-theme="dark"] {
  --ground:      #0E1216;
  --surface:     #161B21;
  --surface-2:   #1E242B;
  --line:        #2A323B;
  --line-strong: #3C4652;
  --ink:         #E7ECF2;
  --ink-2:       #A3AEBB;
  --ink-3:       #737F8C;
  --accent:      #E8A33D;
  --accent-soft: #3A2C15;
  --rise:        #3FBF90;
  --fall:        #F06A70;
  --rise-soft:   #123227;
  --fall-soft:   #351A1D;
  --p-accel:     #E8A33D;
  --p-turn:      #C9A94E;
  --p-buy:       #3FBF90;
  --p-story:     #6BA3E0;
  --p-crowd:     #A48FD1;
  --shadow:      0 1px 2px rgba(0,0,0,.4), 0 8px 24px -12px rgba(0,0,0,.6);
}

* { box-sizing: border-box; }

body {
  background: var(--ground);
  color: var(--ink);
  font-family: "IBM Plex Sans", ui-sans-serif, system-ui, sans-serif;
  font-size: 15px;
  line-height: 1.55;
  -webkit-font-smoothing: antialiased;
}

.wrap {
  max-width: 1080px;
  margin: 0 auto;
  padding: 32px 20px 72px;
  display: flex;
  flex-direction: column;
  gap: 28px;
}

/* ---------- masthead ---------- */
.masthead {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-end;
  justify-content: space-between;
  gap: 16px 24px;
  padding-bottom: 18px;
  border-bottom: 2px solid var(--ink);
}
.wordmark {
  font-family: Archivo, ui-sans-serif, system-ui, sans-serif;
  font-weight: 800;
  font-size: 30px;
  letter-spacing: -.028em;
  line-height: 1;
  margin: 0;
}
.wordmark span { color: var(--accent); }
.tagline {
  margin: 7px 0 0;
  color: var(--ink-2);
  font-size: 13.5px;
  max-width: 46ch;
}
.stamp {
  font-family: "IBM Plex Mono", ui-monospace, monospace;
  font-size: 11.5px;
  color: var(--ink-3);
  text-align: right;
  line-height: 1.75;
  font-variant-numeric: tabular-nums;
}
.stamp b { color: var(--ink); font-weight: 600; }
.pulse {
  display: inline-block;
  width: 7px; height: 7px;
  border-radius: 50%;
  background: var(--rise);
  margin-right: 6px;
  vertical-align: 1px;
  animation: blip 2.6s ease-in-out infinite;
}
@keyframes blip { 0%,100% { opacity: 1; } 50% { opacity: .28; } }
@media (prefers-reduced-motion: reduce) { .pulse { animation: none; } }

/* ---------- summary ---------- */
.summary {
  display: flex;
  flex-wrap: wrap;
  gap: 10px 28px;
  align-items: baseline;
  font-family: "IBM Plex Mono", ui-monospace, monospace;
  font-size: 12px;
  color: var(--ink-3);
  font-variant-numeric: tabular-nums;
}
.summary .k { color: var(--ink); font-weight: 600; font-size: 13px; }

/* ---------- readout row ---------- */
.board { display: flex; flex-direction: column; gap: 14px; }

.readout {
  background: var(--surface);
  border: 1px solid var(--line);
  border-left: 3px solid var(--line-strong);
  border-radius: 3px;
  padding: 18px 20px 20px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.readout.is-strong {
  border-left-color: var(--accent);
  box-shadow: var(--shadow);
}

.head {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 8px 12px;
}
.rank {
  font-family: "IBM Plex Mono", ui-monospace, monospace;
  font-size: 12px;
  color: var(--ink-3);
  font-variant-numeric: tabular-nums;
}
.ticker {
  font-family: Archivo, ui-sans-serif, system-ui, sans-serif;
  font-weight: 700;
  font-size: 22px;
  letter-spacing: -.02em;
  margin: 0;
}
.ticker a { color: inherit; text-decoration: none; border-bottom: 2px solid var(--accent-soft); }
.ticker a:hover { border-bottom-color: var(--accent); }
.ticker a:focus-visible { outline: 2px solid var(--accent); outline-offset: 3px; border-radius: 2px; }
.fullname { color: var(--ink-3); font-size: 13.5px; }

.chip {
  font-family: "IBM Plex Mono", ui-monospace, monospace;
  font-size: 10.5px;
  text-transform: uppercase;
  letter-spacing: .07em;
  padding: 2.5px 7px;
  border-radius: 2px;
  border: 1px solid var(--line);
  color: var(--ink-2);
  background: var(--surface-2);
  white-space: nowrap;
}
.chip.new    { color: var(--accent); border-color: var(--accent); background: var(--accent-soft); font-weight: 600; }
.chip.up     { color: var(--rise);   border-color: var(--rise);   background: var(--rise-soft); font-weight: 600; }
.chip.down   { color: var(--fall);   border-color: var(--fall);   background: var(--fall-soft); font-weight: 600; }
.spacer { flex: 1 1 auto; }

.verdict {
  font-family: "IBM Plex Mono", ui-monospace, monospace;
  font-size: 11px;
  letter-spacing: .12em;
  text-transform: uppercase;
  font-weight: 600;
  color: var(--ink-3);
}
.verdict.strong { color: var(--accent); }

/* ---------- meter ---------- */
.meter-block { display: flex; flex-direction: column; gap: 7px; }
.meter-top {
  display: flex; align-items: baseline; gap: 10px;
  font-family: "IBM Plex Mono", ui-monospace, monospace;
  font-variant-numeric: tabular-nums;
}
.meter-score { font-size: 26px; font-weight: 600; line-height: 1; letter-spacing: -.02em; }
.meter-of { font-size: 11px; color: var(--ink-3); }

.meter {
  position: relative;
  height: 13px;
  background: var(--surface-2);
  border: 1px solid var(--line);
  border-radius: 2px;
  overflow: hidden;
  display: flex;
}
.seg { height: 100%; }
.seg.acceleration { background: var(--p-accel); }
.seg.turnover     { background: var(--p-turn); }
.seg.buy_pressure { background: var(--p-buy); }
.seg.story        { background: var(--p-story); }
.seg.crowd        { background: var(--p-crowd); }
.tick {
  position: absolute; top: -1px; bottom: -1px;
  width: 1px; background: var(--ink-3); opacity: .55;
}

.legend {
  display: flex; flex-wrap: wrap; gap: 4px 14px;
  font-family: "IBM Plex Mono", ui-monospace, monospace;
  font-size: 10.5px; color: var(--ink-3);
  font-variant-numeric: tabular-nums;
}
.legend span { display: inline-flex; align-items: center; gap: 5px; white-space: nowrap; }
.dot { width: 8px; height: 8px; border-radius: 1px; flex: none; }

/* ---------- facts ---------- */
.facts {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(118px, 1fr));
  gap: 12px 20px;
  padding: 14px 0;
  border-top: 1px solid var(--line);
  border-bottom: 1px solid var(--line);
}
.fact-k {
  font-family: "IBM Plex Mono", ui-monospace, monospace;
  font-size: 10px; text-transform: uppercase; letter-spacing: .09em;
  color: var(--ink-3); display: block; margin-bottom: 2px;
}
.fact-v {
  font-family: "IBM Plex Mono", ui-monospace, monospace;
  font-size: 15px; font-variant-numeric: tabular-nums; font-weight: 500;
}
.fact-v.rise { color: var(--rise); }
.fact-v.fall { color: var(--fall); }

/* ---------- reasons ---------- */
.reasons { display: grid; grid-template-columns: 1fr; gap: 16px; }
@media (min-width: 760px) { .reasons.split { grid-template-columns: 1.35fr 1fr; } }

.lab {
  font-family: "IBM Plex Mono", ui-monospace, monospace;
  font-size: 10px; text-transform: uppercase; letter-spacing: .11em;
  color: var(--ink-3); margin: 0 0 7px;
}
.lab.warnlab { color: var(--fall); }

ul.list { margin: 0; padding: 0; list-style: none; display: flex; flex-direction: column; gap: 7px; }
ul.list li {
  font-size: 13.5px; line-height: 1.5; color: var(--ink-2);
  padding-left: 15px; position: relative;
}
ul.list li::before {
  content: ""; position: absolute; left: 0; top: .58em;
  width: 6px; height: 1.5px; background: var(--accent);
}
ul.list.warn li { color: var(--ink); }
ul.list.warn li::before { background: var(--fall); top: .52em; height: 2px; }

.warnbox {
  background: var(--fall-soft);
  border: 1px solid var(--fall);
  border-radius: 3px;
  padding: 12px 14px;
}

/* ---------- empty ---------- */
.empty {
  background: var(--surface);
  border: 1px dashed var(--line-strong);
  border-radius: 3px;
  padding: 44px 28px;
  text-align: center;
}
.empty h2 {
  font-family: Archivo, ui-sans-serif, system-ui, sans-serif;
  font-size: 19px; margin: 0 0 8px; font-weight: 700;
}
.empty p { margin: 0 auto; max-width: 52ch; color: var(--ink-2); font-size: 14px; }

/* ---------- how ---------- */
.how {
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: 3px;
  padding: 20px 22px;
}
.how h2 {
  font-family: Archivo, ui-sans-serif, system-ui, sans-serif;
  font-size: 15px; margin: 0 0 14px; font-weight: 700;
  letter-spacing: -.01em;
}
.rules { display: grid; grid-template-columns: repeat(auto-fit, minmax(215px, 1fr)); gap: 16px 26px; }
.rule-k {
  font-family: "IBM Plex Mono", ui-monospace, monospace;
  font-size: 10.5px; text-transform: uppercase; letter-spacing: .09em;
  color: var(--accent); margin-bottom: 3px;
}
.rule-v { font-size: 13px; color: var(--ink-2); line-height: 1.5; }

.foot {
  font-size: 12px; color: var(--ink-3); text-align: center;
  border-top: 1px solid var(--line); padding-top: 18px; line-height: 1.7;
}
"""


def money(v):
    for unit, div in (("B", 1e9), ("M", 1e6), ("K", 1e3)):
        if abs(v) >= div:
            return f"${v/div:.1f}{unit}"
    return f"${v:.0f}"


def esc(s):
    return html.escape(str(s), quote=True)


def meter(parts, total):
    """Stacked bar: each segment is one signal's earned points, to a 100 scale.

    Band ticks sit at 45 (the show/hide line) and 60 (watch -> strong).
    """
    segs = []
    for key in ("acceleration", "turnover", "buy_pressure", "story", "crowd"):
        val = parts.get(key, 0)
        if val <= 0.4:
            continue
        segs.append(f'<div class="seg {key}" style="width:{val:.2f}%"></div>')
    ticks = '<div class="tick" style="left:45%"></div><div class="tick" style="left:60%"></div>'
    return f'<div class="meter" role="img" aria-label="score {total:.0f} of 100">{"".join(segs)}{ticks}</div>'


def legend(parts):
    out = []
    for key in ("acceleration", "turnover", "buy_pressure", "story", "crowd"):
        val = parts.get(key, 0)
        if val <= 0.4:
            continue
        out.append(
            f'<span><i class="dot" style="background:var(--p-{key.split("_")[0]})"></i>'
            f'{esc(PART_LABEL[key])} {val:.0f}/{PART_MAX[key]}</span>'
        )
    return f'<div class="legend">{"".join(out)}</div>'


def card(c, i):
    strong = c["score"] >= 60
    chips = [f'<span class="chip">{esc(c["chain"])}</span>',
             f'<span class="chip">{esc(c["meta_name"])} &middot; {c["meta_tokens"]} coins</span>']
    if c.get("is_new"):
        chips.append('<span class="chip new">New</span>')
    elif c.get("prev_score") is not None:
        d = c["score"] - c["prev_score"]
        if abs(d) >= 3:
            cls = "up" if d > 0 else "down"
            chips.append(f'<span class="chip {cls}">{d:+.0f} vs last hour</span>')

    def cls_for(v):
        return "rise" if v > 0 else ("fall" if v < 0 else "")

    facts = [
        ("Size", money(c["mcap"]), ""),
        ("Volume 24h", money(c["v24"]), ""),
        ("Price 1h", f'{c["chg1"]:+.1f}%', cls_for(c["chg1"])),
        ("Price 24h", f'{c["chg24"]:+.1f}%', cls_for(c["chg24"])),
        ("Speed vs normal", f'{c["accel"]:.1f}x', "rise" if c["accel"] >= 1.5 else ""),
        ("Buys last hour", f'{c["buy1"]*100:.0f}%', "rise" if c["buy1"] >= .6 else ""),
        ("Trades 24h", f'{c["txns24"]:,.0f}', ""),
        ("Sell risk", f'{c["exit_ratio"]:.0f}:1', "fall" if c["exit_ratio"] > 50 else ""),
    ]
    facts_html = "".join(
        f'<div><span class="fact-k">{esc(k)}</span>'
        f'<span class="fact-v {cl}">{esc(v)}</span></div>'
        for k, v, cl in facts
    )

    why = "".join(f"<li>{esc(w)}</li>" for w in c["why"])
    warn_html = ""
    if c["warn"]:
        items = "".join(f"<li>{esc(w)}</li>" for w in c["warn"])
        warn_html = (f'<div class="warnbox"><p class="lab warnlab">Careful</p>'
                     f'<ul class="list warn">{items}</ul></div>')

    return f"""
<article class="readout{' is-strong' if strong else ''}">
  <div class="head">
    <span class="rank">{i:02d}</span>
    <h2 class="ticker"><a href="{esc(c['url'])}" target="_blank" rel="noopener">${esc(c['symbol'])}</a></h2>
    <span class="fullname">{esc(c['name'])}</span>
    {''.join(chips)}
    <span class="spacer"></span>
    <span class="verdict{' strong' if strong else ''}">{'Strong' if strong else 'Watch'}</span>
  </div>

  <div class="meter-block">
    <div class="meter-top">
      <span class="meter-score">{c['score']:.0f}</span><span class="meter-of">/ 100</span>
    </div>
    {meter(c['parts'], c['score'])}
    {legend(c['parts'])}
  </div>

  <div class="facts">{facts_html}</div>

  <div class="reasons{' split' if warn_html else ''}">
    <div><p class="lab">Why it is here</p><ul class="list">{why}</ul></div>
    {warn_html}
  </div>
</article>"""


def build_html(res):
    cands = res["candidates"][:8]
    ts = res["ts"][:16].replace("T", " ")
    strong_n = sum(1 for c in cands if c["score"] >= 60)
    sk = res["skipped"]

    if cands:
        body = f'<div class="board">{"".join(card(c, i) for i, c in enumerate(cands, 1))}</div>'
    else:
        body = f"""
<div class="empty">
  <h2>Nothing worth your time right now</h2>
  <p>Checked {res['scanned_metas']} stories across every chain. Everything either was
  too small, too quiet, impossible to sell, or traded only by bots. A silent board is
  a working board &mdash; no signal beats a bad signal.</p>
</div>"""

    return f"""<title>Memescan Board</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Archivo:wght@600;700;800&family=IBM+Plex+Mono:wght@400;500;600&family=IBM+Plex+Sans:wght@400;500;600&display=swap">
<style>{CSS}</style>

<div class="wrap">
  <header class="masthead">
    <div>
      <h1 class="wordmark">MEME<span>SCAN</span></h1>
      <p class="tagline">Finds memecoin stories that are starting to run, and says why.
      Signals only &mdash; nothing here is a recommendation.</p>
    </div>
    <div class="stamp">
      <span class="pulse"></span>Last scan <b>{esc(ts)} UTC</b><br>
      Runs every hour &middot; every chain<br>
      Floor <b>$5M</b> size &middot; <b>$200K</b> daily volume
    </div>
  </header>

  <div class="summary">
    <span><span class="k">{len(cands)}</span> on the board</span>
    <span><span class="k">{strong_n}</span> strong</span>
    <span><span class="k">{res['scanned_metas']}</span> stories checked</span>
    <span>Filtered out: {sk['small']} too small &middot; {sk['quiet']} too quiet &middot;
      {sk['illiquid']} unsellable &middot; {sk['bots']} bot-only</span>
  </div>

  {body}

  <section class="how">
    <h2>What the score is made of</h2>
    <div class="rules">
      <div><div class="rule-k">Speeding up &mdash; 30 pts</div><div class="rule-v">
        Is it trading faster this hour than its own daily average? This is what going
        viral looks like from inside the chain.</div></div>
      <div><div class="rule-k">Attention &mdash; 20 pts</div><div class="rule-v">
        How much of the coin's entire size changed hands in 24 hours.</div></div>
      <div><div class="rule-k">Buying &mdash; 20 pts</div><div class="rule-v">
        Share of trades that were buys, weighted toward the last hour.</div></div>
      <div><div class="rule-k">Story &mdash; 20 pts</div><div class="rule-v">
        Is the whole theme rising, and how many coins share it. One coin is a pump;
        many coins is a story.</div></div>
      <div><div class="rule-k">Crowd &mdash; 10 pts</div><div class="rule-v">
        Number of separate trades. Separates real people from three bots.</div></div>
      <div><div class="rule-k">Points removed</div><div class="rule-v">
        Hard to sell, already up over 60% today, falling right now, or no community
        to spread it.</div></div>
    </div>
  </section>

  <p class="foot">
    Sell risk is size divided by liquidity. Above 50:1 the price you see is not the
    price you get.<br>
    Signals only. Not financial advice. You decide. Never risk money you need.
  </p>
</div>"""


# ==========================================================================
# NEW-COIN BOARD (newscan.py): young coins, their age, and a researched story
# ==========================================================================

NEW_PART_MAX = {"momentum": 25, "volume": 25, "buyers": 20, "community": 15, "safety": 15}
NEW_PART_LABEL = {"momentum": "Price rising", "volume": "Busy trading", "buyers": "Buyers",
                  "community": "Community", "safety": "Easy to sell"}
NEW_PART_COLOR = {"momentum": "accel", "volume": "turn", "buyers": "buy",
                  "community": "story", "safety": "crowd"}

NEW_CSS = """
.seg.momentum  { background: var(--p-accel); }
.seg.volume    { background: var(--p-turn); }
.seg.buyers    { background: var(--p-buy); }
.seg.community { background: var(--p-story); }
.seg.safety    { background: var(--p-crowd); }
.chip.lane-new    { color: var(--accent); border-color: var(--accent); background: var(--accent-soft); font-weight: 600; }
.chip.lane-waking { color: var(--p-story); border-color: var(--p-story); font-weight: 600; }

.storybox { border: 1px solid var(--line); border-radius: 3px; background: var(--surface-2); padding: 14px 16px; display: flex; flex-direction: column; gap: 10px; }
.storyhead { display: flex; flex-wrap: wrap; align-items: baseline; gap: 6px 10px; }
.storyhead .lab { margin: 0; }
.vchip { font-family: "IBM Plex Mono", ui-monospace, monospace; font-size: 11px; font-weight: 600; letter-spacing: .08em; text-transform: uppercase; padding: 2px 8px; border-radius: 2px; border: 1px solid; }
.vchip.strong  { color: var(--rise); border-color: var(--rise); background: var(--rise-soft); }
.vchip.weak    { color: var(--fall); border-color: var(--fall); background: var(--fall-soft); }
.vchip.unclear { color: var(--ink-2); border-color: var(--line-strong); }
.fresh { font-family: "IBM Plex Mono", ui-monospace, monospace; font-size: 11px; color: var(--ink-3); }
.storytext { margin: 0; font-size: 14px; line-height: 1.6; color: var(--ink); }
.storyline { margin: 0; font-size: 13px; line-height: 1.55; color: var(--ink-2); }
.storyline b { color: var(--ink); font-weight: 600; }
.sources { display: flex; flex-wrap: wrap; gap: 4px 12px; font-size: 12px; }
.sources a { color: var(--ink-3); overflow-wrap: anywhere; }
.pending { font-size: 13px; color: var(--ink-3); margin: 0; }
"""


def _age(h):
    if h < 1:
        return "under 1 hour"
    if h < 1.5:
        return "1 hour"
    if h < 48:
        return f"{h:.0f} hours"
    return f"{h/24:.0f} days"


def _meter_new(parts, total):
    segs = "".join(f'<div class="seg {k}" style="width:{parts.get(k, 0):.2f}%"></div>'
                   for k in NEW_PART_MAX if parts.get(k, 0) > 0.4)
    ticks = '<div class="tick" style="left:45%"></div><div class="tick" style="left:60%"></div>'
    legend = "".join(
        f'<span><i class="dot" style="background:var(--p-{NEW_PART_COLOR[k]})"></i>'
        f'{esc(NEW_PART_LABEL[k])} {parts.get(k, 0):.0f}/{NEW_PART_MAX[k]}</span>'
        for k in NEW_PART_MAX if parts.get(k, 0) > 0.4)
    return (f'<div class="meter" role="img" aria-label="score {total:.0f} of 100">{segs}{ticks}</div>'
            f'<div class="legend">{legend}</div>')


def _story(st, score):
    if not st:
        note = ("Story not looked up yet. It will be on the next run."
                if score >= 60 else "No story lookup: only coins scoring 60+ get one.")
        return f'<div class="storybox"><p class="lab">The story</p><p class="pending">{note}</p></div>'
    if st.get("error"):
        return (f'<div class="storybox"><p class="lab">The story</p>'
                f'<p class="pending">Could not look it up: {esc(st["error"])} It will try again later.</p></div>')

    verdict = (st.get("verdict") or "unclear").split()[0].strip(".,:;").lower()
    if verdict not in ("strong", "weak", "unclear"):
        verdict = "unclear"
    flags = "".join(f"<li>{esc(f)}</li>" for f in st.get("red_flags") or [])
    flags_html = (f'<div class="warnbox"><p class="lab warnlab">Red flags found online</p>'
                  f'<ul class="list warn">{flags}</ul></div>') if flags else ""
    srcs = "".join(f'<a href="{esc(u)}" target="_blank" rel="noopener noreferrer">{esc(u[:70])}</a>'
                   for u in st.get("sources") or [])
    when = datetime.fromtimestamp(st.get("ts", 0), timezone.utc).strftime("%d %b %H:%M UTC") if st.get("ts") else ""
    return f"""
  <div class="storybox">
    <div class="storyhead">
      <p class="lab">The story</p>
      <span class="vchip {verdict}">Story: {verdict}</span>
      <span class="fresh">{esc(st.get('freshness') or '')} &middot; looked up {esc(when)}</span>
    </div>
    <p class="storytext">{esc(st.get('story') or '')}</p>
    <p class="storyline"><b>Why {verdict}:</b> {esc(st.get('verdict_why') or '')}</p>
    <p class="storyline"><b>Where it started:</b> {esc(st.get('origin') or 'Not found.')}</p>
    <p class="storyline"><b>Who talks about it:</b> {esc(st.get('buzz') or 'Not found.')}</p>
    {f'<p class="storyline"><b>Holders say:</b> {esc(st["thesis"])}</p>' if st.get("thesis") else ''}
    {f'<p class="storyline"><b>Attention:</b> {esc(st.get("attention") or "")} &mdash; {esc("; ".join(st.get("attention_signs") or []))}</p>' if st.get("attention") else ''}
    {flags_html}
    {f'<div class="sources">{srcs}</div>' if srcs else ''}
  </div>"""


def new_card(c, i):
    strong = c["score"] >= 60
    lane = {"new": '<span class="chip lane-new">New</span>',
            "family": '<span class="chip lane-new">Family</span>'}.get(
                c["lane"], '<span class="chip lane-waking">Waking up</span>')
    chips = [f'<span class="chip">{esc(c["chain"])}</span>', lane,
             f'<span class="chip">{esc(_age(c["age_h"]))} old</span>']
    if c.get("is_new"):
        chips.append('<span class="chip new">First time here</span>')
    elif c.get("prev_score") is not None and abs(c["score"] - c["prev_score"]) >= 3:
        d = c["score"] - c["prev_score"]
        chips.append(f'<span class="chip {"up" if d > 0 else "down"}">{d:+.0f} since last scan</span>')

    def cl(v):
        return "rise" if v > 0 else ("fall" if v < 0 else "")

    facts = [
        ("Size", money(c["mcap"]), ""),
        ("Money in pool", money(c["liq"]), ""),
        ("Volume 24h", money(c["v24"]), ""),
        ("Price 1h", f'{c["chg1"]:+.0f}%', cl(c["chg1"])),
        ("Price 6h", f'{c["chg6"]:+.0f}%', cl(c["chg6"])),
        ("Buys this hour", f'{c["buy1"]*100:.0f}%', "rise" if c["buy1"] >= .58 else ""),
        ("Trades 6h", f'{c["txns6"]:,.0f}', ""),
        ("Sell risk", f'{c["exit_ratio"]:.0f}:1', "fall" if c["exit_ratio"] > 60 else ""),
    ]
    facts_html = "".join(f'<div><span class="fact-k">{esc(k)}</span><span class="fact-v {x}">{esc(v)}</span></div>'
                         for k, v, x in facts)
    why = "".join(f"<li>{esc(w)}</li>" for w in c["why"])
    warn_html = ""
    if c["warn"]:
        warn_html = ('<div class="warnbox"><p class="lab warnlab">Careful</p><ul class="list warn">'
                     + "".join(f"<li>{esc(w)}</li>" for w in c["warn"]) + "</ul></div>")

    return f"""
<article class="readout{' is-strong' if strong else ''}">
  <div class="head">
    <span class="rank">{i:02d}</span>
    <h2 class="ticker"><a href="{esc(c['url'])}" target="_blank" rel="noopener">${esc(c['symbol'])}</a></h2>
    <span class="fullname">{esc(c['name'])}</span>
    {''.join(chips)}
    <span class="spacer"></span>
    <span class="verdict{' strong' if strong else ''}">{'Strong' if strong else 'Watch'}</span>
  </div>
  <div class="meter-block">
    <div class="meter-top"><span class="meter-score">{c['score']:.0f}</span><span class="meter-of">/ 100</span></div>
    {_meter_new(c['parts'], c['score'])}
  </div>
  {_story(c.get('story'), c['score'])}
  <div class="facts">{facts_html}</div>
  <div class="reasons{' split' if warn_html else ''}">
    <div><p class="lab">Why it is here</p><ul class="list">{why}</ul></div>
    {warn_html}
  </div>
</article>"""


def build_new_html(res):
    cands = res["candidates"]
    ts = res["ts"][:16].replace("T", " ")
    strong_n = sum(1 for c in cands if c["score"] >= 60)
    sk = res["skipped"]
    if cands:
        body = f'<div class="board">{"".join(new_card(c, i) for i, c in enumerate(cands, 1))}</div>'
    else:
        body = f"""
<div class="empty">
  <h2>No new coin worth your time right now</h2>
  <p>Checked {res['checked']} fresh coins. They were too small, too big, impossible to sell,
  too quiet, or old and asleep. No signal is better than a bad signal.</p>
</div>"""

    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="refresh" content="900">
<title>Memescan New Coins</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Archivo:wght@600;700;800&family=IBM+Plex+Mono:wght@400;500;600&family=IBM+Plex+Sans:wght@400;500;600&display=swap">
<style>{CSS}{NEW_CSS}</style>
</head><body>
<div class="wrap">
  <header class="masthead">
    <div>
      <h1 class="wordmark">MEME<span>SCAN</span></h1>
      <p class="tagline">New memecoins caught early, with the story behind each one looked up
      on the internet. Signals only &mdash; nothing here is a recommendation.</p>
    </div>
    <div class="stamp">
      <span class="pulse"></span>Last scan <b>{esc(ts)} UTC</b><br>
      Coins under <b>3 days</b> old, or up to 14 days and waking up<br>
      Size <b>$250K&ndash;$20M</b> &middot; at least <b>$50K</b> in the pool
    </div>
  </header>

  <div class="summary">
    <span><span class="k">{len(cands)}</span> on the board</span>
    <span><span class="k">{strong_n}</span> strong</span>
    <span><span class="k">{res['checked']}</span> fresh coins checked</span>
    <span><span class="k">{res.get('researched', 0)}</span> stories looked up this run</span>
    <span>Skipped: {sk['small']} too small &middot; {sk['big']} too big &middot; {sk['illiquid']} unsellable
      &middot; {sk['quiet']} too quiet &middot; {sk['old']} old and asleep</span>
  </div>

  {body}

  <section class="how">
    <h2>How to read this</h2>
    <div class="rules">
      <div><div class="rule-k">New / Waking up</div><div class="rule-v">
        New = made in the last 3 days. Waking up = 3 to 14 days old, was quiet, and is suddenly
        busy. Buy The Cat was quiet for 5 days before it ran.</div></div>
      <div><div class="rule-k">The story</div><div class="rule-v">
        Claude searched the web for where the coin came from, who is talking about it, and
        any scam reports. Strong story = a real joke or event that people share on their own.</div></div>
      <div><div class="rule-k">Score</div><div class="rule-v">
        Price rising 25 &middot; busy trading 25 &middot; buyers 20 &middot; community 15 &middot;
        easy to sell 15. Points come off for hard to sell, already ran, falling now, no community.</div></div>
      <div><div class="rule-k">Not tested yet</div><div class="rule-v">
        This score is new. Every pick is saved, so after a week we can check if it
        actually finds winners. Until then, treat it as a list to look at, not a buy list.</div></div>
    </div>
  </section>

  <p class="foot">
    <b>Exit plan (tested on 26 past picks, 24 Sep 2026):</b> sell HALF when the price doubles, then sell
    the rest when it falls 30% from its highest point. Holding gave most runners back (17 of 26 lost
    more than half); this plan cut that to 5 of 26. Watching early buyers sell did NOT help.<br>
    Sell risk is size divided by money in the pool. Above 60:1 the price you see is not the
    price you get.<br>
    Most new coins go to zero. Signals only. Not financial advice. Never risk money you need.
  </p>
</div>
</body></html>"""
