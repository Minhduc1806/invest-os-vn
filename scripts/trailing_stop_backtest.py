#!/usr/bin/env python
from __future__ import annotations
import json,statistics
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT/'outputs'
def summarize(vals):
 if not vals: return {'n':0}
 return {'n':len(vals),'avg_ret':round(statistics.mean([x['ret'] for x in vals]),2),'win_rate':round(sum(x['ret']>0 for x in vals)/len(vals)*100,1),'avg_mae':round(statistics.mean([x['mae'] for x in vals]),2),'stop_hit':round(sum(x['exit_reason']!='time_T10' for x in vals)/len(vals)*100,1)}
def main():
 d=json.loads((OUT/'historical_backtest.json').read_text(encoding='utf-8'))
 items=[x for x in d.get('items_sample',[]) if x.get('tier')=='Tier A']
 # historical engine stores sample only; use horizon fields as proxy strategies
 out={'fixed_stop_T10':[],'time_stop_T5_if_negative':[],'breakeven_after_positive_T5':[]}
 for x in items:
  if 'T+10' not in x or 'T+5' not in x: continue
  out['fixed_stop_T10'].append({'ret':x['T+10']['ret'],'mae':x['T+10']['mae'],'exit_reason':'time_T10' if not x['T+10']['stop_hit'] else 'fixed_stop'})
  r5=x['T+5']['ret']; r10=x['T+10']['ret']
  out['time_stop_T5_if_negative'].append({'ret':r5 if r5<0 else r10,'mae':x['T+5']['mae'] if r5<0 else x['T+10']['mae'],'exit_reason':'time_T5_negative' if r5<0 else 'time_T10'})
  out['breakeven_after_positive_T5'].append({'ret':max(r10,0) if r5>0 else r10,'mae':x['T+10']['mae'],'exit_reason':'breakeven' if r5>0 and r10<0 else 'time_T10'})
 res={'source':'trailing_stop_backtest','note':'Proxy test on historical_backtest items_sample Tier A; full implementation should replay bars per signal.','summary':{k:summarize(v) for k,v in out.items()}}
 (OUT/'trailing_stop_backtest.json').write_text(json.dumps(res,ensure_ascii=False,indent=2),encoding='utf-8')
 md='# Trailing Stop Backtest — Tier A T+10 proxy\n\n| Strategy | N | AvgRet % | Win % | Avg MAE % | Stop/Exit % |\n| --- | --- | --- | --- | --- | --- |\n'
 for k,v in res['summary'].items(): md+=f"| {k} | {v['n']} | {v.get('avg_ret')} | {v.get('win_rate')} | {v.get('avg_mae')} | {v.get('stop_hit')} |\n"
 (OUT/'trailing_stop_backtest.md').write_text(md,encoding='utf-8')
 print('OK trailing stop backtest')
if __name__=='__main__': main()
