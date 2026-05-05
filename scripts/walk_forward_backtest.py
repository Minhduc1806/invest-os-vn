#!/usr/bin/env python
from __future__ import annotations
import json,statistics
from collections import defaultdict
from datetime import datetime,timedelta
import argparse
from pathlib import Path
from fdata_adapter import DEFAULT_FDATA, read_amibroker_dat, load_metadata
ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT/'outputs'
def save(p,x): p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf-8')
def md_table(h,rows):
 out=['| '+' | '.join(h)+' |','| '+' | '.join(['---']*len(h))+' |']
 for r in rows: out.append('| '+' | '.join(map(str,r))+' |')
 return '\n'.join(out)
def ma(v,n):
 c=v[-n:] if len(v)>=n else v; return sum(c)/len(c) if c else 0
def rsi(vals,n=14):
 if len(vals)<n+1: return 50
 gains=[]; losses=[]
 for i in range(-n,0):
  ch=vals[i]-vals[i-1]; gains.append(max(ch,0)); losses.append(abs(min(ch,0)))
 al=sum(losses)/n
 return 100 if al==0 else 100-(100/(1+(sum(gains)/n)/al))
def setup(hist):
 closes=[r['close'] for r in hist]; vols=[r['volume'] for r in hist]; c=closes[-1]; m20=ma(closes,20); m50=ma(closes,50); volr=vols[-1]/(ma(vols,20) or 1); rr=rsi(closes)
 if c>m20>m50 and volr>=1.3 and rr<75: return 'breakout'
 if c>m20>m50 and 45<=rr<=65: return 'trend_follow'
 if c>=m20>=m50 and volr<1.1: return 'base_building'
 if c>m50 and c<m20 and rr>=40: return 'pullback'
 return 'avoid'
def market_regime_for(index_rows,i):
 hist=index_rows[:i+1]; closes=[r['close'] for r in hist]; c=closes[-1]; m20=ma(closes,20); m50=ma(closes,50)
 slope_ok=False
 if len(closes)>=60:
  ma20_series=[ma(closes[:j+1],20) for j in range(max(19,len(closes)-10),len(closes))]
  slope_ok=all(ma20_series[k]>ma20_series[k-1] for k in range(1,len(ma20_series)))
 if c<m20: return 'risk_off'
 if c>m20>m50 and slope_ok: return 'risk_on'
 return 'neutral'
def index_map():
 idx_path=DEFAULT_FDATA/'AmiBroker'/'EOD'/'index'/'VNINDEX.dat'
 rows=read_amibroker_dat(idx_path) if idx_path.exists() else []
 return {r['date']:(rows,i) for i,r in enumerate(rows)}
def signal(rows,i,sector,regime,cal=None):
 st=setup(rows[:i+1]); entry=rows[i]['close']; prev=rows[max(0,i-60):i+1]
 if regime in ['risk_off','neutral']: return None
 support=min(r['low'] for r in prev[-20:]); resistance=max(r['high'] for r in prev[-60:]); stop=min(entry*0.95,support*0.985); risk=entry-stop
 if risk<=0 or st=='avoid': return None
 target=max(resistance,entry+risk*2); rr=(target-entry)/risk
 if rr<1.2: return None
 tier='Tier B'
 regime_ok=(regime=='risk_on' and st in ['breakout','trend_follow'])
 if cal and rr>=2 and regime_ok and st in cal.get('preferred_setups_by_regime',{}).get(regime,[]) and sector in cal.get('preferred_sectors_by_regime',{}).get(regime,[]): tier='Tier A'
 fut=rows[i+1:i+21]; out={'setup':st,'sector':sector,'tier':tier,'regime':regime,'rr':round(rr,2),'entry':entry,'stop':stop,'target':target}
 for h in [1,3,5,10,20]:
  w=fut[:h]
  if not w: continue
  close=w[-1]['close']; maxh=max(r['high'] for r in w); minl=min(r['low'] for r in w)
  out[f'T+{h}']={'ret':(close/entry-1)*100,'mae':(minl/entry-1)*100,'target_hit':maxh>=target,'stop_hit':minl<=stop}
 return out
def collect(start,end,cal=None,max_symbols=500):
 meta=load_metadata(DEFAULT_FDATA); im=index_map(); sigs=[]; files=sorted((DEFAULT_FDATA/'AmiBroker'/'EOD'/'stock').glob('*.dat'))[:max_symbols]
 for p in files:
  t=p.stem.upper(); m=meta.get(t,{})
  if m.get('exchange')!='HSX' or m.get('type')!='stock' or 'Quỹ' in m.get('industry','') or t.startswith(('E1','FUE')): continue
  rows=read_amibroker_dat(p); sector=m.get('icb_level_2_name')
  for i in range(220,len(rows)-21):
   dstr=rows[i]['date']; d=datetime.strptime(dstr,'%Y-%m-%d').date()
   if not (start<=d<=end) or dstr not in im: continue
   idx_rows,idx_i=im[dstr]; regime=market_regime_for(idx_rows,idx_i)
   ev=signal(rows,i,sector,regime,cal)
   if ev: sigs.append({**ev,'ticker':t,'date':dstr})
 return sigs
