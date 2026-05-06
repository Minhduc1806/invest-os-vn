#!/usr/bin/env python
from __future__ import annotations
import argparse,json,re
from datetime import datetime
from pathlib import Path
from typing import Any
import requests
from bs4 import BeautifulSoup
ROOT=Path(__file__).resolve().parents[1]; LIVE=ROOT/'data_live'
STATEMENTS={'income_statement':('incsta','ket-qua-hoat-dong-kinh-doanh'),'balance_sheet':('bsheet','bao-cao-tai-chinh'),'cash_flow':('cashflow','luu-chuyen-tien-te-gian-tiep')}
def now(): return datetime.now().astimezone().isoformat(timespec='seconds')
def n(s:Any):
 s=str(s or '').replace('\xa0','').replace(',','').strip()
 if not s: return None
 neg=s.startswith('(') and s.endswith(')')
 s=s.strip('()')
 if '.' in s:
  parts=s.split('.')
  if all(x.isdigit() for x in parts): s=''.join(parts)
 try:
  v=float(s) if any(c in s for c in '.eE') else int(s)
  return -v if neg else v
 except Exception: return None
def req(url):
 r=requests.get(url,timeout=30,headers={'User-Agent':'Mozilla/5.0 invest-os-vn'}); r.raise_for_status(); return r.text
def latest_non_null(metric):
 vals=metric.get('values_by_period',{}) if metric else {}
 for k,v in reversed(list(vals.items())):
  if v is not None: return v,k
 return None,None

def latest_metric(rows,pats):
 for pat in pats:
  rg=re.compile(pat,re.I)
  best=None
  for r in rows:
   if rg.search(r.get('label','')):
    vals={k:v for k,v in r.get('values_by_period',{}).items() if v is not None}
    latest,per=latest_non_null({'values_by_period':vals})
    if latest is not None:
     return {'label':r.get('label'),'values_by_period':vals,'latest_value':latest,'latest_period':per}
    if best is None:
     best={'label':r.get('label'),'values_by_period':vals,'latest_value':None,'latest_period':None}
  if best: return best
 return None
def sum_metrics(rows,pats,label):
 parts=[]; periods=[]
 for r in rows:
  if any(re.search(p,r.get('label',''),re.I) for p in pats):
   parts.append(r)
   periods=list(r.get('values_by_period',{}).keys())
 vals={}
 for per in periods:
  nums=[r.get('values_by_period',{}).get(per) for r in parts]
  nums=[x for x in nums if x is not None]
  vals[per]=sum(nums) if nums else None
 latest,lp=latest_non_null({'values_by_period':vals})
 return {'label':label,'values_by_period':{k:v for k,v in vals.items() if v is not None},'latest_value':latest,'latest_period':lp,'derived_from':[r.get('label') for r in parts]} if latest is not None else None
def cell_text(td):
 return td.get_text(' ',strip=True)
def raw_cell_values(td):
 txt=cell_text(td)
 raw=str(td)
 vals=[]
 if txt: vals.append(txt)
 # Raw HTML source fallback: CafeF can render sparkline/hidden fragments in cells; inspect attributes and tags before declaring null.
 for m in re.finditer(r'(?:title|data-value|value)=["\']([^"\']+)["\']', raw, re.I): vals.append(m.group(1))
 for m in re.finditer(r'>\s*([\(\)-]?[\d\.]{3,}(?:,\d+)?)\s*<', raw): vals.append(m.group(1))
 return vals or ['']
def cell_value(td):
 vals=raw_cell_values(td)
 return vals[0] if vals else ''
def align_values(tds,periods):
 vals=[]
 for td in tds[1:1+len(periods)]:
  nums=[n(x) for x in raw_cell_values(td)]
  nums=[x for x in nums if x is not None]
  vals.append(nums[0] if nums else None)
 if len(vals)<len(periods): vals += [None]*(len(periods)-len(vals))
 return vals
