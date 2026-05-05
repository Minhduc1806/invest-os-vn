#!/usr/bin/env python
r"""
FData universe filter.
Removes trash/illiquid/zero-volume symbols before leadership and signal logic.
Input: full bars from FData adapter. Output: investable universe + exclusion report.
"""
from __future__ import annotations
import argparse, json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple

from fdata_adapter import DEFAULT_FDATA, scan_full_market_bars

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'outputs'
LIVE=ROOT/'data_live'

def save(p:Path,x:Any):
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf-8')

def md_table(headers, rows):
    out=["| "+" | ".join(headers)+" |", "| "+" | ".join(["---"]*len(headers))+" |"]
    for r in rows: out.append("| "+" | ".join(map(str,r))+" |")
    return "\n".join(out)

def classify_exclusion(b:Dict[str,Any], min_price:float, min_volume:int, min_vol_ratio:float, require_ma20:bool)->List[str]:
    reasons=[]
    if b.get('volume',0) <= 0: reasons.append('zero_volume')
    if b.get('volume',0) < min_volume: reasons.append('low_volume')
    if b.get('close',0) < min_price: reasons.append('low_price')
    if b.get('vol_ratio_20d',0) < min_vol_ratio: reasons.append('low_relative_volume')
    if require_ma20 and (not b.get('ma20') or b.get('ma20',0)<=0): reasons.append('missing_ma20')
    if b.get('exchange') not in ['HSX','HNX','UPCOM']: reasons.append('bad_exchange')
    if b.get('industry') in ['', 'unknown', None]: reasons.append('missing_industry')
    if 'Quỹ' in str(b.get('industry','')): reasons.append('fund_etf_industry')
    if str(b.get('ticker','')).startswith(('E1','FUE')): reasons.append('fund_etf_ticker_prefix')
    if b.get('type') and b.get('type') not in ['stock','common_stock']:
        reasons.append('not_common_stock')
    return reasons

def liquidity_score(b:Dict[str,Any])->float:
    # proxy because turnover value not parsed yet; volume + relative volume + exchange quality.
    ex_bonus={'HSX':1.0,'HNX':0.85,'UPCOM':0.65}.get(b.get('exchange'),0.5)
    vol=min(b.get('volume',0)/1_000_000,5)/5
    rv=min(b.get('vol_ratio_20d',0),2)/2
    price=min(max(b.get('close',0),0)/100,1)
    return round(100*(0.45*vol+0.25*rv+0.15*price+0.15*ex_bonus),2)

def filter_universe(bars:List[Dict[str,Any]], min_price:float, min_volume:int, min_vol_ratio:float, require_ma20:bool, min_liquidity_score:float)->Tuple[List[Dict[str,Any]],List[Dict[str,Any]]]:
    kept=[]; excluded=[]
    for b in bars:
        b=dict(b); b['liquidity_score']=liquidity_score(b)
        reasons=classify_exclusion(b,min_price,min_volume,min_vol_ratio,require_ma20)
        if b['liquidity_score'] < min_liquidity_score: reasons.append('low_liquidity_score')
        if reasons:
            excluded.append({'ticker':b.get('ticker'),'exchange':b.get('exchange'),'industry':b.get('industry'),'close':b.get('close'),'volume':b.get('volume'),'vol_ratio_20d':b.get('vol_ratio_20d'),'liquidity_score':b['liquidity_score'],'reasons':reasons})
        else:
            kept.append(b)
    kept.sort(key=lambda x:(x['liquidity_score'],x.get('volume',0)), reverse=True)
    return kept, excluded

def group_summary(bars:List[Dict[str,Any]], key:str)->List[List[Any]]:
    c=Counter([b.get(key) or 'unknown' for b in bars])
    return [[k,v] for k,v in c.most_common(30)]

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--root',default=str(DEFAULT_FDATA))
    ap.add_argument('--timeframe',default='EOD')
    ap.add_argument('--min-price',type=float,default=5.0)
    ap.add_argument('--min-volume',type=int,default=50000)
    ap.add_argument('--min-vol-ratio',type=float,default=0.05)
    ap.add_argument('--min-liquidity-score',type=float,default=25.0)
    ap.add_argument('--require-ma20',action='store_true',default=True)
    args=ap.parse_args()
    bars,warnings=scan_full_market_bars(Path(args.root),args.timeframe)
    kept,excluded=filter_universe(bars,args.min_price,args.min_volume,args.min_vol_ratio,args.require_ma20,args.min_liquidity_score)
    reason_counter=Counter(r for e in excluded for r in e['reasons'])
    result={'as_of':datetime.now().astimezone().isoformat(timespec='seconds'),'source':'fdata_universe_filter','timeframe':args.timeframe,'params':vars(args),'input_universe':len(bars),'kept_count':len(kept),'excluded_count':len(excluded),'keep_rate':round(len(kept)/max(1,len(bars)),4),'reason_counts':reason_counter.most_common(),'kept_by_exchange':group_summary(kept,'exchange'),'kept_by_sector':group_summary(kept,'icb_level_2_name'),'kept':kept,'excluded_sample':excluded[:300],'warnings':warnings}
    save(OUT/'fdata_investable_universe.json',result)
    # compact live file for downstream signals
    save(LIVE/'fdata_investable_bars.json',{'as_of':result['as_of'],'source':'fdata_universe_filter','timeframe':args.timeframe,'bars':kept,'excluded_count':len(excluded),'params':result['params']})
    md="# FData Investable Universe Filter\n\n"
    md+=f"As of: {result['as_of']}\n\nInput: {len(bars)} symbols\nKept: {len(kept)}\nExcluded: {len(excluded)}\nKeep rate: {result['keep_rate']}\n\n"
    md+="## Params\n"+md_table(['Param','Value'], [[k,v] for k,v in result['params'].items()])
    md+="\n\n## Exclusion reasons\n"+md_table(['Reason','Count'], result['reason_counts'])
    md+="\n\n## Kept by exchange\n"+md_table(['Exchange','Count'], result['kept_by_exchange'])
    md+="\n\n## Kept by sector\n"+md_table(['Sector','Count'], result['kept_by_sector'])
    md+="\n\n## Top kept by liquidity score\n"+md_table(['Ticker','Exchange','Industry','Close','Volume','VolRatio20D','LiquidityScore'], [[b['ticker'],b['exchange'],b.get('industry',''),b['close'],b['volume'],b['vol_ratio_20d'],b['liquidity_score']] for b in kept[:50]])
    (OUT/'fdata_investable_universe.md').write_text(md,encoding='utf-8')
    print('OK universe filter')
    print(OUT/'fdata_investable_universe.json')
    print(OUT/'fdata_investable_universe.md')
    print(LIVE/'fdata_investable_bars.json')
if __name__=='__main__': main()
