#!/usr/bin/env python
"""Build real-only VN fundamental layer.

No mock/sample fallback. Fails when provider returns no usable company data.
"""
from __future__ import annotations
import argparse, json, math, re, sys
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT=Path(__file__).resolve().parents[1]
LIVE=ROOT/'data_live'
OUT=ROOT/'outputs'

def now_iso(): return datetime.now().astimezone().isoformat(timespec='seconds')
def save(p:Path,d:Any): p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8')
def recs(df:Any)->list[dict[str,Any]]:
    try: return df.to_dict('records')
    except Exception: return []
def pick(row:dict[str,Any], names:list[str], default=None):
    low={str(k).lower():v for k,v in row.items()}
    for n in names:
        if n in row: return row[n]
        if n.lower() in low: return low[n.lower()]
    return default
def num(x:Any)->float|None:
    try:
        if x is None or x=='': return None
        v=float(str(x).replace(',',''))
        return None if math.isnan(v) else v
    except Exception: return None
def clean(s:Any, limit:int=900)->str:
    t=re.sub(r'\s+',' ',str(s or '')).strip()
    return t[:limit]

def load_cafef_financials()->dict[str,Any]:
    p=LIVE/'cafef_financial_statements_html.vn.json'
    if not p.exists(): return {}
    data=json.loads(p.read_text(encoding='utf-8'))
    out={}
    for item in data.get('items',[]):
        periods=item.get('periods') or []
        if periods: out[item.get('ticker')]=periods[0]
    return out

def vnstock_obj():
    try:
        import vnstock # type: ignore
        return vnstock
    except Exception as e:
        raise RuntimeError(f'vnstock_unavailable:{e}')

def fetch_company(vnstock:Any, ticker:str)->tuple[dict[str,Any]|None,list[str]]:
    warnings=[]
    try:
        c=vnstock.Company(symbol=ticker)
        rows=recs(c.overview()) if hasattr(c,'overview') else []
    except Exception as e:
        return None,[f'{ticker}:overview_error:{e}']
    if not rows:
        return None,[f'{ticker}:overview_empty']
    r=rows[0]
    company={
        'ticker':ticker,
        'exchange':pick(r,['exchange']),
        'business':clean(pick(r,['business_model','companyProfile','businessType']),1400),
        'profile':{
            'founded_date':pick(r,['founded_date']),
            'listing_date':pick(r,['listing_date']),
            'ceo_name':pick(r,['ceo_name']),
            'company_type':pick(r,['company_type']),
            'address':pick(r,['address']),
            'website':pick(r,['website']),
            'employees':num(pick(r,['number_of_employees'])),
            'charter_capital_bil_vnd': (num(pick(r,['charter_capital'])) or 0)/1_000_000_000 if num(pick(r,['charter_capital'])) else None,
            'outstanding_shares':num(pick(r,['outstanding_shares'])),
            'free_float_pct':num(pick(r,['free_float_percentage'])),
            'as_of_date':pick(r,['as_of_date']),
        },
        'financials':{},
        'valuation':{},
        'risks':[],
        'source_quality':'primary_profile_real',
        'confidence':0.74,
    }
    # Free vnstock may return empty financial tables. Capture only if real rows exist; never sample fallback.
    try:
        f=vnstock.Finance(symbol=ticker, source='VCI')
        for method,key in [('ratio','ratios'),('income_statement','income_statement'),('balance_sheet','balance_sheet'),('cash_flow','cash_flow')]:
            if hasattr(f,method):
                try:
                    rows=recs(getattr(f,method)())
                    if rows: company['financials'][key]=rows[:4]
                except Exception as e: warnings.append(f'{ticker}:{method}_error:{e}')
    except Exception as e: warnings.append(f'{ticker}:finance_error:{e}')
    if not company['financials']:
        warnings.append(f'{ticker}:financial_statement_empty_free_provider')
        company['risks'].append('financial_statement_empty_free_provider; deep dive limited to real company profile')
        company['confidence']=0.62
    return company,warnings

def score_company(c:dict[str,Any])->dict[str,Any]:
    p=c.get('profile',{})
    score=50
    if p.get('employees') and p['employees']>1000: score+=10
    if p.get('free_float_pct') is not None and p['free_float_pct']>=20: score+=5
    if c.get('business'): score+=10
    if c.get('financials'): score+=15
    return {'ticker':c['ticker'],'fundamental_score':min(score,90),'thesis':clean(c.get('business'),260),'key_risks':c.get('risks',[])[:3]}

def main()->int:
    ap=argparse.ArgumentParser()
    ap.add_argument('--tickers',default='FPT,MWG,VCB,SSI')
    ap.add_argument('--allow-profile-only',action='store_true')
    args=ap.parse_args()
    tickers=[x.strip().upper() for x in args.tickers.split(',') if x.strip()]
    warnings=[]; companies=[]
    try: vnstock=vnstock_obj()
    except Exception as e:
        print(f'FUNDAMENTAL_REAL_FAILED {e}',file=sys.stderr); return 2
    cafef=load_cafef_financials()
    for t in tickers:
        c,w=fetch_company(vnstock,t); warnings+=w
        if c:
            if t in cafef and cafef[t].get('status')=='ok':
                c['financials']['cafef_html']=cafef[t]
                c['financial_metrics']=cafef[t].get('key_metrics',{})
                c['source_quality']='primary_profile_plus_cafef_financials_real'
                c['confidence']=0.82
                c['risks']=[r for r in c.get('risks',[]) if 'financial_statement_empty_free_provider' not in r]
            companies.append(c)
    missing=[t for t in tickers if t not in {c['ticker'] for c in companies}]
    if missing: warnings.append('missing_company_profiles:'+','.join(missing))
    if not companies or (missing and not args.allow_profile_only):
        print('FUNDAMENTAL_REAL_FAILED missing real profiles: '+','.join(missing),file=sys.stderr); return 2
    if any(not c.get('financials') for c in companies) and not args.allow_profile_only:
        print('FUNDAMENTAL_REAL_FAILED financial statements empty; run cafef_financial_statements_html_parser.py or rerun with --allow-profile-only',file=sys.stderr); return 2
    out={'as_of':now_iso(),'source':'vnstock.Company overview + vnstock.Finance when available + CafeF HTML financial statement tables','companies':companies,'deep_dive':[score_company(c) for c in companies],'parse_quality':{'required_passed':not missing,'missing_tickers':missing,'warnings':warnings,'no_sample_fallback':True},'quality_score':0.82 if all(c.get('financials') for c in companies) else 0.68,'status':'real_profile_fundamental_layer' if any(not c.get('financials') for c in companies) else 'real_full_fundamental_layer'}
    save(LIVE/'fundamentals_live.vn.json',out)
    save(OUT/'company_deep_dive_real.json',out)
    md=['# VN Fundamental Real Layer','',f"as_of: {out['as_of']}",f"status: {out['status']}",'']
    for d in out['deep_dive']:
        md += [f"## {d['ticker']}",f"Score: {d['fundamental_score']}",f"Thesis: {d['thesis']}",f"Risks: {'; '.join(d['key_risks']) or 'None'}",'']
    (OUT/'company_deep_dive_real.md').write_text('\n'.join(md),encoding='utf-8')
    print(json.dumps(out,ensure_ascii=False,indent=2))
    return 0
if __name__=='__main__': raise SystemExit(main())
