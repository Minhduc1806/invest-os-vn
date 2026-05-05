#!/usr/bin/env python
"""Create production Telegram digest from validated outputs.
No sending here; channel delivery reads outputs/telegram_digest.txt.
"""
from __future__ import annotations
import json, argparse
from datetime import datetime
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT/'outputs'; LIVE=ROOT/'data_live'

def now_iso(): return datetime.now().astimezone().isoformat(timespec='seconds')
def load(p:Path): return json.loads(p.read_text(encoding='utf-8')) if p.exists() else None
def ok_quality(d):
    if not isinstance(d,dict): return False
    pq=d.get('parse_quality',{})
    return pq.get('required_passed',True) and not pq.get('missing_fields')
def main()->int:
    ap=argparse.ArgumentParser(); ap.add_argument('--strict',action='store_true'); args=ap.parse_args()
    macro=load(LIVE/'macro_rates_live.vn.json'); news=load(LIVE/'news_live.vn.json'); fund=load(LIVE/'fundamentals_live.vn.json')
    report=load(OUT/'eod_market_brief.json') or load(OUT/'eod_vn_report.json')
    bad=[]
    for name,d in [('macro',macro),('news',news),('fundamentals',fund)]:
        if d is None or not ok_quality(d): bad.append(name)
    if args.strict and bad:
        raise SystemExit('DIGEST_BLOCKED invalid_outputs: '+','.join(bad))
    lines=['VN daily digest',f'as_of: {now_iso()}']
    if bad: lines.append('WARN invalid: '+', '.join(bad))
    if macro:
        pr=macro.get('rates',{}).get('policy_rate_pct',{}).get('value')
        usd=macro.get('rates',{}).get('usd_vnd',{}).get('value')
        dep=macro.get('rates',{}).get('deposit_rates',{})
        lines.append(f"Macro: policy {pr}%; USD/VND {usd}; deposits confidence {dep.get('confidence')}")
    if fund:
        dives=fund.get('deep_dive',[])[:5]
        lines.append('Fundamental: '+('; '.join(f"{x.get('ticker')} score {x.get('fundamental_score')}" for x in dives) or 'None'))
    if news:
        items=news.get('items',[])[:3]
        lines.append('News: '+(' | '.join(x.get('title','')[:80] for x in items) or 'None'))
    if report:
        if isinstance(report.get('tier_a'),list): lines.append('Tier A: '+', '.join(x.get('ticker',str(x)) for x in report.get('tier_a',[])[:8]))
        elif report.get('top_candidates'): lines.append('Top: '+', '.join(x.get('ticker',str(x)) for x in report.get('top_candidates',[])[:8]))
    lines.append('Rule: validated outputs only; no sample fallback.')
    msg='\n'.join(lines)
    (OUT/'telegram_digest.txt').write_text(msg,encoding='utf-8')
    print(msg)
    return 0
if __name__=='__main__': raise SystemExit(main())