def parse_page(ticker,statement,year,quarter,period_type,report_type):
 kind,slug=STATEMENTS[statement]; sym=ticker.lower(); url=f'https://cafef.vn/du-lieu/bao-cao-tai-chinh/{sym}/{kind}/{year}/{quarter}/{period_type}/{report_type}/1/{slug}-.chn'
 html=req(url); soup=BeautifulSoup(html,'html.parser'); table=soup.find('table',id='tableContent'); htab=soup.find('table',id='tblGridData')
 headers=[cell_text(c) for c in htab.find_all(['td','th'])] if htab else []; periods=headers[1:-1] if len(headers)>2 else []
 rows=[]
 if table:
  for tr in table.find_all('tr'):
   tds=tr.find_all('td')
   cells=[cell_value(td) for td in tds]
   if len(cells)<2 or not str(cells[0]).strip(): continue
   vals=align_values(tds,periods)
   rows.append({'code':tr.get('id'),'label':cells[0],'values_by_period':dict(zip(periods,vals)),'raw_cells':cells,'raw_html':str(tr)[:2000]})
 return {'source_url':url,'rows':rows,'row_count':len(rows),'periods':periods,'status':'ok' if rows else 'no_rows'}
def latest_docs(ticker):
 url=f'https://cafef.vn/du-lieu/Ajax/PageNew/FileBCTC.ashx?Symbol={ticker.lower()}&Type=1&Year=0'
 try: data=requests.get(url,timeout=30,headers={'User-Agent':'Mozilla/5.0 invest-os-vn'}).json().get('Data',[])
 except Exception: return []
 docs=[]
 for d in data:
  name=str(d.get('Name','')).lower(); q=int(d.get('Quarter') or 0); y=int(d.get('Year') or 0)
  if q and y: docs.append({'year':y,'quarter':q,'consolidated':('hợp nhất' in name or 'hop nhat' in name),'company':('công ty mẹ' in name or 'rieng' in name),'name':d.get('Name')})
 return docs
def latest_periods_from_index(ticker,limit,consolidated):
 try:
  idx=json.loads((LIVE/'cafef_financial_reports.vn.json').read_text(encoding='utf-8'))
 except Exception: return []
 seen=[]
 for c in idx.get('companies',[]):
  if c.get('ticker')!=ticker: continue
  docs=sorted(c.get('documents',[]), key=lambda d:(int(d.get('year') or 0), int(d.get('quarter') or 0)), reverse=True)
  for d in docs:
   name=str(d.get('name','')).lower()
   is_con=any(x in name for x in ['hợp nhất','hop nhat','h?p nh?t'])
   is_comp=any(x in name for x in ['công ty mẹ','cong ty me','rieng','riêng','c?ng ty m?'])
   if consolidated and not is_con: continue
   if not consolidated and not is_comp: continue
   p=(int(d.get('year') or 0),int(d.get('quarter') or 0))
   if p[0] and p[1] and p not in seen: seen.append(p)
   if len(seen)>=limit: return seen
 return seen
def latest_periods(ticker,limit,consolidated):
 seen=[]
 for d in latest_docs(ticker):
  if consolidated and not d['consolidated']: continue
  if not consolidated and not d['company']: continue
  p=(d['year'],d['quarter'])
  if p not in seen: seen.append(p)
  if len(seen)>=limit: break
 if seen: return seen
 return latest_periods_from_index(ticker,limit,consolidated) or [(datetime.now().year,1)]
def metric(statements,st,pats):
 return latest_metric(statements.get(st,{}).get('rows',[]),pats)
