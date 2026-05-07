#!/usr/bin/env python
from __future__ import annotations
import argparse, json, math, sys, subprocess
from datetime import datetime, date
from pathlib import Path
from typing import Any, Dict, List

ROOT=Path(__file__).resolve().parents[1]
LIVE=ROOT/'data_live'

def now_iso(): return datetime.now().astimezone().isoformat(timespec='seconds')
def save(p:Path,d:Any): p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8')
def load(p:Path): return json.loads(p.read_text(encoding='utf-8')) if p.exists() else {}
def pct(a,b): return round((a/b-1)*100,2) if b else 0.0
def ma(xs,n):
    c=xs[-n:] if len(xs)>=n else xs
    return round(sum(c)/len(c),2) if c else 0.0
def rsi(vals,n=14):
    if len(vals)<n+1: return 50.0
    gains=[]; losses=[]
    for i in range(-n,0):
        ch=vals[i]-vals[i-1]; gains.append(max(ch,0)); losses.append(abs(min(ch,0)))
    ag=sum(gains)/n; al=sum(losses)/n
    if al==0: return 100.0
    return round(100-(100/(1+ag/al)),2)
def atr_pct(rows,n=14):
    if len(rows)<2: return 0.0
    trs=[]
    for i in range(max(1,len(rows)-n),len(rows)):
        trs.append(max(rows[i]['high']-rows[i]['low'], abs(rows[i]['high']-rows[i-1]['close']), abs(rows[i]['low']-rows[i-1]['close'])))
    return round((sum(trs)/len(trs))/rows[-1]['close']*100,2) if rows[-1]['close'] else 0.0

def bar_from_history(ticker:str, rows:List[Dict[str,Any]], meta=None):
    rows=sorted([r for r in rows if r.get('close')], key=lambda r:r['date'])
    if not rows: return None
    if len(rows)==1:
        prev=rows[-1]
    else:
        prev=rows[-2]
    closes=[r['close'] for r in rows]; vols=[r.get('volume') or 0 for r in rows]
    last=rows[-1]; vol20=sum(vols[-20:])/min(20,len(vols)) if vols else 0
    ret20=pct(closes[-1],closes[-21]) if len(closes)>=21 else 0
    meta=meta or {}
    return {'ticker':ticker,'exchange':meta.get('exchange','VN'),'industry':meta.get('industry','unknown'),'industry_code':meta.get('industry_code',''),'icb_level_1_name':meta.get('icb_level_1_name',''),'icb_level_2_name':meta.get('icb_level_2_name',''),'icb_level_3_name':meta.get('icb_level_3_name',''),'icb_level_4_name':meta.get('icb_level_4_name',''),'date':last['date'],'time':0,'close':last['close'],'change_pct':pct(last['close'],prev['close']),'volume':last.get('volume') or 0,'vol_ratio_20d':round((last.get('volume') or 0)/vol20,2) if vol20 else 0,'ma20':ma(closes,20),'ma50':ma(closes,50),'ma200':ma(closes,200),'rsi14':rsi(closes,14),'atr14_pct':atr_pct(rows,14),'rs_20d':round(ret20/10,2),'raw_path':'cophieu68:quote/history'}

def bars_from_cp68(data:Dict[str,Any], prefer_amibroker=True):
    out=[]; meta={}
    try:
        existing=load(LIVE/'fdata_investable_bars.json')
        meta={b.get('ticker'):b for b in existing.get('bars',[]) if b.get('ticker')}
    except Exception: pass
    if prefer_amibroker:
        am=(data.get('amibroker_ohlcv') or {})
        for r in am.get('bars') or []:
            t=r.get('ticker')
            if not t or not r.get('close'): continue
            m=meta.get(t,{})
            out.append({'ticker':t,'exchange':m.get('exchange','VN'),'industry':m.get('industry','unknown'),'industry_code':m.get('industry_code',''),'icb_level_1_name':m.get('icb_level_1_name',''),'icb_level_2_name':m.get('icb_level_2_name',''),'icb_level_3_name':m.get('icb_level_3_name',''),'icb_level_4_name':m.get('icb_level_4_name',''),'date':r.get('date'),'time':0,'open':r.get('open'),'high':r.get('high'),'low':r.get('low'),'close':r.get('close'),'change_pct':0.0,'volume':r.get('volume') or 0,'vol_ratio_20d':0,'ma20':r.get('close'),'ma50':r.get('close'),'ma200':r.get('close'),'rsi14':50.0,'atr14_pct':0.0,'rs_20d':0.0,'raw_path':'cophieu68:download/_amibroker.php?type=last'})
    if out: return out
    for item in data.get('items') or []:
        t=item.get('ticker')
        rows=(item.get('history') or {}).get('daily_ohlcv') or []
        b=bar_from_history(t,rows,meta.get(t,{}))
        if b: out.append(b)
    return out

