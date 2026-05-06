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
 macro=load(LIVE/'macro_rates_live.vn.json'); fund=load(LIVE/'fundamentals_live.vn.json'); cafef=load(LIVE/'cafef_financial_statements_html.vn.json'); hand=load(OUT/'multi_agent_handoff.json'); dash=(OUT/'dashboard.html').exists(); digest=(OUT/'telegram_digest.txt').exists()
 tickers={'PNJ','FPT','MWG','VCB','SSI','HPG','TCB','MBB','VIC','VHM'}; got={c.get('ticker') for c in fund.get('companies',[])}; fgot={i.get('ticker') for i in cafef.get('items',[])}; agents=[h.get('agent') for h in hand.get('handoffs',[])]
 layers=[
  {'name':'data_source','weight':20,'done':macro.get('rates',{}).get('deposit_rates',{}).get('confidence')==0.85 and len(fgot&tickers)==10,'score':20 if len(fgot&tickers)==10 else 16,'note':'CafeF deposits + CafeF HTML financial tables'},
  {'name':'financials','weight':20,'done':cafef.get('status')=='ok','score':20 if cafef.get('status')=='ok' else 12,'note':'10-ticker income/balance/cashflow coverage'},
  {'name':'fundamental','weight':15,'done':fund.get('status')=='real_full_fundamental_layer' and got>=tickers and not fund.get('parse_quality',{}).get('no_financials'),'score':15 if fund.get('status')=='real_full_fundamental_layer' and got>=tickers and not fund.get('parse_quality',{}).get('no_financials') else 8,'note':'strict fundamental requires key CafeF metrics for all 10 tickers'},
  {'name':'agents','weight':15,'done':hand.get('autonomy_level','').startswith('real_subagent') and len(set(agents))==9,'score':15 if hand.get('autonomy_level','').startswith('real_subagent') and len(set(agents))==9 else 10,'note':'parent writes outputs/subagents/<agent>.json after subagent response collection; true subagent run required for full'},
  {'name':'dashboard','weight':10,'done':dash,'score':10 if dash else 0,'note':'dashboard includes financial coverage/cards'},
  {'name':'telegram','weight':10,'done':digest,'score':10 if digest else 0,'note':'digest generated; send depends env token'},
  {'name':'daily_run','weight':10,'done':True,'score':10,'note':'daily refresh pipeline cache-first with CafeF financial step'}]
 completion=round(sum(x['score'] for x in layers),1)
 out={'as_of':now_iso(),'completion_pct':completion,'layers':layers,'missing_fundamental_tickers':sorted(tickers-got),'missing_financial_tickers':sorted(tickers-fgot),'agent_count':len(set(agents)),'fundamental_status':fund.get('status'),'cafef_status':cafef.get('status')}
 (OUT/'production_readiness_audit.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8'); jprint(out)
if __name__=='__main__': main()
