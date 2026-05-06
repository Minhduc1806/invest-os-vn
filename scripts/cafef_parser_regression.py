#!/usr/bin/env python
from __future__ import annotations
import argparse,json,subprocess,sys,os
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; LIVE=ROOT/'data_live'; OUT=ROOT/'outputs'
SETS={
 'core':'PNJ,FPT,MWG,VCB,SSI,HPG,TCB,MBB,VIC,VHM',
 'random_mixed':'REE,GAS,VNM,SAB,MSN,BID,CTG,STB,VND,KDH',
}
def run_set(name,tickers,periods):
 env=os.environ.copy(); env['PYTHONIOENCODING']='utf-8'
 cmd=[sys.executable,'scripts/cafef_financial_statements_html_parser.py','--tickers',tickers,'--periods',str(periods),'--summary']
 r=subprocess.run(cmd,cwd=ROOT,text=True,capture_output=True,encoding='utf-8',errors='replace',env=env)
 health=json.loads((LIVE/'cafef_financial_statements_health.vn.json').read_text(encoding='utf-8')) if (LIVE/'cafef_financial_statements_health.vn.json').exists() else {}
 return {'set':name,'tickers':tickers.split(','),'returncode':r.returncode,'stdout':r.stdout[-2000:],'stderr':r.stderr[-2000:],'health':health,'passed':r.returncode==0 and health.get('status')=='ok' and health.get('ok_ticker_count')==len(tickers.split(','))}
def main():
 ap=argparse.ArgumentParser(); ap.add_argument('--periods',type=int,default=3); args=ap.parse_args()
 results=[run_set(n,t,args.periods) for n,t in SETS.items()]
 out={'status':'ok' if all(r['passed'] for r in results) else 'failed','periods':args.periods,'results':results}
 OUT.mkdir(exist_ok=True); (OUT/'cafef_parser_regression.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps({'status':out['status'],'sets':[{ 'set':r['set'], 'passed':r['passed'], 'ok_ticker_count':r['health'].get('ok_ticker_count'), 'ticker_count':r['health'].get('ticker_count')} for r in results]},ensure_ascii=False,indent=2))
 return 0 if out['status']=='ok' else 2
if __name__=='__main__': raise SystemExit(main())
