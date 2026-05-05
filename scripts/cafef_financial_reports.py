#!/usr/bin/env python
"""Fetch real CafeF financial-statement document index for Vietnam tickers.
CafeF page uses /du-lieu/Ajax/PageNew/FileBCTC.ashx?Symbol=<ticker>&Type=1&Year=0.
This returns official PDF links for BCTC; no mock fallback.
"""
from __future__ import annotations
import argparse, hashlib, json, time, urllib.request
from datetime import datetime
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; LIVE=ROOT/'data_live'; RAW=LIVE/'raw'
URL='https://cafef.vn/du-lieu/Ajax/PageNew/FileBCTC.ashx?Symbol={symbol}&Type=1&Year={year}'

def now_iso(): return datetime.now().astimezone().isoformat(timespec='seconds')
def fetch(symbol:str,year:int=0,timeout:int=25):
    url=URL.format(symbol=symbol.lower(),year=year)
    req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0 invest-os-vn/1.0','Accept':'application/json,text/plain,*/*','Referer':f'https://cafef.vn/du-lieu/hose/{symbol.lower()}-bao-cao-tai-chinh.chn'})
    raw=urllib.request.urlopen(req,timeout=timeout).read()
    text=raw.decode('utf-8','ignore')
    RAW.mkdir(parents=True,exist_ok=True); (RAW/f'cafef_filebctc_{symbol.upper()}_{year}.json').write_text(text,encoding='utf-8')
    d=json.loads(text)
    rows=d.get('Data') or []
    docs=[]
    for r in rows:
        if not isinstance(r,dict): continue
        docs.append({'id':r.get('id'),'ticker':symbol.upper(),'name':r.get('Name'),'time':r.get('Time'),'year':r.get('Year'),'quarter':r.get('Quarter'),'type':r.get('Type'),'format':'pdf' if str(r.get('Link','')).lower().endswith('.pdf') else None,'url':r.get('Link'),'source':'CafeF FileBCTC.ashx'})
    return {'ticker':symbol.upper(),'url':url,'sha256':hashlib.sha256(raw).hexdigest(),'count':len(docs),'documents':docs}

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--tickers',default='FPT,MWG,VCB,SSI'); ap.add_argument('--year',type=int,default=0); ap.add_argument('--sleep',type=float,default=0.6); args=ap.parse_args()
    warnings=[]; companies=[]
    for t in [x.strip().upper() for x in args.tickers.split(',') if x.strip()]:
        try: companies.append(fetch(t,args.year))
        except Exception as e: warnings.append(f'{t}:cafef_filebctc_error:{e}')
        time.sleep(args.sleep)
    out={'as_of':now_iso(),'source':'CafeF FileBCTC Ajax','endpoint':'/du-lieu/Ajax/PageNew/FileBCTC.ashx','companies':companies,'parse_quality':{'required_passed':bool(companies) and all(c['count']>0 for c in companies),'warnings':warnings,'no_sample_fallback':True},'quality_score':0.9 if companies and all(c['count']>0 for c in companies) else 0.6,'status':'real_cafef_financial_statement_documents'}
    LIVE.mkdir(exist_ok=True); (LIVE/'cafef_financial_reports.vn.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(out,ensure_ascii=False,indent=2))
if __name__=='__main__': main()
