#!/usr/bin/env python
from __future__ import annotations
import argparse, json, math, re, sys
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT=Path(__file__).resolve().parents[1]; LIVE=ROOT/'data_live'; OUT=ROOT/'outputs'; CACHE=LIVE/'cache'
CP68_PATH=LIVE/'cophieu68_market_data.vn.json'
CAFEF_PATH=LIVE/'cafef_financial_statements_html.vn.json'

def now_iso(): return datetime.now().astimezone().isoformat(timespec='seconds')
def save(p:Path,d:Any): p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8')
def load(p:Path): return json.loads(p.read_text(encoding='utf-8')) if p.exists() else None
def clean(s,limit=900): return re.sub(r'\s+',' ',str(s or '')).strip()[:limit]
def num(x):
    try:
        if x is None or x=='': return None
        text=str(x).replace(',','').replace('%','').strip()
        if text.upper() in {'N/A','NA','NONE','NULL','-'}: return None
        v=float(text)
        return None if math.isnan(v) else v
    except Exception: return None
def pct(a,b): return round((a/b-1)*100,2) if a is not None and b not in (None,0) else None
def latest_period(periods:list[str], prefer_year=True):
    if not periods: return None
    years=[p for p in periods if str(p).startswith('Năm ')]
    return years[0] if prefer_year and years else periods[0]

def latest_period_with_values(rows:list[dict[str,Any]], periods:list[str], names:list[str]):
    for p in periods or []:
        if row_value(rows,names,p) is not None:
            return p
    return None
def norm_label(s:str)->str:
    s=str(s or '').lower().strip()
    s=re.sub(r'^\d+\.\s*','',s)
    s=re.sub(r'\s+',' ',s)
    return s

def row_value(rows:list[dict[str,Any]], names:list[str], period:str|None):
    if not period: return None
    names_l=[n.lower() for n in names]
    labels=[(norm_label(r.get('label')),r) for r in rows or []]
    for label,r in labels:
        if label in names_l:
            return num((r.get('values_by_period') or {}).get(period))
    for label,r in labels:
        if any(n in label for n in names_l):
            return num((r.get('values_by_period') or {}).get(period))
    return None
def cp68_profile(item:dict[str,Any])->dict[str,Any]:
    fields=((item.get('profile') or {}).get('fields') or {})
    listed=num(fields.get('KL niêm yết')); outstanding=num(fields.get('KL lưu hành'))
    mcap=num(fields.get('Vốn thị trường'))
    return {
        'company_name':fields.get('Tên công ty'),
        'trading_name':fields.get('Tên giao dịch'),
        'address':fields.get('Địa chỉ'),
        'phone':fields.get('Điện thoại'),
        'email':fields.get('Email'),
        'website':fields.get('Website'),
        'listing_date':fields.get('Ngày niêm yết'),
        'listed_shares':listed,
        'outstanding_shares':outstanding,
        'market_cap_mil_vnd':mcap,
        'foreign_buy':fields.get('NN mua'),
        'foreign_ownership':fields.get('NN sở hữu'),
        'source_url':(item.get('profile') or {}).get('source_url'),
    }