def edge_by(train,key):
 d=defaultdict(list)
 for s in train:
  if 'T+10' in s: d[(s['regime'],s.get(key,'unknown'))].append(s['T+10']['ret'])
 out=defaultdict(dict)
 for (reg,k),vals in d.items():
  if len(vals)>=20: out[reg][k]={'n':len(vals),'avg':statistics.mean(vals),'win':sum(x>0 for x in vals)/len(vals)*100}
 return out
def calibrate(train):
 es=edge_by(train,'setup'); ec=edge_by(train,'sector')
 return {'preferred_setups_by_regime':{reg:[k for k,v in vals.items() if v['avg']>1.0 and v['win']>=48] for reg,vals in es.items()},'preferred_sectors_by_regime':{reg:[k for k,v in vals.items() if v['avg']>1.0 and v['win']>=48] for reg,vals in ec.items()},'train_setup_edge_by_regime':es,'train_sector_edge_by_regime':ec}
def summarize(sigs):
 out={}
 for reg in ['risk_on','neutral','risk_off']:
  for tier in ['Tier A','Tier B']:
   xs=[s for s in sigs if s['tier']==tier and s['regime']==reg]; key=f'{reg}_{tier}'; out[key]={}
   for h in ['T+1','T+3','T+5','T+10','T+20']:
    vals=[s[h]['ret'] for s in xs if h in s]
    if vals: out[key][h]={'n':len(vals),'avg_ret':round(statistics.mean(vals),2),'win_rate':round(sum(v>0 for v in vals)/len(vals)*100,1),'target_hit':round(sum(s[h]['target_hit'] for s in xs if h in s)/len(vals)*100,1),'stop_hit':round(sum(s[h]['stop_hit'] for s in xs if h in s)/len(vals)*100,1),'avg_mae':round(statistics.mean([s[h]['mae'] for s in xs if h in s]),2)}
 return out
def run_split(train_months=9,test_months=3,end_date=None,max_symbols=500):
 test_end=end_date or datetime.now().date(); test_start=test_end-timedelta(days=test_months*30); train_end=test_start-timedelta(days=1); train_start=train_end-timedelta(days=train_months*30)
 train_raw=collect(train_start,train_end,None,max_symbols=max_symbols); cal=calibrate(train_raw); test=collect(test_start,test_end,cal,max_symbols=max_symbols)
 regime_counts={r:sum(1 for s in test if s['regime']==r) for r in ['risk_on','neutral','risk_off']}
 return {'as_of':datetime.now().astimezone().isoformat(timespec='seconds'),'source':'walk_forward_backtest','split':{'train_start':str(train_start),'train_end':str(train_end),'test_start':str(test_start),'test_end':str(test_end)},'rule':'NO NEW BUY unless risk_on; neutral/risk_off -> zero new buys; Tier A requires regime-matched setup and sector learned from train','calibration':cal,'train_signals':len(train_raw),'test_signals':len(test),'test_regime_signal_counts':regime_counts,'test_summary_by_regime':summarize(test),'test_items_sample':test[:500],'test_items_all':test}
def main():
 ap=argparse.ArgumentParser(); ap.add_argument('--train-months',type=int,default=9); ap.add_argument('--test-months',type=int,default=3); ap.add_argument('--end-date'); ap.add_argument('--max-symbols',type=int,default=500); args=ap.parse_args()
 end=datetime.strptime(args.end_date,'%Y-%m-%d').date() if args.end_date else None
 res=run_split(args.train_months,args.test_months,end,args.max_symbols)
 save(OUT/'walk_forward_backtest.json',res)
 sp=res['split']; train_start=sp['train_start']; train_end=sp['train_end']; test_start=sp['test_start']; test_end=sp['test_end']; cal=res['calibration']; regime_counts=res['test_regime_signal_counts']
 md='# Walk-Forward Backtest — Regime Aware\n\n'+f"Train: {train_start} → {train_end} | Test: {test_start} → {test_end}\n\nTrain signals: {res['train_signals']} | Test signals: {res['test_signals']} | Regime counts: {regime_counts}\n\n"
 md+='## Calibration by regime\n```json\n'+json.dumps({'setup':cal['preferred_setups_by_regime'],'sector':cal['preferred_sectors_by_regime']},ensure_ascii=False,indent=2)+'\n```\n\n'
 for key,hs in res['test_summary_by_regime'].items():
  if hs: md+=f'## Test {key}\n'+md_table(['H','N','AvgRet','Win%','Target%','Stop%','MAE'],[[h,v['n'],v['avg_ret'],v['win_rate'],v['target_hit'],v['stop_hit'],v['avg_mae']] for h,v in hs.items()])+'\n\n'
 (OUT/'walk_forward_backtest.md').write_text(md,encoding='utf-8')
 print('OK walk-forward backtest regime-aware')
if __name__=='__main__': main()
