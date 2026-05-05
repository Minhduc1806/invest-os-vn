#!/usr/bin/env python
from __future__ import annotations
import argparse,json,re,html
from datetime import datetime
from pathlib import Path
import requests
from bs4 import BeautifulSoup
ROOT=Path(__file__).resolve().parents[1]; LIVE=ROOT/'data_live'
URLS={'income_statement':'incsta','balance_sheet':'bsheet','cash_flow':'cashflow'}
SLUG={'income_statement':'ket-qua-hoat-dong-kinh-doanh','balance_sheet':'can-doi-ke-toan','cash_flow':'luu-chuyen-tien-te'}
def now(): return datetime.now().astimezone().isoformat(timespec='seconds')
def parse_num(s):
 s=(s or '').replace('\xa0','').replace(',','').replace('.','').strip()
 if not s: return None
 try: return int(s)
 except: return None
def parse_page(ticker,statement,year,quarter,period_type=0,report_type=0):
 sym=ticker.lower(); kind=URLS[statement]; slug=SLUG[statement]
 url=f'https://cafef.vn/du-lieu/bao-cao-tai-chinh/{sym}/{kind}/{year}/{quarter}/{period_type}/{report_type}/{slug}-cong-ty-co-phan-{sym}.chn'
 r=requests.get(url,timeout=30,headers={'User-Agent':'Mozilla/5.0 invest-os-vn'}); r.raise_for_status()
 soup=BeautifulSoup(r.text,'html.parser')
 table=soup.find('table',id='tableContent')
 heads=[]
 htab=soup.find('table',id='tblGridData')
 if htab:
  heads=[c.get_text(' ',strip=True) for c in htab.find_all('td')]
 rows=[]
 if table:
  for tr in table.find_all('tr'):
   cells=[td.get_text(' ',strip=True) for td in tr.find_all('td')]
   if len(cells)>=2:
    vals=[parse_num(x) for x in cells[1:4]]
    rows.append({'code':tr.get('id'),'label':cells[0],'values':vals,'raw_cells':cells})
 return {'statement':statement,'url':url,'status':'ok' if rows else 'no_rows','headers':heads,'rows':rows,'row_count':len(rows)}
def main():
 ap=argparse.ArgumentParser(); ap.add_argument('--tickers',default='FPT'); ap.add_argument('--year',type=int,default=2024); ap.add_argument('--quarter',type=int,default=2); args=ap.parse_args()
 out={'as_of':now(),'source':'CafeF rendered HTML financial statement pages; no OCR','items':[]}
 for t in [x.strip().upper() for x in args.tickers.split(',') if x.strip()]:
  rec={'ticker':t,'year':args.year,'quarter':args.quarter,'statements':{}}
  for st in URLS:
   try: rec['statements'][st]=parse_page(t,st,args.year,args.quarter)
   except Exception as e: rec['statements'][st]={'status':'error','error':str(e)}
  out['items'].append(rec)
 LIVE.mkdir(exist_ok=True); (LIVE/'cafef_financial_statements_html.vn.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps(out,ensure_ascii=False,indent=2)[:5000])
if __name__=='__main__': main()