def cp68_metrics(item:dict[str,Any])->tuple[dict[str,Any],list[str]]:
    fin=item.get('financials') or {}; summary=fin.get('summary') or {}; rows=summary.get('rows') or []; periods=summary.get('periods') or []
    period=latest_period(periods,prefer_year=True); warnings=[]
    balance_period=latest_period_with_values(rows,periods,['tổng cộng tài sản','tổng tài sản','vốn chủ sở hữu']) or period
    revenue=row_value(rows,['doanh thu bán hàng','doanh thu thuần'],period)
    gross_profit=row_value(rows,['lợi nhuận gộp'],period)
    operating_profit=row_value(rows,['lợi nhuận thuần từ hoạt động kinh doanh'],period)
    pretax_profit=row_value(rows,['tổng lợi nhuận trước thuế','lợi nhuận trước thuế'],period)
    profit_after_tax=row_value(rows,['lợi nhuận sau thuế'],period)
    parent_profit=row_value(rows,['lợi nhuận sau thuế của công ty mẹ'],period)
    current_assets=row_value(rows,['tổng tài sản ngắn hạn'],balance_period)
    total_assets=row_value(rows,['tổng cộng tài sản','tổng tài sản'],balance_period)
    liabilities=row_value(rows,['nợ phải trả','tổng nợ'],balance_period)
    equity=row_value(rows,['vốn chủ sở hữu','nguồn vốn chủ sở hữu'],balance_period)
    eps=row_value(rows,['eps'],period)
    bvps=row_value(rows,['book value','giá trị sổ sách'],period)
    metrics={
        'period':period,
        'balance_period':balance_period,
        'source':'cophieu68_financial_summary',
        'source_url':summary.get('source_url'),
        'revenue':{'latest_value':revenue,'unit':'million_vnd'},
        'gross_profit':{'latest_value':gross_profit,'unit':'million_vnd'},
        'operating_profit':{'latest_value':operating_profit,'unit':'million_vnd'},
        'pretax_profit':{'latest_value':pretax_profit,'unit':'million_vnd'},
        'profit_after_tax':{'latest_value':profit_after_tax,'unit':'million_vnd'},
        'parent_profit':{'latest_value':parent_profit,'unit':'million_vnd'},
        'current_assets':{'latest_value':current_assets,'unit':'million_vnd'},
        'total_assets':{'latest_value':total_assets,'unit':'million_vnd'},
        'liabilities':{'latest_value':liabilities,'unit':'million_vnd'},
        'equity':{'latest_value':equity,'unit':'million_vnd'},
        'eps':{'latest_value':eps,'unit':'vnd'},
        'bvps':{'latest_value':bvps,'unit':'vnd'},
        'ratios':{
            'gross_margin_pct':pct(gross_profit,revenue),
            'net_margin_pct':pct(profit_after_tax,revenue),
            'roe_pct':pct(profit_after_tax,equity),
            'debt_to_equity':round(liabilities/equity,2) if liabilities is not None and equity not in (None,0) else None,
        },
        'raw_rows':rows,
    }
    required={'revenue':revenue,'profit_after_tax':profit_after_tax,'total_assets':total_assets,'equity':equity}
    miss=[k for k,v in required.items() if v is None]
    if miss: warnings.append('cophieu68_financial_missing:'+','.join(miss))
    return metrics,warnings
def cp68_company(item:dict[str,Any])->tuple[dict[str,Any],list[str]]:
    ticker=item.get('ticker'); warnings=list(item.get('warnings') or [])
    profile=cp68_profile(item); metrics,w=cp68_metrics(item); warnings+=w
    business=profile.get('company_name') or profile.get('trading_name') or ticker
    financial_ok=not any(str(x).startswith('cophieu68_financial_missing') for x in warnings)
    c={
        'ticker':ticker,
        'exchange':'VN',
        'business':clean(business,1400),
        'profile':profile,
        'financials':{'cophieu68':item.get('financials') or {}},
        'financial_metrics':metrics,
        'valuation':{},
        'risks':[] if financial_ok else ['cophieu68_financial_missing_or_partial'],
        'source_quality':'primary_cophieu68_profile_financials_real' if financial_ok else 'primary_cophieu68_profile_partial_financials',
        'confidence':0.88 if financial_ok else 0.68,
    }
    return c,warnings
def load_cp68(tickers:list[str])->tuple[dict[str,dict[str,Any]],list[str]]:
    d=load(CP68_PATH) or {}; warnings=[]
    if d.get('status')!='ok': warnings.append(f"cophieu68_status={d.get('status')}")
    items={str(i.get('ticker')).upper():i for i in d.get('items',[]) if i.get('ticker')}
    return {t:items[t] for t in tickers if t in items},warnings
def load_cafef_fallback():
    d=load(CAFEF_PATH) or {}; out={}
    for item in d.get('items',[]): out[item.get('ticker')]=item
    return out
def vnstock_profile_fallback(ticker):
    cp=CACHE/f'company_profile_{ticker}.json'
    try:
        import vnstock
        c=vnstock.Company(symbol=ticker); rows=c.overview().to_dict('records') if hasattr(c,'overview') else []
        if rows:
            save(cp,{'as_of':now_iso(),'ticker':ticker,'rows':rows,'source':'vnstock.Company.overview_fallback'}); return rows[0],[]
        raise RuntimeError('overview_empty')
    except Exception as e:
        cached=load(cp)
        if cached and cached.get('rows'): return cached['rows'][0],[f'{ticker}:vnstock_profile_cache_fallback_used:{e}']
        return None,[f'{ticker}:vnstock_profile_fallback_failed:{e}']
