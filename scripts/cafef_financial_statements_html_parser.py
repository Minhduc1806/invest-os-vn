#!/usr/bin/env python
from __future__ import annotations
import argparse,json,re,math
from datetime import datetime
from pathlib import Path
from typing import Any
import requests
from bs4 import BeautifulSoup
ROOT=Path(__file__).resolve().parents[1]; LIVE=ROOT/'data_live'
STATEMENTS={'income_statement':('incsta','ket-qua-hoat-dong-kinh-doanh'),'balance_sheet':('bsheet','can-doi-ke-toan'),'cash_flow':('cashflow','luu-chuyen-tien-te')}
def now(): return datetime.now().astimezone().isoformat(timespec='seconds')
def n(s:Any):
 s=str(s or '').replace('\xa0','').replace(',','').replace('.','').strip()
 if not s: return None
 try: return int(s)
 except: return None
def req(url):
 r=requests.get(url,timeout=30,headers={'User-Agent':'Mozilla/5.0 invest-os-vn'}); r.raise_for_status(); return r.text
def parse_page(ticker,statement,year,quarter,period_type,report_type):
 kind,slug=STATEMENTS[statement]; sym=ticker.lower()
 url=f'https://cafef.vn/du-lieu/bao-cao-tai-chinh/{sym}/{kind}/{year}/{quarter}/{period_type}/{report_type}/{slug}-cong-ty-co-phan-{sym}.chn'
 soup=BeautifulSoup(req(url),'html.parser'); table=soup.find('table',id='tableContent'); htab=soup.find('table',id='tblGridData')
 headers=[c.get_text(' ',strip=True) for c in htab.find_all('td')] if htab else []
 periods=headers[1:-1] if len(headers)>2 else []
 rows=[]
 if table:
  for tr in table.find_all('tr'):
   cells=[td.get_text(' ',strip=True) for td in tr.find_all('td')]
   if len(cells)<2 or not cells[0].strip(): continue
   vals=[n(x) for x in cells[1:1+len(periods)]]
   rows.append({'code':tr.get('id'),'label':cells[0],'values_by_period':dict(zip(periods,vals)),'values':vals,'raw_cells':cells})
 return {'statement':statement,'url':url,'status':'ok' if rows else 'no_rows','headers':headers,'periods':periods,'rows':rows,'row_count':len(rows)}
def latest_docs(ticker):
 url=f'https://cafef.vn/du-lieu/Ajax/PageNew/FileBCTC.ashx?Symbol={ticker.lower()}&Type=1&Year=0'
 try: data=requests.get(url,timeout=30,headers={'User-Agent':'Mozilla/5.0 invest-os-vn'}).json().get('Data',[])
 except Exception: return []
 docs=[]
 for d in data:
  name=str(d.get('Name','')).lower(); q=int(d.get('Quarter') or 0); y=int(d.get('Year') or 0)
  if q and y: docs.append({'year':y,'quarter':q,'consolidated':('hợp nhất' in name or 'hop nhat' in name),'company':('công ty mẹ' in name or 'rieng' in name),'name':d.get('Name'),'link':d.get('Link')})
 return docs
def latest_periods(ticker,limit=4,consolidated=True):
 seen=[]
 for d in latest_docs(ticker):
  if consolidated and not d['consolidated']: continue
  if not consolidated and not d['company']: continue
  p=(d['year'],d['quarter'])
  if p not in seen: seen.append(p)
  if len(seen)>=limit: break
 if not seen:
  y=datetime.now().year
  seen=[(y,q) for q in [1,2,3,4]][:limit]
 return seen
def key_metrics(statements):
 out={}
 def find(st, pats):
  rows=statements.get(st,{}).get('rows',[])
  for pat in pats:
   rg=re.compile(pat,re.I)
   for r in rows:
    if rg.search(r['label']):
     vals={k:v for k,v in r.get('values_by_period',{}).items() if v is not None}
     if vals: return {'label':r['label'],'values_by_period':vals,'latest_value':list(vals.values())[-1],'latest_period':list(vals.keys())[-1]}
 for k,st,pats in [
  ('revenue','income_statement',[r'doanh thu thuần']),('gross_profit','income_statement',[r'lợi nhuận gộp']),('profit_after_tax','income_statement',[r'lợi nhuận sau thuế thu nhập']),('parent_profit','income_statement',[r'lợi nhuận sau thuế công ty mẹ']),
  ('total_assets','balance_sheet',[r'tổng cộng tài sản']),('total_liabilities','balance_sheet',[r'nợ phải trả']),('equity','balance_sheet',[r'vốn chủ sở hữu']),('cash','balance_sheet',[r'tiền và các khoản tương đương tiền']),
  ('operating_cash_flow','cash_flow',[r'lưu chuyển tiền thuần từ hoạt động kinh doanh'])]:
  v=find(st,pats)
  if v: out[k]=v
 rev=out.get('revenue',{}).get('latest_value'); pat=out.get('profit_after_tax',{}).get('latest_value'); assets=out.get('total_assets',{}).get('latest_value'); eq=out.get('equity',{}).get('latest_value')
 ratios={}
 if rev and pat is not None: ratios['net_margin']=round(pat/rev,4)
 if assets and pat is not None: ratios['roa_period']=round(pat/assets,4)
 if eq and pat is not None: ratios['roe_period']=round(pat/eq,4)
 out['ratios']=ratios; return out
def main():
 ap=argparse.ArgumentParser(); ap.add_argument('--tickers',default='FPT,MWG,VCB,SSI'); ap.add_argument('--periods',type=int,default=2); ap.add_argument('--report-type',choices=['consolidated','company'],default='consolidated'); ap.add_argument('--year',type=int); ap.add_argument('--quarter',type=int); args=ap.parse_args()
 items=[]; warnings=[]
 for t in [x.strip().upper() for x in args.tickers.split(',') if x.strip()]:
  periods=[(args.year,args.quarter)] if args.year and args.quarter else latest_periods(t,args.periods,args.report_type=='consolidated')
  trec={'ticker':t,'report_type':args.report_type,'periods':[]}
  for y,q in periods:
   prec={'year':y,'quarter':q,'statements':{}}
   for st in STATEMENTS:
    try: prec['statements'][st]=parse_page(t,st,y,q,0,0)
    except Exception as e: prec['statements'][st]={'statement':st,'status':'error','error':str(e)}; warnings.append(f'{t}:{y}Q{q}:{st}:{e}')
   prec['key_metrics']=key_metrics(prec['statements']); prec['coverage']={k:v.get('row_count',0) for k,v in prec['statements'].items()}
   prec['status']='ok' if all(v.get('status')=='ok' for v in prec['statements'].values()) else 'partial'
   trec['periods'].append(prec)
  items.append(trec)
 ok=all(p['status']=='ok' for it in items for p in it['periods'])
 out={'as_of':now(),'source':'CafeF HTML financial statement tables','status':'ok' if ok else 'partial','items':items,'parse_quality':{'required_passed':ok,'warnings':warnings,'no_sample_fallback':True}}
 LIVE.mkdir(exist_ok=True); (LIVE/'cafef_financial_statements_html.vn.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8'); print(json.dumps(out,ensure_ascii=False,indent=2)[:5000])
if __name__=='__main__': main()
