#!/usr/bin/env python
from __future__ import annotations
import json,statistics
from pathlib import Path
from fdata_adapter import DEFAULT_FDATA, read_amibroker_dat
ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT/'outputs'
def replay(sig, rows):
 idx=next((i for i,r in enumerate(rows) if r['date']==sig['date']),None)
 if idx is None or idx+10>=len(rows): return []
 entry=sig['entry']; init_stop=sig['stop']; target=sig['target']; risk=entry-init_stop
 if risk<=0: return []
 fut=rows[idx+1:idx+11]
 strategies=[]
 for name in ['fixed_stop_T10','trailing_low3_after_T3','breakeven_after_1R','time_stop_T5_if_negative']:
  stop=init_stop; exit_price=fut[-1]['close']; exit_day=10; reason='time_T10'; mae=0; mfe=0
  for d,bar in enumerate(fut,1):
   mae=min(mae,(bar['low']/entry-1)*100); mfe=max(mfe,(bar['high']/entry-1)*100)
   if name=='trailing_low3_after_T3' and d>3:
    last3=fut[max(0,d-4):d-1]
    if last3: stop=max(stop,min(x['low'] for x in last3))
   if name=='breakeven_after_1R' and bar['high']>=entry+risk:
    stop=max(stop,entry)
   if bar['low']<=stop:
    exit_price=stop; exit_day=d; reason='stop'; break
   if bar['high']>=target:
    exit_price=target; exit_day=d; reason='target'; break
   if name=='time_stop_T5_if_negative' and d==5 and bar['close']<entry:
    exit_price=bar['close']; exit_day=d; reason='time_T5_negative'; break
  strategies.append({'strategy':name,'ret':(exit_price/entry-1)*100,'mae':mae,'mfe':mfe,'exit_day':exit_day,'exit_reason':reason})
 return strategies
def summarize(xs):
 if not xs: return {'n':0}
 return {'n':len(xs),'avg_ret':round(statistics.mean(x['ret'] for x in xs),2),'win_rate':round(sum(x['ret']>0 for x in xs)/len(xs)*100,1),'avg_mae':round(statistics.mean(x['mae'] for x in xs),2),'avg_exit_day':round(statistics.mean(x['exit_day'] for x in xs),1),'target_hit_pct':round(sum(x['exit_reason']=='target' for x in xs)/len(xs)*100,1),'stop_hit_pct':round(sum(x['exit_reason']=='stop' for x in xs)/len(xs)*100,1)}
def main():
 d=json.loads((OUT/'historical_backtest.json').read_text(encoding='utf-8'))
 sigs=[x for x in d.get('items_all', d.get('items_sample',[])) if x.get('tier')=='Tier A']
 by_ticker={}
 results=[]
 for s in sigs:
  t=s['ticker'];
  if t not in by_ticker: by_ticker[t]=read_amibroker_dat(DEFAULT_FDATA/'AmiBroker'/'EOD'/'stock'/(t+'.dat'))
  for r in replay(s,by_ticker[t]): results.append({**r,'ticker':t,'date':s['date']})
 groups={}
 for r in results: groups.setdefault(r['strategy'],[]).append(r)
 summary={k:summarize(v) for k,v in groups.items()}
 # choose by avg_ret first, then MAE penalty
 best=max(summary.items(), key=lambda kv:(kv[1].get('avg_ret',-999)+kv[1].get('avg_mae',0)*0.15, kv[1].get('win_rate',0)))[0] if summary else None
 res={'source':'trailing_stop_full_replay','universe':'historical_backtest all Tier A if available','holding_window':'T+10','summary':summary,'selected_rule':best,'selection_logic':'maximize avg_ret with MAE penalty; full bar replay high/low stop/target path','items_sample':results[:1000]}
 (OUT/'trailing_stop_full_replay.json').write_text(json.dumps(res,ensure_ascii=False,indent=2),encoding='utf-8')
 md='# Trailing Stop Full Replay — Tier A T+10\n\n| Strategy | N | AvgRet % | Win % | Avg MAE % | Avg exit day | Target % | Stop % |\n| --- | --- | --- | --- | --- | --- | --- | --- |\n'
 for k,v in summary.items(): md+=f"| {k} | {v['n']} | {v['avg_ret']} | {v['win_rate']} | {v['avg_mae']} | {v['avg_exit_day']} | {v['target_hit_pct']} | {v['stop_hit_pct']} |\n"
 md+=f"\n## Selected Tier A stop rule\n`{best}`\n"
 (OUT/'trailing_stop_full_replay.md').write_text(md,encoding='utf-8')
 print('OK trailing stop full replay')
if __name__=='__main__': main()
