#!/usr/bin/env python
from __future__ import annotations
import argparse, json, math, re, sys
from datetime import datetime
from pathlib import Path
from typing import Any
ROOT=Path(__file__).resolve().parents[1]; LIVE=ROOT/'data_live'; OUT=ROOT/'outputs'; CACHE=LIVE/'cache'
def now_iso(): return datetime.now().astimezone().isoformat(timespec='seconds')
def save(p:Path,d:Any): p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8')
def load(p:Path): return json.loads(p.read_text(encoding='utf-8')) if p.exists() else None
def recs(df:Any):
    try: return df.to_dict('records')
    except Exception: return []
def pick(row,names,default=None):
    low={str(k).lower():v for k,v in row.items()}
    for n in names:
        if n in row: return row[n]
        if n.lower() in low: return low[n.lower()]
    return default
def num(x):
    try:
        if x is None or x=='': return None
        v=float(str(x).replace(',',''))
        return None if math.isnan(v) else v
    except Exception: return None
def clean(s,limit=900): return re.sub(r'\s+',' ',str(s or '')).strip()[:limit]
def vnstock_obj():
    import vnstock; return vnstock
def cache_profile_path(t): return CACHE/f'company_profile_{t}.json'
def fetch_profile(vnstock,ticker):
    cp=cache_profile_path(ticker)
    try:
        c=vnstock.Company(symbol=ticker); rows=recs(c.overview()) if hasattr(c,'overview') else []
        if rows:
            save(cp,{'as_of':now_iso(),'ticker':ticker,'rows':rows,'source':'vnstock.Company.overview'}); return rows[0],[]
        raise RuntimeError('overview_empty')
    except Exception as e:
        cached=load(cp)
        if cached and cached.get('rows'):
            return cached['rows'][0],[f'{ticker}:overview_cache_used:{e}']
        return None,[f'{ticker}:overview_error_no_cache:{e}']
def cafef_metric_ok(p):
    km=p.get('key_metrics',{}) if isinstance(p,dict) else {}
    def has(k): return bool(isinstance(km.get(k),dict) and km.get(k).get('latest_value') is not None)
    return has('revenue') and (has('profit_after_tax') or has('parent_profit')) and has('total_assets') and has('equity')
def load_cafef():
    d=load(LIVE/'cafef_financial_statements_html.vn.json') or {}; out={}; partial=[]
    for item in d.get('items',[]):
        ps=item.get('periods') or []
        chosen=None
        for p in ps:
            if p.get('status')=='ok' and cafef_metric_ok(p): chosen=p; break
        if chosen: out[item.get('ticker')]=chosen
        else: partial.append(item.get('ticker'))
    return out,partial
def build_company(row,ticker,warnings):
    p={'founded_date':pick(row,['founded_date']),'listing_date':pick(row,['listing_date']),'ceo_name':pick(row,['ceo_name']),'company_type':pick(row,['company_type']),'address':pick(row,['address']),'website':pick(row,['website']),'employees':num(pick(row,['number_of_employees'])),'outstanding_shares':num(pick(row,['outstanding_shares'])),'free_float_pct':num(pick(row,['free_float_percentage'])),'as_of_date':pick(row,['as_of_date'])}
    cc=num(pick(row,['charter_capital'])); p['charter_capital_bil_vnd']=cc/1_000_000_000 if cc else None
    return {'ticker':ticker,'exchange':pick(row,['exchange']),'business':clean(pick(row,['business_model','companyProfile','businessType']),1400),'profile':p,'financials':{},'valuation':{},'risks':[],'source_quality':'primary_profile_real','confidence':0.74}
def fetch_company(vnstock,ticker,cafef):
    row,warnings=fetch_profile(vnstock,ticker)
    if row is None: return None,warnings
    c=build_company(row,ticker,warnings)
    if ticker in cafef and cafef[ticker].get('status')=='ok' and cafef_metric_ok(cafef[ticker]):
        c['financials']['cafef_html']=cafef[ticker]; c['financial_metrics']=cafef[ticker].get('key_metrics',{}); c['source_quality']='primary_profile_plus_cafef_financials_real'; c['confidence']=0.84
    else:
        c['risks'].append('cafef_financial_statement_missing_or_partial'); c['confidence']=0.62; warnings.append(f'{ticker}:cafef_financial_missing_or_partial')
    return c,warnings
def score_company(c):
    p=c.get('profile',{}); score=50
    if p.get('employees') and p['employees']>1000: score+=10
    if p.get('free_float_pct') is not None and p['free_float_pct']>=20: score+=5
    if c.get('business'): score+=10
    if c.get('financials'): score+=15
    km=c.get('financial_metrics',{}); ratios=km.get('ratios',{}) if isinstance(km.get('ratios'),dict) else {}
    return {'ticker':c['ticker'],'fundamental_score':min(score,90),'thesis':clean(c.get('business'),260),'key_risks':c.get('risks',[])[:3],'ratios':ratios}
def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--tickers',default='PNJ,FPT,MWG,VCB,SSI,HPG,TCB,MBB,VIC,VHM'); ap.add_argument('--allow-profile-only',action='store_true'); args=ap.parse_args()
    tickers=[x.strip().upper() for x in args.tickers.split(',') if x.strip()]; warnings=[]; companies=[]; cafef,cafef_partial=load_cafef()
    warnings += [f'{t}:cafef_partial_forced_no_financials' for t in cafef_partial]
    try: vnstock=vnstock_obj()
    except Exception as e: print(f'FUNDAMENTAL_REAL_FAILED {e}',file=sys.stderr); return 2
    for t in tickers:
        c,w=fetch_company(vnstock,t,cafef); warnings+=w
        if c: companies.append(c)
    got={c['ticker'] for c in companies}; missing=[t for t in tickers if t not in got]
    nofin=sorted(set([c['ticker'] for c in companies if not c.get('financials')] + cafef_partial))
    status='real_full_fundamental_layer' if not nofin and not missing else 'real_profile_partial_fundamental_layer'
    out={'as_of':now_iso(),'source':'vnstock.Company overview cached + CafeF HTML financial statement tables','companies':companies,'deep_dive':[score_company(c) for c in companies],'parse_quality':{'required_passed':not missing and (not nofin or args.allow_profile_only),'missing_tickers':missing,'no_financials':nofin,'warnings':warnings,'no_sample_fallback':True,'strict_cafef_partial_blocks_real_full':True},'quality_score':0.86 if status=='real_full_fundamental_layer' else 0.72,'status':status}
    save(LIVE/'fundamentals_live.vn.json',out); save(OUT/'company_deep_dive_real.json',out)
    if missing or (nofin and not args.allow_profile_only):
        print('FUNDAMENTAL_REAL_FAILED missing='+','.join(missing)+' no_financials='+','.join(nofin),file=sys.stderr)
    md=['# VN Fundamental Real Layer','',f"as_of: {out['as_of']}",f"status: {out['status']}",'']
    for d in out['deep_dive']: md += [f"## {d['ticker']}",f"Score: {d['fundamental_score']}",f"Ratios: {d.get('ratios')}",f"Risks: {'; '.join(d['key_risks']) or 'None'}",'']
    (OUT/'company_deep_dive_real.md').write_text('\n'.join(md),encoding='utf-8'); print(json.dumps(out,ensure_ascii=True,indent=2)); return 0
if __name__=='__main__': raise SystemExit(main())
