#!/usr/bin/env python
r"""
Full-market breadth from FData.
Scans all AmiBroker stock .dat files and outputs market breadth, exchange breadth, sector breadth, top/bottom movers.
"""
from __future__ import annotations
import argparse, json
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from fdata_adapter import DEFAULT_FDATA, LIVE, scan_full_market_bars, build_market_fdata

ROOT=Path(__file__).resolve().parents[1]

def save(p:Path,x:Any):
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf-8')

def md_table(headers, rows):
    out=["| "+" | ".join(headers)+" |", "| "+" | ".join(["---"]*len(headers))+" |"]
    for r in rows: out.append("| "+" | ".join(map(str,r))+" |")
    return "\n".join(out)

def pct(x): return f"{x:.2f}%"

def group_stats(bars:List[Dict[str,Any]], key:str)->List[Dict[str,Any]]:
    buckets=defaultdict(list)
    for b in bars: buckets[b.get(key) or 'unknown'].append(b)
    rows=[]
    for name,xs in buckets.items():
        adv=sum(1 for x in xs if x['change_pct']>0); dec=sum(1 for x in xs if x['change_pct']<0); unch=len(xs)-adv-dec
        above=sum(1 for x in xs if x['ma20'] and x['close']>=x['ma20']); below=sum(1 for x in xs if x['ma20'] and x['close']<x['ma20'])
        rows.append({'name':name,'count':len(xs),'advancers':adv,'decliners':dec,'unchanged':unch,'adv_dec_ratio':round(adv/max(1,dec),2),'avg_change_pct':round(sum(x['change_pct'] for x in xs)/len(xs),2),'above_ma20':above,'below_ma20':below,'above_ma20_pct':round(above/max(1,above+below)*100,2),'avg_rs20':round(sum(x['rs_20d'] for x in xs)/len(xs),2),'total_volume':sum(x['volume'] for x in xs)})
    rows.sort(key=lambda r:(r['avg_rs20'],r['avg_change_pct'],r['adv_dec_ratio'],r['count']), reverse=True)
    return rows

def load_investable_bars(path: Path) -> tuple[list[dict[str,Any]], list[str]]:
    if not path.exists():
        return [], [f'investable_file_missing: {path}']
    data=json.loads(path.read_text(encoding='utf-8'))
    return data.get('bars',[]), [f"using_investable_universe: {path}", f"excluded_count: {data.get('excluded_count')}"]

def market_from_bars(bars:List[Dict[str,Any]], timeframe:str, warnings:List[str])->Dict[str,Any]:
    adv=sum(1 for b in bars if b['change_pct']>0); dec=sum(1 for b in bars if b['change_pct']<0); unch=max(0,len(bars)-adv-dec)
    above=sum(1 for b in bars if b.get('ma20') and b['close']>=b['ma20']); below=sum(1 for b in bars if b.get('ma20') and b['close']<b['ma20'])
    return {'as_of':datetime.now().astimezone().isoformat(timespec='seconds'),'source':'fdata_investable_universe_breadth','market':'VN','timeframe':timeframe,'universe_size':len(bars),'breadth':{'advancers':adv,'decliners':dec,'unchanged':unch,'above_ma20':above,'below_ma20':below,'new_high_20d':None,'new_low_20d':None},'warnings':warnings}

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--root',default=str(DEFAULT_FDATA)); ap.add_argument('--timeframe',default='EOD'); ap.add_argument('--top',type=int,default=30)
    ap.add_argument('--investable',default=str(LIVE/'fdata_investable_bars.json'),help='Use filtered investable universe instead of full raw universe')
    ap.add_argument('--raw-full',action='store_true',help='Override: scan all raw FData stock files')
    args=ap.parse_args(); root=Path(args.root)
    if args.raw_full:
        bars,warnings=scan_full_market_bars(root,args.timeframe)
        market=build_market_fdata([],root,args.timeframe,full_market=True,stale_days=3)
    else:
        bars,warnings=load_investable_bars(Path(args.investable))
        market=market_from_bars(bars,args.timeframe,warnings)
    bars_sorted_up=sorted(bars,key=lambda b:b['change_pct'],reverse=True)[:args.top]
    bars_sorted_dn=sorted(bars,key=lambda b:b['change_pct'])[:args.top]
    by_exchange=group_stats(bars,'exchange')
    by_sector=group_stats(bars,'icb_level_2_name')
    by_industry=group_stats(bars,'industry')
    dates={}
    for b in bars: dates[b['date']]=dates.get(b['date'],0)+1
    result={'as_of':datetime.now().astimezone().isoformat(timespec='seconds'),'source':'fdata_investable_breadth' if not args.raw_full else 'fdata_amibroker_dat_full_breadth','timeframe':args.timeframe,'universe_size':len(bars),'last_dates':sorted(dates.items(),key=lambda x:x[1],reverse=True)[:10],'market':market,'exchange_breadth':by_exchange,'sector_breadth':by_sector,'industry_breadth':by_industry,'top_gainers':bars_sorted_up,'top_losers':bars_sorted_dn,'warnings':warnings}
    out_json=ROOT/'outputs'/'fdata_breadth_full.json'; save(out_json,result)
    md="# FData Full Breadth\n\n"
    md+=f"As of: {result['as_of']}\n\nUniverse: {len(bars)} symbols\n\n"
    br=market['breadth']; md+=md_table(['Metric','Value'], [['Advancers',br['advancers']],['Decliners',br['decliners']],['Unchanged',br['unchanged']],['Above MA20',br['above_ma20']],['Below MA20',br['below_ma20']]])
    md+='\n\n## Exchange breadth\n'+md_table(['Exchange','Count','Adv','Dec','A/D','Avg %','Above MA20 %'], [[r['name'],r['count'],r['advancers'],r['decliners'],r['adv_dec_ratio'],pct(r['avg_change_pct']),pct(r['above_ma20_pct'])] for r in by_exchange])
    md+='\n\n## Sector breadth (ICB level 2)\n'+md_table(['Sector','Count','Adv','Dec','A/D','Avg %','RS20','Above MA20 %'], [[r['name'],r['count'],r['advancers'],r['decliners'],r['adv_dec_ratio'],pct(r['avg_change_pct']),r['avg_rs20'],pct(r['above_ma20_pct'])] for r in by_sector[:30]])
    md+='\n\n## Top gainers\n'+md_table(['Ticker','Exchange','Industry','%','Close','Volume'], [[b['ticker'],b['exchange'],b.get('industry',''),pct(b['change_pct']),b['close'],b['volume']] for b in bars_sorted_up[:20]])
    md+='\n\n## Top losers\n'+md_table(['Ticker','Exchange','Industry','%','Close','Volume'], [[b['ticker'],b['exchange'],b.get('industry',''),pct(b['change_pct']),b['close'],b['volume']] for b in bars_sorted_dn[:20]])
    out_md=ROOT/'outputs'/'fdata_breadth_full.md'; out_md.write_text(md,encoding='utf-8')
    print('OK full breadth'); print(out_json); print(out_md)
if __name__=='__main__': main()