def sector_name(b): return b.get('icb_level_2_name') or b.get('industry') or 'Khác'
def build_market(bars:List[Dict[str,Any]], source_as_of:str):
    adv=sum(1 for b in bars if b.get('change_pct',0)>0); dec=sum(1 for b in bars if b.get('change_pct',0)<0); unch=max(0,len(bars)-adv-dec)
    above=sum(1 for b in bars if b.get('ma20') and b.get('close',0)>=b.get('ma20',0)); below=sum(1 for b in bars if b.get('ma20') and b.get('close',0)<b.get('ma20',0))
    buckets={}
    for b in bars: buckets.setdefault(sector_name(b),[]).append(b)
    sectors=[]
    for sec,xs in buckets.items():
        sectors.append({'name':sec,'count':len(xs),'change_pct':round(sum(x.get('change_pct',0) for x in xs)/len(xs),2),'value_bil_vnd':0,'relative_strength_20d':round(sum(x.get('rs_20d',0) for x in xs)/len(xs),2),'advancers':sum(1 for x in xs if x.get('change_pct',0)>0),'decliners':sum(1 for x in xs if x.get('change_pct',0)<0)})
    dates=[b.get('date') for b in bars if b.get('date')]
    last=max(dates) if dates else None
    total_value=sum((float(b.get('close') or 0)*float(b.get('volume') or 0))/1_000_000_000 for b in bars)
    vn_change=round(sum(b.get('change_pct',0) for b in bars)/len(bars),2) if bars else 0.0
    indices=[{'symbol':'VNINDEX','name':'Vietnam all listed proxy from cophieu68 AmiBroker ZIP','close':0,'change_pct':vn_change,'value_bil_vnd':round(total_value,2),'volume':sum(int(b.get('volume') or 0) for b in bars),'source':'cophieu68_amibroker_ohlcv','note':'proxy index derived from cophieu68 full-market OHLCV; official index level not present in AmiBroker ZIP'}]
    return {'as_of':now_iso(),'source':'cophieu68_amibroker_ohlcv','source_as_of':source_as_of,'market':'VN','timeframe':'EOD','last_data_date':last,'stale':False,'universe_size':len(bars),'indices':indices,'breadth':{'advancers':adv,'decliners':dec,'unchanged':unch,'above_ma20':above,'below_ma20':below,'new_high_20d':None,'new_low_20d':None},'sectors':sorted(sectors,key=lambda s:(s['relative_strength_20d'],s['change_pct'],s['count']),reverse=True),'foreign_flow':{'net_value_bil_vnd':0,'top_buy':[],'top_sell':[],'note':'not_in_cophieu68_amibroker_zip'},'derivatives':{'vn30f1m_basis':0,'open_interest':0,'note':'not_available'},'quality_score':0.90 if bars else 0.0,'warnings':['ma/rsi/change_pct limited when using single-day amibroker_last zip','VNINDEX is proxy derived from cophieu68 full-market OHLCV because official index level is not in AmiBroker ZIP']}

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--refresh',action='store_true'); ap.add_argument('--tickers',default='PNJ,FPT,MWG,VCB,SSI,HPG,TCB,MBB,VIC,VHM'); args=ap.parse_args()
    if args.refresh:
        subprocess.run([sys.executable,str(ROOT/'scripts'/'cophieu68_parser.py'),'--tickers',args.tickers,'--history-pages','2','--include-stockonline','--download-amibroker','last','--summary'],cwd=ROOT,check=True)
    data=load(LIVE/'cophieu68_market_data.vn.json')
    bars=bars_from_cp68(data,prefer_amibroker=True)
    if not bars: raise SystemExit('no cophieu68 bars')
    out={'as_of':now_iso(),'source':'cophieu68_amibroker_ohlcv','timeframe':'EOD','bars':bars,'quality_score':0.90,'warnings':['supplemental_source_from_cophieu68']}
    save(LIVE/'fdata_investable_bars.json',out)
    save(LIVE/'fdata_hose_all_bars.json',out)
    save(LIVE/'market_snapshot.vn.json',build_market(bars,data.get('as_of')))
    print(json.dumps({'status':'ok','bars':len(bars),'as_of':out['as_of'],'last_data_date':max(b['date'] for b in bars if b.get('date'))},ensure_ascii=False,indent=2))
if __name__=='__main__': main()
