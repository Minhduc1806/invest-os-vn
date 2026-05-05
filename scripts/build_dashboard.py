#!/usr/bin/env python
"""Build interactive static HTML dashboard from validated JSON only."""
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
def spark(vals):
    vals=[float(v) for v in vals if v is not None]
    if not vals: return ''
    mn,mx=min(vals),max(vals); span=mx-mn or 1
    pts=' '.join(f'{i*100/max(1,len(vals)-1):.1f},{40-(v-mn)*36/span:.1f}' for i,v in enumerate(vals))
    return f'<svg viewBox="0 0 100 44" class="spark"><polyline points="{pts}"/></svg>'
def bars_table(ohlcv):
    bars=(ohlcv or {}).get('bars',{})
    rows=[]
    if isinstance(bars, dict):
        iterator=bars.items()
    elif isinstance(bars, list):
        grouped={}
        for r in bars:
            if isinstance(r,dict): grouped.setdefault(r.get('ticker') or r.get('symbol') or 'UNKNOWN',[]).append(r)
        iterator=grouped.items()
    else:
        iterator=[]
    for sym,arr in iterator:
        if not arr: continue
        last=arr[-1]; closes=[x.get('close') for x in arr[-30:] if isinstance(x,dict)]
        rows.append((sym,last.get('close'),last.get('volume'),spark(closes)))
    return rows[:80]
