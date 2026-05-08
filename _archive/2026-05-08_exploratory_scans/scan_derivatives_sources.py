from __future__ import annotations
import json, re, time
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT/'outputs'; LIVE=ROOT/'data_live'; RAW=LIVE/'raw'/'derivatives_scan'
RAW.mkdir(parents=True, exist_ok=True)
UA='Mozilla/5.0 invest-os-vn derivatives-scan/0.1'

def fetch(url, timeout=20):
    req=Request(url,headers={'User-Agent':UA,'Accept':'application/json,text/html,*/*','Referer':'https://fireant.vn/'})
    with urlopen(req,timeout=timeout) as r:
        data=r.read(); ct=r.headers.get('content-type','')
    return data,ct

def try_url(name,url):
    rec={'name':name,'url':url,'ok':False}
    try:
        data,ct=fetch(url); rec.update(ok=True,status=200,content_type=ct,bytes=len(data))
        suffix='.json' if b'{' in data[:20] or b'[' in data[:20] else '.html'
        p=RAW/(re.sub(r'[^A-Za-z0-9_.-]+','_',name)[:80]+suffix); p.write_bytes(data); rec['file']=str(p)
        text=data[:200000].decode('utf-8','ignore')
        rec['mentions']={k:bool(re.search(k,text,re.I)) for k in ['VN30F','VN30F1M','futures','derivative','openInterest','open_interest','basis','OI']}
        rec['sample']=text[:500]
    except Exception as e:
        rec.update(error=type(e).__name__+': '+str(e)[:300])
    return rec

def inspect_fireant():
    out=[]
    fire=LIVE/'fireant_foreign_flow.vn.json'
    if fire.exists():
        d=json.loads(fire.read_text(encoding='utf-8'))
        syms=d.get('ticker_metadata',[])
        fut=[s for s in syms if 'VN30F' in str(s.get('symbol','')).upper() or 'FUT' in str(s).upper() or 'PHÁI SINH' in str(s).upper()]
        prices=[p for p in d.get('ticker_realtime_prices',[]) if 'VN30F' in str(p.get('symbol','')).upper()]
        out.append({'source':'fireant_existing_capture','ticker_metadata_count':len(syms),'futures_like_metadata':fut[:50],'futures_prices':prices[:50]})
    worker=LIVE/'raw'/'fireant'/'quote_worker.redacted.js'
    if worker.exists():
        txt=worker.read_text(encoding='utf-8',errors='ignore')
        hits=[]
        for pat in ['VN30F','derivative','futures','openInterest','OpenInterest','GetDerivative','GetSymbols','UpdateLastPrices']:
            for m in re.finditer(pat,txt,re.I): hits.append({'pat':pat,'pos':m.start(),'context':txt[max(0,m.start()-140):m.start()+220]})
        out.append({'source':'fireant_worker_redacted','hits':hits[:80]})
    return out

def main():
    urls=[
      ('fireant_dashboard','https://fireant.vn/dashboard'),
      ('fireant_symbol_vn30f1m','https://fireant.vn/symbol/VN30F1M'),
      ('fireant_rest_symbol_vn30f1m','https://restv2.fireant.vn/symbols/VN30F1M'),
      ('ssi_derivatives_board','https://iboard.ssi.com.vn/bang-gia/phai-sinh'),
      ('ssi_iboard','https://iboard.ssi.com.vn/'),
      ('vndirect_derivatives','https://dstock.vndirect.com.vn/thi-truong/chung-khoan-phai-sinh'),
      ('hnx_derivatives','https://www.hnx.vn/vi-vn/thi-truong-phai-sinh.html'),
      ('vietstock_derivatives','https://finance.vietstock.vn/phai-sinh.htm'),
      ('cafef_derivatives','https://s.cafef.vn/du-lieu/phai-sinh.chn'),
    ]
    results={'as_of':time.strftime('%Y-%m-%dT%H:%M:%S%z'),'fireant_inspect':inspect_fireant(),'url_probes':[]}
    for name,url in urls:
        results['url_probes'].append(try_url(name,url))
    OUT.mkdir(exist_ok=True); (OUT/'derivatives_source_scan.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
    md=['# Derivatives source scan','']
    for x in results['fireant_inspect']:
        md.append(f"## {x.get('source')}")
        md.append('```json\n'+json.dumps(x,ensure_ascii=False,indent=2)[:6000]+'\n```')
    md.append('## URL probes')
    for r in results['url_probes']:
        md.append(f"- {r['name']}: ok={r.get('ok')} bytes={r.get('bytes')} file={r.get('file')} error={r.get('error')} mentions={r.get('mentions')}")
    (OUT/'derivatives_source_scan.md').write_text('\n'.join(md),encoding='utf-8')
    print(OUT/'derivatives_source_scan.json')
    print(OUT/'derivatives_source_scan.md')
if __name__=='__main__': main()