def fallback_company(ticker,cafef):
    warnings=[f'{ticker}:cophieu68_missing_used_fallback']
    row,w=vnstock_profile_fallback(ticker); warnings+=w
    profile={'source':'vnstock_fallback','raw':row or {}}
    c={'ticker':ticker,'exchange':None,'business':clean((row or {}).get('companyProfile') or ticker,1400),'profile':profile,'financials':{},'financial_metrics':{},'valuation':{},'risks':['not_from_cophieu68_primary'],'source_quality':'fallback_vnstock_profile_only','confidence':0.55}
    if ticker in cafef:
        c['financials']['cafef_html_fallback']=cafef[ticker]; c['source_quality']='fallback_vnstock_profile_plus_cafef_financials'; c['confidence']=0.62
    return c,warnings
def score_company(c):
    p=c.get('profile',{}); score=50
    if p.get('outstanding_shares') or p.get('listed_shares'): score+=8
    if p.get('market_cap_mil_vnd'): score+=7
    if c.get('business'): score+=10
    if c.get('financial_metrics',{}).get('revenue',{}).get('latest_value') is not None: score+=15
    ratios=c.get('financial_metrics',{}).get('ratios',{}) if isinstance(c.get('financial_metrics'),dict) else {}
    return {'ticker':c['ticker'],'fundamental_score':min(score,90),'thesis':clean(c.get('business'),260),'key_risks':c.get('risks',[])[:3],'ratios':ratios,'source_quality':c.get('source_quality')}
def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--tickers',default='PNJ,FPT,MWG,VCB,SSI,HPG,TCB,MBB,VIC,VHM'); ap.add_argument('--allow-fallback',action='store_true',help='Use CafeF/vnstock only for tickers missing from cophieu68 primary data'); args=ap.parse_args()
    tickers=[x.strip().upper() for x in args.tickers.split(',') if x.strip()]; warnings=[]; companies=[]
    cp68,w=load_cp68(tickers); warnings+=w; cafef=load_cafef_fallback() if args.allow_fallback else {}
    for t in tickers:
        if t in cp68:
            c,w=cp68_company(cp68[t]); warnings+=w; companies.append(c)
        elif args.allow_fallback:
            c,w=fallback_company(t,cafef); warnings+=w; companies.append(c)
        else:
            warnings.append(f'{t}:missing_from_cophieu68_primary')
    got={c['ticker'] for c in companies}; missing=[t for t in tickers if t not in got]
    nofin=sorted(c['ticker'] for c in companies if c.get('source_quality')!='primary_cophieu68_profile_financials_real')
    status='real_full_fundamental_layer' if not missing and not nofin else 'real_cophieu68_partial_fundamental_layer'
    out={'as_of':now_iso(),'source':'cophieu68.vn primary fundamental mapper; CafeF/vnstock fallback only when --allow-fallback and cophieu68 missing','source_policy':'cophieu68_primary_cafef_vnstock_fallback_only','companies':companies,'deep_dive':[score_company(c) for c in companies],'parse_quality':{'required_passed':not missing and not nofin,'missing_tickers':missing,'no_financials':nofin,'warnings':warnings,'no_sample_fallback':True,'fallback_enabled':args.allow_fallback},'quality_score':0.88 if status=='real_full_fundamental_layer' else 0.72,'status':status}
    save(LIVE/'fundamentals_live.vn.json',out); save(OUT/'company_deep_dive_real.json',out)
    md=['# VN Fundamental Real Layer','',f"as_of: {out['as_of']}",f"status: {out['status']}",f"source_policy: {out['source_policy']}",'']
    for d in out['deep_dive']: md += [f"## {d['ticker']}",f"Score: {d['fundamental_score']}",f"Source: {d.get('source_quality')}",f"Ratios: {d.get('ratios')}",f"Risks: {'; '.join(d['key_risks']) or 'None'}",'']
    (OUT/'company_deep_dive_real.md').write_text('\n'.join(md),encoding='utf-8')
    if missing or nofin: print('FUNDAMENTAL_REAL_FAILED missing='+','.join(missing)+' no_financials='+','.join(nofin),file=sys.stderr)
    print(json.dumps(out,ensure_ascii=True,indent=2)); return 0 if status=='real_full_fundamental_layer' else 2
if __name__=='__main__': raise SystemExit(main())
