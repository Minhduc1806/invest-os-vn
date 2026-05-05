#!/usr/bin/env python
"""Build simple static HTML dashboard from validated JSON only."""
from __future__ import annotations
import json, html
from datetime import datetime
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; LIVE=ROOT/'data_live'; OUT=ROOT/'outputs'

def now_iso(): return datetime.now().astimezone().isoformat(timespec='seconds')
def load(p:Path):
    if not p.exists(): return None
    return json.loads(p.read_text(encoding='utf-8'))
def valid(name,d):
    if not isinstance(d,dict): return False, f'{name}:missing'
    pq=d.get('parse_quality',{})
    if pq.get('required_passed') is False: return False, f'{name}:required_failed'
    if pq.get('missing_fields'): return False, f'{name}:missing_fields'
    if d.get('status','').endswith('sample') or 'sample' in str(d.get('source','')).lower(): return False, f'{name}:sample_source'
    return True, ''
def esc(x): return html.escape(str(x if x is not None else ''))
def main()->int:
    macro=load(LIVE/'macro_rates_live.vn.json')
    fund=load(LIVE/'fundamentals_live.vn.json')
    news=load(LIVE/'news_live.vn.json')
    market=load(LIVE/'market_snapshot.vn.json')
    checks=[]
    for n,d in [('macro',macro),('fundamentals',fund),('news',news),('market',market)]: checks.append(valid(n,d))
    bad=[m for ok,m in checks if not ok]
    if bad: raise SystemExit('DASHBOARD_BLOCKED invalid_json: '+','.join(bad))
    rates=macro.get('rates',{})
    dives=fund.get('deep_dive',[])
    news_items=news.get('items',[])[:8]
    idx=market.get('indices',[])
    html_doc=f"""<!doctype html>
<html lang="vi"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>InvestOS VN Dashboard</title>
<style>
body{{font-family:Arial,sans-serif;margin:24px;background:#0b1020;color:#eef2ff}} .grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:16px}} .card{{background:#151b2f;border:1px solid #2b3558;border-radius:12px;padding:16px}} h1,h2{{margin:0 0 12px}} table{{width:100%;border-collapse:collapse}} td,th{{border-bottom:1px solid #2b3558;padding:8px;text-align:left}} .ok{{color:#7ee787}} .warn{{color:#ffcc66}} a{{color:#8ab4ff}}
</style></head><body>
<h1>InvestOS VN Dashboard</h1><p class="ok">Validated JSON only. No sample fallback. Built {esc(now_iso())}</p>
<div class="grid">
<section class="card"><h2>Macro</h2><table>
<tr><th>Policy rate</th><td>{esc(rates.get('policy_rate_pct',{}).get('value'))}%</td></tr>
<tr><th>USD/VND</th><td>{esc(rates.get('usd_vnd',{}).get('value'))}</td></tr>
<tr><th>Deposit confidence</th><td>{esc(rates.get('deposit_rates',{}).get('confidence'))}</td></tr>
</table></section>
<section class="card"><h2>Market</h2><table>{''.join(f'<tr><th>{esc(x.get("symbol"))}</th><td>{esc(x.get("close"))} ({esc(x.get("change_pct"))}%)</td></tr>' for x in idx)}</table></section>
<section class="card"><h2>Fundamental</h2><table>{''.join(f'<tr><th>{esc(x.get("ticker"))}</th><td>Score {esc(x.get("fundamental_score"))}</td></tr>' for x in dives[:10])}</table></section>
<section class="card"><h2>Quality</h2><table>
<tr><th>Macro</th><td>{esc(macro.get('status'))}</td></tr><tr><th>Fund</th><td>{esc(fund.get('status'))}</td></tr><tr><th>News</th><td>{esc(news.get('status'))}</td></tr>
</table></section>
</div>
<section class="card" style="margin-top:16px"><h2>News</h2><ul>{''.join(f'<li>{esc(x.get("title"))}</li>' for x in news_items)}</ul></section>
</body></html>"""
    OUT.mkdir(exist_ok=True)
    (OUT/'dashboard.html').write_text(html_doc,encoding='utf-8')
    print('DASHBOARD_OK outputs/dashboard.html')
    return 0
if __name__=='__main__': raise SystemExit(main())