def main()->int:
    macro=load(LIVE/'macro_rates_live.vn.json'); fund=load(LIVE/'fundamentals_live.vn.json'); news=load(LIVE/'news_live.vn.json'); market=load(LIVE/'market_snapshot.vn.json'); portfolio=load(LIVE/'portfolio_real.json'); ohlcv=load(LIVE/'fdata_investable_bars.json'); handoff=load(OUT/'multi_agent_handoff.json'); audit=load(OUT/'production_readiness_audit.json'); cafef=load(LIVE/'cafef_financial_statements_html.vn.json')
    checks=[valid(n,d) for n,d in [('macro',macro),('fundamentals',fund),('news',news),('market',market),('portfolio',portfolio),('ohlcv',ohlcv)]]
    bad=[m for ok,m in checks if not ok]
    if bad: raise SystemExit('DASHBOARD_BLOCKED invalid_json: '+','.join(bad))
    rates=macro.get('rates',{}); dives=fund.get('deep_dive',[]); news_items=news.get('items',[])[:20]; idx=market.get('indices',[]); positions=portfolio.get('positions',[]); rows=bars_table(ohlcv); fin_items=(cafef or {}).get('items',[])
    dep_conf=rates.get('deposit_rates',{}).get('confidence')

    fin_rows=[]
    for it in fin_items:
        p0=(it.get('periods') or [{}])[0]; km=p0.get('key_metrics',{}); cov=p0.get('coverage',{})
        def lv(k):
            v=km.get(k,{}); return v.get('latest_value') if isinstance(v,dict) else None
        fin_rows.append((it.get('ticker'), p0.get('year'), p0.get('quarter'), cov, lv('revenue'), lv('profit_after_tax'), lv('total_assets'), lv('equity')))
    html_doc=f'''<!doctype html><html lang="vi"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>InvestOS VN Dashboard</title><style>
body{{font-family:Arial,sans-serif;margin:24px;background:#0b1020;color:#eef2ff}} .grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:16px}} .card{{background:#151b2f;border:1px solid #2b3558;border-radius:12px;padding:16px;margin-bottom:16px}} h1,h2{{margin:0 0 12px}} input,select{{background:#0b1020;color:#eef2ff;border:1px solid #2b3558;border-radius:8px;padding:8px}} table{{width:100%;border-collapse:collapse}} td,th{{border-bottom:1px solid #2b3558;padding:8px;text-align:left}} .ok{{color:#7ee787}} .warn{{color:#ffcc66}} .bad{{color:#ff7b72}} a{{color:#8ab4ff}} .spark{{width:120px;height:44px}} .spark polyline{{fill:none;stroke:#7ee787;stroke-width:3}}
</style></head><body><h1>InvestOS VN Dashboard</h1><p class="ok">Validated JSON only. No sample fallback. Built {esc(now_iso())}</p>
<div class="grid"><section class="card"><h2>Macro</h2><table><tr><th>Policy rate</th><td>{esc(rates.get('policy_rate_pct',{}).get('value'))}%</td></tr><tr><th>USD/VND</th><td>{esc(rates.get('usd_vnd',{}).get('value'))}</td></tr><tr><th>Deposit confidence</th><td class="{'ok' if dep_conf==0.85 else 'warn'}">{esc(dep_conf)}</td></tr></table></section>
<section class="card"><h2>Market</h2><table>{''.join(f'<tr><th>{esc(x.get("symbol"))}</th><td>{esc(x.get("close"))} ({esc(x.get("change_pct"))}%)</td></tr>' for x in idx)}</table></section>
<section class="card"><h2>Portfolio drilldown</h2><table><tr><th>Ticker</th><th>Qty</th><th>Last</th><th>Value</th></tr>{''.join(f'<tr><td>{esc(p.get("ticker"))}</td><td>{esc(p.get("quantity"))}</td><td>{esc(p.get("last_price"))}</td><td>{esc(round(float(p.get("quantity") or 0)*float(p.get("last_price") or 0),0))}</td></tr>' for p in positions)}</table></section>
<section class="card"><h2>Readiness</h2><p>Completion: {esc((audit or {}).get('completion_pct'))}%</p><p>Handoff: {esc((handoff or {}).get('status'))}</p></section></div>
<section class="card"><h2>Investable chart/filter</h2><input id="q" placeholder="filter ticker" onkeyup="filterRows()"> <select id="minp" onchange="filterRows()"><option value="0">all prices</option><option value="10000">price >= 10k</option><option value="50000">price >= 50k</option></select><table id="bars"><tr><th>Ticker</th><th>Close</th><th>Volume</th><th>30-bar chart</th></tr>{''.join(f'<tr data-sym="{esc(s)}" data-price="{esc(c)}"><td>{esc(s)}</td><td>{esc(c)}</td><td>{esc(v)}</td><td>{chart}</td></tr>' for s,c,v,chart in rows)}</table></section>

<section class="card"><h2>Financial statement coverage</h2><table><tr><th>Ticker</th><th>Period</th><th>Rows I/B/C</th><th>Revenue</th><th>Profit</th><th>Assets</th><th>Equity</th></tr>{''.join(f'<tr><td>{esc(t)}</td><td>{esc(y)}Q{esc(q)}</td><td>{esc(cov.get("income_statement"))}/{esc(cov.get("balance_sheet"))}/{esc(cov.get("cash_flow"))}</td><td>{esc(rev)}</td><td>{esc(prof)}</td><td>{esc(assets)}</td><td>{esc(eq)}</td></tr>' for t,y,q,cov,rev,prof,assets,eq in fin_rows)}</table></section>
<section class="card"><h2>Fundamental</h2><table>{''.join(f'<tr><th>{esc(x.get("ticker"))}</th><td>Score {esc(x.get("fundamental_score"))}; {esc("; ".join(x.get("key_risks",[])[:1]))}</td></tr>' for x in dives[:20])}</table></section>
<section class="card"><h2>News</h2><ul>{''.join(f'<li>{esc(x.get("title"))}</li>' for x in news_items)}</ul></section>
<script>function filterRows(){{let q=document.getElementById('q').value.toUpperCase(),m=parseFloat(document.getElementById('minp').value);document.querySelectorAll('#bars tr[data-sym]').forEach(r=>{{let ok=r.dataset.sym.includes(q)&&parseFloat(r.dataset.price||0)>=m;r.style.display=ok?'':'none';}})}}</script></body></html>'''
    OUT.mkdir(exist_ok=True); (OUT/'dashboard.html').write_text(html_doc,encoding='utf-8'); print('DASHBOARD_OK outputs/dashboard.html'); return 0
if __name__=='__main__': raise SystemExit(main())