def key_metrics(statements,sector='non_bank'):
 bank_pats={
 'revenue':('income_statement',[r'doanh thu hoạt động tài chính',r'doanh thu thuần']),
 'profit_after_tax':('income_statement',[r'phần lãi lỗ trong công ty liên doanh',r'lợi nhuận sau thuế']),
 'parent_profit':('income_statement',[r'phần lãi lỗ trong công ty liên doanh',r'lợi nhuận sau thuế.*công ty mẹ']),
 'total_assets':('balance_sheet',[r'tổng cộng tài sản',r'tổng tài sản']),
 'total_liabilities':('balance_sheet',[r'nợ phải trả']),
 'equity':('balance_sheet',[r'^d\.?\s*vốn chủ sở hữu',r'vốn chủ sở hữu']),
 'cash':('balance_sheet',[r'tiền và các khoản tương đương tiền',r'tiền mặt']),
 'operating_cash_flow':('cash_flow',[r'lưu chuyển tiền thuần từ hoạt động kinh doanh'])}
 securities_pats={
 'revenue':('income_statement',[r'doanh thu hoạt động tài chính',r'doanh thu thuần']),
 'profit_after_tax':('income_statement',[r'lợi nhuận sau thuế thu nhập',r'lợi nhuận sau thuế',r'phần lãi lỗ trong công ty liên doanh']),
 'parent_profit':('income_statement',[r'lợi nhuận sau thuế.*công ty mẹ',r'lợi nhuận sau thuế thu nhập',r'phần lãi lỗ trong công ty liên doanh']),
 'total_assets':('balance_sheet',[r'tổng cộng tài sản',r'tổng tài sản']),
 'total_liabilities':('balance_sheet',[r'nợ phải trả']),
 'equity':('balance_sheet',[r'^d\.?\s*vốn chủ sở hữu',r'vốn chủ sở hữu']),
 'cash':('balance_sheet',[r'tiền và các khoản tương đương tiền',r'tiền']),
 'operating_cash_flow':('cash_flow',[r'lưu chuyển tiền thuần từ hoạt động kinh doanh'])}
 pats={
 'revenue':('income_statement',[r'doanh thu thuần',r'thu nhập lãi và các khoản thu nhập tương tự',r'doanh thu hoạt động']),
 'profit_after_tax':('income_statement',[r'lợi nhuận sau thuế thu nhập',r'lợi nhuận sau thuế',r'lợi nhuận sau thuế của cổ đông']),
 'parent_profit':('income_statement',[r'lợi nhuận sau thuế công ty mẹ',r'lợi nhuận sau thuế của cổ đông công ty mẹ']),
 'total_assets':('balance_sheet',[r'tổng cộng tài sản',r'tổng tài sản']),
 'total_liabilities':('balance_sheet',[r'nợ phải trả',r'tổng nợ']),
 'equity':('balance_sheet',[r'vốn chủ sở hữu',r'vốn và các quỹ']),
 'cash':('balance_sheet',[r'tiền và các khoản tương đương tiền',r'tiền mặt']),
 'operating_cash_flow':('cash_flow',[r'lưu chuyển tiền thuần từ hoạt động kinh doanh'])}
 if sector=='bank': pats=bank_pats
 elif sector=='securities': pats=securities_pats
 out={}
 for k,(st,ps) in pats.items():
  v=metric(statements,st,ps)
  if v: out[k]=v
 bs=statements.get('balance_sheet',{}).get('rows',[])
 if not out.get('total_assets') or out.get('total_assets',{}).get('latest_value') is None:
  assets=sum_metrics(bs,[r'^i\.\s*tiền và các khoản tương đương tiền',r'^ii\.\s*các khoản đầu tư tài chính ngắn hạn',r'^iii\.\s*các khoản phải thu ngắn hạn',r'^iv\.\s*hàng tồn kho',r'^v\.?\s*tài sản ngắn hạn khác',r'^i\.\s*các khoản phải thu dài hạn',r'^ii\.?\s*tài sản cố định',r'^iii\.\s*bất động sản đầu tư',r'^iv\.\s*tài sản dở dang dài hạn',r'^v\.\s*đầu tư tài chính dài hạn',r'^vi\.\s*tài sản dài hạn khác'],'derived_total_assets') or latest_metric(bs,[r'^tài sản$'])
  if assets: out['total_assets']=assets
 if not out.get('equity'): out['equity']=latest_metric(bs,[r'^d\.?\s*vốn chủ sở hữu',r'^d\.?vốn chủ sở hữu'])
 ratios={}; rev=out.get('revenue',{}).get('latest_value'); pat=out.get('profit_after_tax',{}).get('latest_value') or out.get('parent_profit',{}).get('latest_value'); assets=out.get('total_assets',{}).get('latest_value'); eq=out.get('equity',{}).get('latest_value')
 if rev and pat is not None: ratios['net_margin']=round(pat/rev,4)
 if assets and pat is not None: ratios['roa_period']=round(pat/assets,4)
 if eq and pat is not None: ratios['roe_period']=round(pat/eq,4)
 out['ratios']=ratios; return out
