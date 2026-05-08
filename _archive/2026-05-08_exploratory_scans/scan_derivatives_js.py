from __future__ import annotations
import re,json
from pathlib import Path
from urllib.request import Request,urlopen
ROOT=Path(__file__).resolve().parents[1]; RAW=ROOT/'data_live'/'raw'/'derivatives_scan'; OUT=ROOT/'outputs'
UA='Mozilla/5.0 invest-os-vn derivatives-js/0.1'

def fetch(url):
    with urlopen(Request(url,headers={'User-Agent':UA,'Accept':'*/*'}),timeout=25) as r: return r.read()

def main():
    html=(RAW/'vndirect_derivatives.html').read_text(encoding='utf-8',errors='ignore')
    scripts=re.findall(r'src="([^"]+\.js)"',html)
    base='https://dstock.vndirect.com.vn'
    results=[]
    for src in scripts:
        url=src if src.startswith('http') else base+src
        try:
            data=fetch(url); txt=data.decode('utf-8','ignore')
            name=re.sub(r'[^A-Za-z0-9_.-]+','_',src)[-120:]
            p=RAW/('vndirect_js_'+name); p.write_bytes(data)
            hits=[]
            for pat in ['VN30F','derivative','futures','openInterest','basis','coveredWarrant','stockSearch','market']:
                if re.search(pat,txt,re.I):
                    pos=re.search(pat,txt,re.I).start(); hits.append({'pat':pat,'pos':pos,'ctx':txt[max(0,pos-180):pos+300]})
            if hits: results.append({'url':url,'file':str(p),'bytes':len(data),'hits':hits})
        except Exception as e: results.append({'url':url,'error':str(e)})
    (OUT/'derivatives_js_scan.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
    print(OUT/'derivatives_js_scan.json')
if __name__=='__main__': main()
