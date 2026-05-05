#!/usr/bin/env python
from __future__ import annotations
import argparse,json,statistics,math
from collections import defaultdict
from datetime import datetime,timedelta
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
def classify(hist):
 closes=[r['close'] for r in hist]; vols=[r['volume'] for r in hist]; c=closes[-1]; m20=ma(closes,20); m50=ma(closes,50); volr=vols[-1]/(ma(vols,20) or 1); rrsi=rsi(closes)
 if c>m20>m50 and volr>=1.3 and rrsi<75: return 'breakout'
 if c>m20>m50 and 45<=rrsi<=65: return 'trend_follow'
 if c>=m20>=m50 and volr<1.1: return 'base_building'
 if c>m50 and c<m20 and rrsi>=40: return 'pullback'
 return 'avoid'
def load_calibration():
 p=OUT/'backtest_calibration.json'
 if not p.exists(): return {'preferred_setups':[],'preferred_sectors':[]}
 return json.loads(p.read_text(encoding='utf-8'))
def eval_signal(rows,i,setup,sector,cal):
 entry=rows[i]['close']; prev=rows[max(0,i-60):i+1]
 support=min(r['low'] for r in prev[-20:]); resistance=max(r['high'] for r in prev[-60:])
 stop=min(entry*0.95,support*0.985); risk=entry-stop
 if risk<=0: return None
 target=max(resistance, entry+risk*2)
 rr=(target-entry)/risk
 bt_ok=(setup in cal.get('preferred_setups',[]) and sector in cal.get('preferred_sectors',[]))
 tier='Tier A' if rr>=2 and setup in ['breakout','base_building','trend_follow'] and bt_ok else 'Tier B' if rr>=1.2 and setup!='avoid' else None
 if not tier: return None
 out={'entry':entry,'stop':stop,'target':target,'rr':round(rr,2),'tier':tier,'setup':setup}
 fut=rows[i+1:i+21]
 for h in [1,3,5,10,20]:
  w=fut[:h]
  if not w: continue
  close=w[-1]['close']; maxh=max(r['high'] for r in w); minl=min(r['low'] for r in w)
  out[f'T+{h}']={'ret':(close/entry-1)*100,'mae':(minl/entry-1)*100,'mfe':(maxh/entry-1)*100,'target_hit':maxh>=target,'stop_hit':minl<=stop}
 return out
def summarize(sigs):
 res={}
 for tier in ['Tier A','Tier B']:
  xs=[s for s in sigs if s['tier']==tier]
  res[tier]={}
  for h in ['T+1','T+3','T+5','T+10','T+20']:
   vals=[x[h]['ret'] for x in xs if h in x]
   if vals:
    res[tier][h]={'n':len(vals),'avg_ret':round(statistics.mean(vals),2),'win_rate':round(sum(v>0 for v in vals)/len(vals)*100,1),'expectancy':round(statistics.mean(vals),2),'target_hit':round(sum(x[h]['target_hit'] for x in xs if h in x)/len(vals)*100,1),'stop_hit':round(sum(x[h]['stop_hit'] for x in xs if h in x)/len(vals)*100,1),'avg_mae':round(statistics.mean([x[h]['mae'] for x in xs if h in x]),2)}
 return res
def group(sigs,key):
 d=defaultdict(list)
 for s in sigs: d[s.get(key,'unknown')].append(s)
 rows=[]
 for k,xs in d.items():
  vals=[s['T+10']['ret'] for s in xs if 'T+10' in s]
  if vals: rows.append([k,len(vals),round(statistics.mean(vals),2),round(sum(v>0 for v in vals)/len(vals)*100,1)])
 return sorted(rows,key=lambda r:r[2],reverse=True)
def main():
 ap=argparse.ArgumentParser(); ap.add_argument('--root',default=str(DEFAULT_FDATA)); ap.add_argument('--months',type=int,default=12); ap.add_argument('--max-symbols',type=int,default=500); ap.add_argument('--save-all-signals',action='store_true'); args=ap.parse_args()
 root=Path(args.root); meta=load_metadata(root); start=datetime.now().date()-timedelta(days=args.months*30); sigs=[]
 cal=load_calibration()
 files=sorted((root/'AmiBroker'/'EOD'/'stock').glob('*.dat'))[:args.max_symbols]
 for p in files:
  t=p.stem.upper(); m=meta.get(t,{})
  if m.get('exchange')!='HSX' or m.get('type')!='stock' or 'Quỹ' in m.get('industry','') or t.startswith(('E1','FUE')): continue
  rows=read_amibroker_dat(p)
  for i in range(220,len(rows)-21):
   if datetime.strptime(rows[i]['date'],'%Y-%m-%d').date()<start: continue
   hist=rows[:i+1]; setup=classify(hist)
   sector=m.get('icb_level_2_name')
   ev=eval_signal(rows,i,setup,sector,cal)
   if ev: sigs.append({**ev,'ticker':t,'date':rows[i]['date'],'sector':sector,'industry':m.get('industry')})
 summary=summarize(sigs); by_setup=group(sigs,'setup'); by_sector=group(sigs,'sector')
 res={'as_of':datetime.now().astimezone().isoformat(timespec='seconds'),'source':'historical_backtest_engine','months':args.months,'calibration_applied':True,'tier_a_rule':'rr>=2 AND setup/sector positive in backtest_calibration','signals':len(sigs),'summary':summary,'by_setup_T10':by_setup,'by_sector_T10':by_sector,'items_sample':sigs[:500]}
 if args.save_all_signals:
  res['items_all']=sigs
 save(OUT/'historical_backtest.json',res)
 md='# Historical Backtest\n\n'+f"Months: {args.months} | Signals: {len(sigs)}\n\n"
 for tier,hs in summary.items(): md+=f'## {tier}\n'+md_table(['H','N','AvgRet','Win%','Expectancy','Target%','Stop%','MAE'],[[h,v['n'],v['avg_ret'],v['win_rate'],v['expectancy'],v['target_hit'],v['stop_hit'],v['avg_mae']] for h,v in hs.items()])+'\n\n'
 md+='## Setup T+10\n'+md_table(['Setup','N','AvgRet','Win%'],by_setup)+'\n\n## Sector T+10\n'+md_table(['Sector','N','AvgRet','Win%'],by_sector[:30])
 (OUT/'historical_backtest.md').write_text(md,encoding='utf-8')
 print('OK historical backtest')
if __name__=='__main__': main()
