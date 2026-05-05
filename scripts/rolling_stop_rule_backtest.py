#!/usr/bin/env python
from __future__ import annotations
import argparse,json,statistics,importlib.util
from pathlib import Path
from fdata_adapter import DEFAULT_FDATA, read_amibroker_dat
ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT/'outputs'
spec=importlib.util.spec_from_file_location('rwf',ROOT/'scripts'/'rolling_walk_forward_backtest.py'); rwf=importlib.util.module_from_spec(spec); spec.loader.exec_module(rwf)
def replay(sig, rows):
 idx=next((i for i,r in enumerate(rows) if r['date']==sig['date']),None)
 if idx is None or idx+10>=len(rows): return []
 entry=sig['entry']; init_stop=sig['stop']; target=sig['target']; risk=entry-init_stop
 if risk<=0: return []
 fut=rows[idx+1:idx+11]; res=[]
 for name in ['fixed_stop_T10','breakeven_after_1R','time_stop_T5_if_negative','trailing_low3_after_T3']:
  stop=init_stop; exit_price=fut[-1]['close']; reason='time_T10'; mae=0; day=10
  for d,bar in enumerate(fut,1):
   mae=min(mae,(bar['low']/entry-1)*100)
   if name=='trailing_low3_after_T3' and d>3:
    last3=fut[max(0,d-4):d-1]
    if last3: stop=max(stop,min(x['low'] for x in last3))
   if name=='breakeven_after_1R' and bar['high']>=entry+risk: stop=max(stop,entry)
   if bar['low']<=stop: exit_price=stop; reason='stop'; day=d; break
   if bar['high']>=target: exit_price=target; reason='target'; day=d; break
   if name=='time_stop_T5_if_negative' and d==5 and bar['close']<entry: exit_price=bar['close']; reason='time_T5_negative'; day=d; break
  res.append({'strategy':name,'ret':(exit_price/entry-1)*100,'mae':mae,'exit_reason':reason,'exit_day':day})
 return res
def summ(xs):
 if not xs: return {'n':0}
 return {'n':len(xs),'avg_ret':round(statistics.mean(x['ret'] for x in xs),2),'win_rate':round(sum(x['ret']>0 for x in xs)/len(xs)*100,1),'avg_mae':round(statistics.mean(x['mae'] for x in xs),2),'avg_exit_day':round(statistics.mean(x['exit_day'] for x in xs),1),'target_hit':round(sum(x['exit_reason']=='target' for x in xs)/len(xs)*100,1),'stop_hit':round(sum(x['exit_reason']=='stop' for x in xs)/len(xs)*100,1)}
def main():
 ap=argparse.ArgumentParser(); ap.add_argument('--train-months',type=int,default=9); ap.add_argument('--test-months',type=int,default=3); ap.add_argument('--months-back',type=int,default=24); ap.add_argument('--max-symbols',type=int,default=150); args=ap.parse_args()
 roll=json.loads((OUT/'rolling_walk_forward_backtest.json').read_text(encoding='utf-8')) if (OUT/'rolling_walk_forward_backtest.json').exists() else None
 if not roll or roll.get('max_symbols')!=args.max_symbols:
  # caller should run rolling first; keep current if exists
  pass
 rows_cache={}; allres=[]; split_rows=[]
 for sp in (roll or {}).get('splits',[]):
  sigs=[s for s in sp.get('test_items_all',sp.get('test_items_sample',[])) if s.get('tier')=='Tier A']
  split_res=[]
  for s in sigs:
   t=s['ticker']
   if t not in rows_cache: rows_cache[t]=read_amibroker_dat(DEFAULT_FDATA/'AmiBroker'/'EOD'/'stock'/(t+'.dat'))
   for r in replay(s,rows_cache[t]):
    rr={**r,'ticker':t,'date':s['date'],'split_end':sp['split']['test_end']}; allres.append(rr); split_res.append(rr)
  by={}
  for r in split_res: by.setdefault(r['strategy'],[]).append(r)
  split_rows.append({'split':sp['split'],'tier_a_signals':len(sigs),'summary':{k:summ(v) for k,v in by.items()}})
 by={}
 for r in allres: by.setdefault(r['strategy'],[]).append(r)
 summary={k:summ(v) for k,v in by.items()}
 best=max(summary.items(), key=lambda kv:(kv[1].get('avg_ret',-999)+0.2*kv[1].get('avg_mae',0), kv[1].get('win_rate',0)))[0] if summary else None
 res={'source':'rolling_stop_rule_backtest','status':'done','input':'rolling_walk_forward_backtest OOS Tier A test_items_all','summary':summary,'selected_rule':best,'splits':split_rows}
 (OUT/'rolling_stop_rule_backtest.json').write_text(json.dumps(res,ensure_ascii=False,indent=2),encoding='utf-8')
 md='# Rolling Stop Rule Backtest — OOS Full Replay\n\n| Strategy | N | AvgRet % | Win % | Avg MAE % | Avg exit day | Target % | Stop % |\n| --- | --- | --- | --- | --- | --- | --- | --- |\n'
 for k,v in summary.items(): md+=f"| {k} | {v['n']} | {v.get('avg_ret')} | {v.get('win_rate')} | {v.get('avg_mae')} | {v.get('avg_exit_day')} | {v.get('target_hit')} | {v.get('stop_hit')} |\n"
 md+=f"\nSelected OOS stop rule: `{best}`\n"
 (OUT/'rolling_stop_rule_backtest.md').write_text(md,encoding='utf-8')
 print('OK rolling stop rule OOS full replay')
if __name__=='__main__': main()
