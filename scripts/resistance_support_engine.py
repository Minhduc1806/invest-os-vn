#!/usr/bin/env python
from __future__ import annotations
import json,argparse
from datetime import datetime
from pathlib import Path
from typing import Any
from fdata_adapter import DEFAULT_FDATA, read_amibroker_dat
ROOT=Path(__file__).resolve().parents[1]; LIVE=ROOT/'data_live'; OUT=ROOT/'outputs'
def save(p,x): p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf-8')
def md_table(h,rows):
 out=['| '+' | '.join(h)+' |','| '+' | '.join(['---']*len(h))+' |']
 for r in rows: out.append('| '+' | '.join(map(str,r))+' |')
 return '\n'.join(out)
def pivots(rows,look=3):
 highs=[]; lows=[]
 for i in range(look,len(rows)-look):
  w=rows[i-look:i+look+1]
  if rows[i]['high']==max(x['high'] for x in w): highs.append(rows[i])
  if rows[i]['low']==min(x['low'] for x in w): lows.append(rows[i])
 return highs,lows
def calc(ticker, raw_path):
 rows=read_amibroker_dat(Path(raw_path))[-260:]
 if len(rows)<30: return {}
 c=rows[-1]['close']; highs,lows=pivots(rows,3)
 recent_highs=sorted([x['high'] for x in highs if x['high']>c*1.005])[-20:]
 recent_lows=[x for x in lows if x['low']<c*0.995][-10:]
 res=min(recent_highs, default=max(r['high'] for r in rows[-20:]))
 higher=[h for h in recent_highs if h>res*1.03]
 next_res=min(higher, default=max(r['high'] for r in rows[-120:]))
 sup=max([x['low'] for x in recent_lows], default=min(r['low'] for r in rows[-20:]))
 high20=max(r['high'] for r in rows[-20:]); high60=max(r['high'] for r in rows[-60:]); high120=max(r['high'] for r in rows[-120:])
 swing_high=max(rows[-60:], key=lambda x:x['high']); swing_low=min(rows[-60:], key=lambda x:x['low'])
 breakout_zone=f"{res:.2f}-{res*1.02:.2f}"
 supply=f"{res*0.99:.2f}-{res*1.02:.2f}"
 demand=f"{sup*0.98:.2f}-{sup*1.01:.2f}"
 return {'ticker':ticker,'support_nearest':round(sup,2),'resistance_nearest':round(res,2),'next_resistance':round(next_res,2),'rolling_high_20d':round(high20,2),'rolling_high_60d':round(high60,2),'rolling_high_120d':round(high120,2),'swing_high_60d':round(swing_high['high'],2),'swing_high_date':swing_high['date'],'swing_low_60d':round(swing_low['low'],2),'swing_low_date':swing_low['date'],'breakout_zone':breakout_zone,'supply_zone_nearest':supply,'demand_zone_nearest':demand,'close':c}
def main():
 ap=argparse.ArgumentParser(); ap.add_argument('--input',default=str(LIVE/'fdata_investable_bars.json')); args=ap.parse_args()
 data=json.loads(Path(args.input).read_text(encoding='utf-8')); out=[]
 for b in data.get('bars',[]):
  x=calc(b['ticker'],b['raw_path']);
  if x: out.append({**x,'industry':b.get('industry'),'type':b.get('type')})
 res={'as_of':datetime.now().astimezone().isoformat(timespec='seconds'),'source':'resistance_support_engine','universe':'investable','items':out}
 save(OUT/'resistance_support_investable.json',res)
 md='# Resistance / Support — Investable\n\n'+md_table(['Ticker','Close','Support','Resistance','SwingHigh60','SwingLow60','Breakout','Supply','Demand'],[[x['ticker'],x['close'],x['support_nearest'],x['resistance_nearest'],x['swing_high_60d'],x['swing_low_60d'],x['breakout_zone'],x['supply_zone_nearest'],x['demand_zone_nearest']] for x in out])
 (OUT/'resistance_support_investable.md').write_text(md,encoding='utf-8')
 print('OK resistance support')
if __name__=='__main__': main()
