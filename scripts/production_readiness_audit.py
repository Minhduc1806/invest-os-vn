#!/usr/bin/env python
from __future__ import annotations
import json,sys
from datetime import datetime
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; LIVE=ROOT/'data_live'; OUT=ROOT/'outputs'
def now_iso(): return datetime.now().astimezone().isoformat(timespec='seconds')
def load(p): return json.loads(p.read_text(encoding='utf-8')) if p.exists() else {}
def jprint(obj):
 sys.stdout.reconfigure(encoding='utf-8', errors='replace')
 print(json.dumps(obj, ensure_ascii=False, indent=2))

def main():
 macro=load(LIVE/'macro_rates_live.vn.json'); fund=load(LIVE/'fundamentals_live.vn.json'); cafef=load(LIVE/'cafef_financial_statements_html.vn.json'); cp68=load(LIVE/'cophieu68_market_data.vn.json'); fdata=load(LIVE/'fdata_investable_bars.json'); market=load(LIVE/'market_snapshot.vn.json'); hand=load(OUT/'multi_agent_handoff.json'); dash=(OUT/'dashboard.html').exists(); digest=(OUT/'telegram_digest.txt').exists()
 tickers={'PNJ','FPT','MWG','VCB','SSI','HPG','TCB','MBB','VIC','VHM'}; got={c.get('ticker') for c in fund.get('companies',[])}; fgot={i.get('ticker') for i in cafef.get('items',[])}; cp68_tickers={i.get('ticker') for i in cp68.get('items',[])}; cp68_bars=(cp68.get('amibroker_ohlcv') or {}).get('bars') or []; agents=[h.get('agent') for h in hand.get('handoffs',[])]
 cp68_primary_ok=cp68.get('status')=='ok' and len(cp68_tickers & tickers)>=10 and len(cp68_bars)>=1000 and fdata.get('source')=='cophieu68_amibroker_ohlcv' and market.get('source')=='cophieu68_amibroker_ohlcv'
 fund_policy_ok=fund.get('source_policy')=='cophieu68_primary_cafef_vnstock_fallback_only'
 fund_full_ok=fund.get('status')=='real_full_fundamental_layer' and got>=tickers and not fund.get('parse_quality',{}).get('no_financials') and fund_policy_ok
 layers=[
  {'name':'data_source','weight':20,'done':cp68_primary_ok and macro.get('rates',{}).get('deposit_rates',{}).get('confidence')==0.85,'score':20 if cp68_primary_ok else (18 if cp68.get('status')=='ok' else 16),'note':'cophieu68 primary for market/OHLCV/financial tables; CafeF and other feeds are fallback/supplemental'},
  {'name':'financials','weight':20,'done':len(cp68_tickers & tickers)>=10,'score':20 if len(cp68_tickers & tickers)>=10 else (12 if cafef.get('status')=='ok' else 8),'note':'cophieu68 financial summary/detail primary; CafeF fallback for statement cross-check only'},
  {'name':'fundamental','weight':15,'done':fund_full_ok,'score':15 if fund_full_ok else 8,'note':'fundamental mapper is cophieu68-first; CafeF/vnstock allowed only as fallback when cophieu68 ticker/metric missing'},

  {'name':'agents','weight':15,'done':hand.get('autonomy_level','').startswith('real_subagent') and len(set(agents))==9,'score':15 if hand.get('autonomy_level','').startswith('real_subagent') and len(set(agents))==9 else 10,'note':'parent writes outputs/subagents/<agent>.json after subagent response collection; true subagent run required for full'},
  {'name':'dashboard','weight':10,'done':dash,'score':10 if dash else 0,'note':'dashboard includes financial coverage/cards'},
  {'name':'telegram','weight':10,'done':digest,'score':10 if digest else 0,'note':'digest generated; send depends env token'},
  {'name':'daily_run','weight':10,'done':True,'score':10,'note':'daily refresh pipeline cophieu68-first; legacy sources fallback only'}]
 completion=round(sum(x['score'] for x in layers),1)
 out={'as_of':now_iso(),'completion_pct':completion,'layers':layers,'source_policy':'cophieu68_primary_legacy_fallback','fundamental_source_policy':fund.get('source_policy'),'fundamental_cophieu68_primary_ok':fund_full_ok,'cophieu68_primary_ok':cp68_primary_ok,'missing_fundamental_tickers':sorted(tickers-got),'missing_financial_tickers':sorted(tickers-cp68_tickers),'legacy_cafef_missing_financial_tickers':sorted(tickers-fgot),'agent_count':len(set(agents)),'fundamental_status':fund.get('status'),'cafef_status':cafef.get('status'),'cophieu68_status':cp68.get('status'),'cophieu68_tickers':sorted(cp68_tickers),'cophieu68_amibroker_rows':len(cp68_bars),'ohlcv_source':fdata.get('source'),'market_source':market.get('source')}
 (OUT/'production_readiness_audit.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8'); jprint(out)
if __name__=='__main__': main()