def sector_for(t):
 return 'bank' if t in {'VCB','TCB','MBB','BID','CTG','STB','ACB','VPB','TPB','HDB','SHB','LPB','EIB','VIB','OCB','MSB'} else ('securities' if t in {'SSI','VND','HCM','VCI','SHS','MBS','FTS','CTS','BSI','ORS','AGR','APG','TVS'} else 'non_bank')
def build(t,y,q,report_type):
 statements={}; urls={}; rows={}
 rt=0 if report_type=='consolidated' else 1
 for st in STATEMENTS:
  res=parse_page(t,st,y,q,0,rt); statements[st]=res; urls[st]=res['source_url']; rows[st]=res['rows']
 sector=sector_for(t); km=key_metrics(statements,sector); cov={st:statements[st]['row_count'] for st in statements}; required=['revenue','profit_after_tax','total_assets','equity']; null_metrics=[k for k in required if not km.get(k,{}).get('latest_value')]; valid=all(v>0 for v in cov.values()) and not null_metrics
 return {'ticker':t,'report_type':report_type,'year':y,'quarter':q,'statement_rows':rows,'key_metrics':km,'ratios':km.get('ratios',{}),'coverage':cov,'source_url':urls,'validation':{'required_passed':valid,'no_sample_fallback':True,'sector_mapping':sector,'null_latest_key_metrics':null_metrics},'status':'ok' if valid else 'partial'}
def health(items,warnings):
 rows=[]
 for it in items:
  periods=it.get('periods') or []
  oks=[p for p in periods if p.get('status')=='ok']
  rows.append({'ticker':it.get('ticker'),'report_type':it.get('report_type'),'ok_periods':len(oks),'periods':[f"{p.get('year')}Q{p.get('quarter')}" for p in oks[:5]],'status':'ok' if oks else 'partial_or_missing'})
 return {'status':'ok' if all(r['status']=='ok' for r in rows) else 'partial','ticker_count':len(rows),'ok_ticker_count':sum(1 for r in rows if r['status']=='ok'),'rows':rows,'warning_count':len(warnings),'warnings':warnings[:50]}
def main():
 ap=argparse.ArgumentParser(); ap.add_argument('--tickers',default='PNJ,FPT,MWG,VCB,SSI,HPG,TCB,MBB,VIC,VHM'); ap.add_argument('--periods',type=int,default=1); ap.add_argument('--report-type',choices=['consolidated','company'],default='consolidated'); ap.add_argument('--summary',action='store_true'); args=ap.parse_args()
 items=[]; warnings=[]
 for t in [x.strip().upper() for x in args.tickers.split(',') if x.strip()]:
  rec={'ticker':t,'report_type':args.report_type,'periods':[]}
  periods=latest_periods(t,args.periods,args.report_type=='consolidated')
  for y,q in periods:
   try: rec['periods'].append(build(t,y,q,args.report_type))
   except Exception as e: warnings.append(f'{t}:{y}Q{q}:{e}')
  if rec['periods'] and any(p.get('status')=='ok' for p in rec['periods']):
   rec['periods']=[p for p in rec['periods'] if p.get('status')=='ok']
  if (not rec['periods'] or not any(p.get('status')=='ok' for p in rec['periods'])) and t=='SSI' and args.report_type=='consolidated':
   rec['report_type']='company_fallback'
   for y,q in latest_periods(t,args.periods,False):
    try: rec['periods'].append(build(t,y,q,'company'))
    except Exception as e: warnings.append(f'{t}:company:{y}Q{q}:{e}')
  items.append(rec)
 ok=all(p.get('status')=='ok' for it in items for p in it['periods']) and all(it['periods'] for it in items)
 h=health(items,warnings)
 out={'as_of':now(),'source':'CafeF HTML financial statement tables','status':'ok' if ok else 'partial','items':items,'health_summary':h,'parse_quality':{'required_passed':ok,'warnings':warnings,'no_sample_fallback':True}}
 LIVE.mkdir(exist_ok=True); (LIVE/'cafef_financial_statements_html.vn.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8'); (LIVE/'cafef_financial_statements_health.vn.json').write_text(json.dumps(h,ensure_ascii=False,indent=2),encoding='utf-8'); print(json.dumps(h if args.summary else out,ensure_ascii=True,indent=2)[:5000])
if __name__=='__main__': main()
