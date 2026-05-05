#!/usr/bin/env python
r"""HOSE leadership engine using full HOSE universe, no investable filter."""
from __future__ import annotations
import argparse,json
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any,Dict,List
ROOT=Path(__file__).resolve().parents[1]; LIVE=ROOT/'data_live'; OUT=ROOT/'outputs'

def save(p:Path,x:Any): p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf-8')
def md_table(h,rows):
 out=['| '+' | '.join(h)+' |','| '+' | '.join(['---']*len(h))+' |']
 for r in rows: out.append('| '+' | '.join(map(str,r))+' |')
 return '\n'.join(out)
def pct(x): return f'{x:.2f}%'

def sector_stats(bars:List[Dict[str,Any]], key='icb_level_2_name')->List[Dict[str,Any]]:
 buckets=defaultdict(list)
 for b in bars: buckets[b.get(key) or b.get('industry') or 'unknown'].append(b)
 rows=[]
 for name,xs in buckets.items():
  adv=sum(1 for x in xs if x['change_pct']>0); dec=sum(1 for x in xs if x['change_pct']<0); above=sum(1 for x in xs if x.get('ma20') and x['close']>=x['ma20'])
  liq=sum(x.get('volume',0) for x in xs); avg_ch=sum(x['change_pct'] for x in xs)/len(xs); avg_rs=sum(x['rs_20d'] for x in xs)/len(xs)
  breadth=adv/max(1,adv+dec); above_pct=above/max(1,len(xs))
  score=round(100*(0.30*max(min(avg_ch/3,1),-1)+0.25*max(min(avg_rs/2,1),-1)+0.25*breadth+0.20*above_pct),2)
  rows.append({'sector':name,'count':len(xs),'advancers':adv,'decliners':dec,'adv_dec_ratio':round(adv/max(1,dec),2),'avg_change_pct':round(avg_ch,2),'avg_rs20':round(avg_rs,2),'above_ma20_pct':round(above_pct*100,2),'volume':liq,'leadership_score':score})
 rows.sort(key=lambda r:(r['leadership_score'],r['count']),reverse=True); return rows

def stock_scores(bars:List[Dict[str,Any]])->List[Dict[str,Any]]:
 out=[]
 for b in bars:
  trend=1 if b['close']>b.get('ma20',0)>0 and b['ma20']>=b.get('ma50',0) else 0
  vol=min(b.get('vol_ratio_20d',0)/2,1); rs=max(min((b.get('rs_20d',0)+2)/4,1),0); ch=max(min((b.get('change_pct',0)+7)/14,1),0)
  liq=min(b.get('volume',0)/5_000_000,1)
  score=round(100*(0.25*trend+0.25*rs+0.20*vol+0.15*ch+0.15*liq),2)
  x={k:b.get(k) for k in ['ticker','exchange','industry','icb_level_2_name','date','close','change_pct','volume','vol_ratio_20d','ma20','ma50','rsi14','rs_20d']}
  x['leadership_score']=score; out.append(x)
 out.sort(key=lambda x:(x['leadership_score'],x['volume']),reverse=True); return out

def main():
 ap=argparse.ArgumentParser(); ap.add_argument('--input',default=str(LIVE/'fdata_hose_all_bars.json')); ap.add_argument('--top',type=int,default=50); args=ap.parse_args()
 data=json.loads(Path(args.input).read_text(encoding='utf-8')); bars=data.get('bars',[])
 sectors=sector_stats(bars); stocks=stock_scores(bars)
 result={'as_of':datetime.now().astimezone().isoformat(timespec='seconds'),'source':'hose_leadership_engine_full_universe','universe':'HOSE_ALL_LISTED_NO_LIQUIDITY_FILTER','universe_size':len(bars),'sector_leadership':sectors,'stock_leadership':stocks[:args.top],'methodology':{'sector_score':'30% avg_change + 25% RS20 + 25% breadth + 20% above_ma20','stock_score':'25% trend + 25% RS20 + 20% volume_ratio + 15% day_change + 15% liquidity_proxy','warning':'Leadership is data-ranked, not investment recommendation.'}}
 save(OUT/'hose_leadership.json',result)
 md='# HOSE Leadership — Full Listed Universe\n\n'; md+=f"As of: {result['as_of']}\n\nUniverse: {len(bars)} HOSE stocks, no liquidity filter.\n\n"
 md+='## Sector leadership\n'+md_table(['Rank','Sector','Count','Score','Avg %','RS20','A/D','Above MA20 %'],[[i+1,r['sector'],r['count'],r['leadership_score'],pct(r['avg_change_pct']),r['avg_rs20'],r['adv_dec_ratio'],pct(r['above_ma20_pct'])] for i,r in enumerate(sectors)])
 md+='\n\n## Stock leadership top '+str(args.top)+'\n'+md_table(['Rank','Ticker','Industry','Score','%','RS20','VolRatio','Close','Volume'],[[i+1,s['ticker'],s.get('industry',''),s['leadership_score'],pct(s['change_pct']),s['rs_20d'],s['vol_ratio_20d'],s['close'],s['volume']] for i,s in enumerate(stocks[:args.top])])
 md+='\n\nNote: leadership = ranking theo dữ liệu hiện tại, không phải khuyến nghị mua/bán.\n'
 (OUT/'hose_leadership.md').write_text(md,encoding='utf-8')
 print('OK HOSE leadership'); print(OUT/'hose_leadership.md')
if __name__=='__main__': main()
