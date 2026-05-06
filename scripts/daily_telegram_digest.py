#!/usr/bin/env python
from __future__ import annotations
import json,argparse
from datetime import datetime
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT/'outputs'; LIVE=ROOT/'data_live'
def now_iso(): return datetime.now().astimezone().isoformat(timespec='seconds')
def load(p): return json.loads(p.read_text(encoding='utf-8')) if p.exists() else None
def okq(d): return isinstance(d,dict) and d.get('parse_quality',{}).get('required_passed',True) and not d.get('parse_quality',{}).get('missing_fields')
def fmt(v):
 try:
  v=float(v); return f'{v/1e12:.2f}tn' if abs(v)>=1e12 else f'{v/1e9:.1f}bn'
 except Exception: return 'n/a'
def fin_lines(cafef,limit=5):
 lines=[]
 for it in (cafef or {}).get('items',[])[:limit]:
  p=(it.get('periods') or [{}])[0]; km=p.get('key_metrics',{}); r=p.get('ratios',{})
  def lv(k): return (km.get(k) or {}).get('latest_value') if isinstance(km.get(k),dict) else None
  lines.append(f"{it.get('ticker')} Q{p.get('quarter')}/{p.get('year')} revenue {fmt(lv('revenue'))}, PAT {fmt(lv('profit_after_tax') or lv('parent_profit'))}, assets {fmt(lv('total_assets'))}, equity {fmt(lv('equity'))}, margin {r.get('net_margin')}")
 return lines
def main():
 ap=argparse.ArgumentParser(); ap.add_argument('--strict',action='store_true'); args=ap.parse_args()
 macro=load(LIVE/'macro_rates_live.vn.json'); news=load(LIVE/'news_live.vn.json'); fund=load(LIVE/'fundamentals_live.vn.json'); cafef=load(LIVE/'cafef_financial_statements_html.vn.json'); report=load(OUT/'eod_market_brief.json') or load(OUT/'eod_vn_report.json')
 bad=[n for n,d in [('macro',macro),('news',news),('fundamentals',fund),('financials',cafef)] if d is None or not okq(d)]
 if args.strict and bad: raise SystemExit('DIGEST_BLOCKED invalid_outputs: '+','.join(bad))
 lines=['VN daily digest',f'as_of: {now_iso()}']
 if bad: lines.append('WARN invalid: '+', '.join(bad))
 if macro:
  r=macro.get('rates',{}); lines.append(f"Macro: policy {r.get('policy_rate_pct',{}).get('value')}%; USD/VND {r.get('usd_vnd',{}).get('value')}; deposits confidence {r.get('deposit_rates',{}).get('confidence')}")
 if fund: lines.append('Fundamental: '+('; '.join(f"{x.get('ticker')} score {x.get('fundamental_score')}" for x in fund.get('deep_dive',[])[:10]) or 'None'))
 fl=fin_lines(cafef,10)
 if fl: lines += ['Financials:'] + fl
 if news: lines.append('News: '+(' | '.join(x.get('title','')[:80] for x in news.get('items',[])[:3]) or 'None'))
 if report:
  if isinstance(report.get('tier_a'),list): lines.append('Tier A: '+', '.join(x.get('ticker',str(x)) for x in report.get('tier_a',[])[:8]))
  elif report.get('top_candidates'): lines.append('Top: '+', '.join(x.get('ticker',str(x)) for x in report.get('top_candidates',[])[:8]))
 lines.append('Rule: validated outputs only; no sample fallback.'); msg='\n'.join(lines); (OUT/'telegram_digest.txt').write_text(msg,encoding='utf-8'); print(msg); return 0
if __name__=='__main__': raise SystemExit(main())
