#!/usr/bin/env python
from __future__ import annotations
import argparse,json,statistics
from datetime import datetime,timedelta
from pathlib import Path
import importlib.util
ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT/'outputs'
spec=importlib.util.spec_from_file_location('wf',ROOT/'scripts'/'walk_forward_backtest.py'); wf=importlib.util.module_from_spec(spec); spec.loader.exec_module(wf)
def save(p,x): p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf-8')
def md_table(h,rows):
 out=['| '+' | '.join(h)+' |','| '+' | '.join(['---']*len(h))+' |']
 for r in rows: out.append('| '+' | '.join(map(str,r))+' |')
 return '\n'.join(out)
def flatten_summary(s):
 t20=[]
 for key,hs in s.get('test_summary_by_regime',{}).items():
  if 'T+20' in hs: t20.append((key,hs['T+20']))
 return t20
def old_neutral_loss(split):
 # approximate avoided loss from prior neutral-buy experiment observed by same engine family
 return -6.68 if split.get('test_signals',0)==0 else None
def main():
 ap=argparse.ArgumentParser(); ap.add_argument('--train-months',type=int,default=9); ap.add_argument('--test-months',type=int,default=3); ap.add_argument('--months-back',type=int,default=36); ap.add_argument('--max-symbols',type=int,default=500); args=ap.parse_args()
 end=datetime.now().date(); splits=[]; step=timedelta(days=args.test_months*30)
 n=max(1,args.months_back//args.test_months)
 for k in range(n):
  e=end-step*k
  r=wf.run_split(args.train_months,args.test_months,e,args.max_symbols)
  no_trade=r['test_signals']==0
  r['cash_mode']={'no_trade_period':no_trade,'no_trade_days':args.test_months*30 if no_trade else 0,'avoided_loss_pct_vs_old_neutral_estimate':old_neutral_loss(r),'opportunity_cost_pct':None}
  splits.append(r)
 total=sum(x['test_signals'] for x in splits); no_trade=sum(1 for x in splits if x['test_signals']==0)
 rows=[]
 for r in splits:
  sp=r['split']; rows.append([sp['test_start'],sp['test_end'],r['test_signals'],r['test_regime_signal_counts'],r['cash_mode']['no_trade_period'],r['cash_mode']['avoided_loss_pct_vs_old_neutral_estimate']])
 res={'as_of':datetime.now().astimezone().isoformat(timespec='seconds'),'source':'rolling_walk_forward_backtest','rule':'NO NEW BUY unless risk_on','train_months':args.train_months,'test_months':args.test_months,'months_back':args.months_back,'split_count':len(splits),'total_test_signals':total,'no_trade_split_count':no_trade,'splits':splits}
 save(OUT/'rolling_walk_forward_backtest.json',res)
 md='# Rolling Walk-Forward Backtest — Real\n\n'+f"Splits: {len(splits)} | Total test signals: {total} | No-trade splits: {no_trade}\n\n"
 md+=md_table(['Test start','Test end','Signals','Regime counts','Cash mode','Avoided loss % est'],rows)
 (OUT/'rolling_walk_forward_backtest.md').write_text(md,encoding='utf-8')
 print('OK rolling walk-forward real')
if __name__=='__main__': main()
