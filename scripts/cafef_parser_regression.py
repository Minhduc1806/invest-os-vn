#!/usr/bin/env python
from __future__ import annotations
import argparse,json,subprocess,sys,os
from pathlib import Path
from tempfile import TemporaryDirectory
ROOT=Path(__file__).resolve().parents[1]; LIVE=ROOT/'data_live'; OUT=ROOT/'outputs'
SETS={
 'core':'PNJ,FPT,MWG,VCB,SSI,HPG,TCB,MBB,VIC,VHM',
 'random_mixed':'REE,GAS,VNM,SAB,MSN,BID,CTG,STB,VND,KDH',
 'banks':'VCB,TCB,MBB,BID,CTG,STB,ACB,VPB,TPB,HDB,SHB,EIB,VIB,OCB,MSB',
 'securities':'SSI,VND,VCI,MBS,BSI,ORS,AGR,APG,TVS',
 'real_estate':'VIC,VHM,KDH,NLG,DXG,PDR,NVL,DIG,CEO,HDG,CRE,SCR,IJC,BCM,SIP',
 'retail_consumer_industrial':'PNJ,FPT,MWG,HPG,REE,GAS,VNM,SAB,MSN,KDC,DGC,DPM,DCM,GMD,VSC,CTR,PC1,GVR,BMP,AAA',
 'sector50':'PNJ,FPT,MWG,VCB,SSI,HPG,TCB,MBB,VIC,VHM,REE,GAS,VNM,SAB,MSN,BID,CTG,STB,VND,KDH,ACB,VPB,HDB,SHB,EIB,VIB,OCB,MSB,VCI,MBS,BSI,ORS,AGR,APG,TVS,NLG,DXG,PDR,DIG,CEO,HDG,CRE,SCR,BCM,SIP,DGC,DPM,DCM,GMD',
 'sector100':'PNJ,FPT,MWG,VCB,SSI,HPG,TCB,MBB,VIC,VHM,REE,GAS,VNM,SAB,MSN,BID,CTG,STB,VND,KDH,ACB,VPB,HDB,SHB,EIB,VIB,OCB,MSB,VCI,MBS,BSI,ORS,AGR,APG,TVS,NLG,DXG,PDR,DIG,CEO,HDG,CRE,SCR,BCM,SIP,DGC,DPM,DCM,GMD,VSC,CTR,PC1,GVR,BMP,AAA,KDC,DPM,DCM,POW,NT2,PPC,VCG,HHV,C4G,PLC,ANV,VHC,IDI,LTG,DBC,BAF,HAG,HNG,CSV,LAS,BFC,IDC,KBC,SZC,DXS,NHA,TCH,HUT,VIX,FTS,CTS,TVB,EVF,HCM,SHS,FTS,CTS,PHR,DPR,NTP,CII,KSB,FCN,VTP,DGW,PET,FRT'
}
def run_set(name,tickers,periods,timeout):
 env=os.environ.copy(); env['PYTHONIOENCODING']='utf-8'
 cmd=[sys.executable,'scripts/cafef_financial_statements_html_parser.py','--tickers',tickers,'--periods',str(periods),'--summary']
 try:
  r=subprocess.run(cmd,cwd=ROOT,text=True,capture_output=True,encoding='utf-8',errors='replace',env=env,timeout=timeout)
  rc,stdout,stderr=r.returncode,r.stdout[-2000:],r.stderr[-2000:]
 except subprocess.TimeoutExpired as e:
  rc,stdout,stderr=124,(e.stdout or '')[-2000:],((e.stderr or '')+f'\nTIMEOUT after {timeout}s')[-2000:]
 health=json.loads((LIVE/'cafef_financial_statements_health.vn.json').read_text(encoding='utf-8')) if (LIVE/'cafef_financial_statements_health.vn.json').exists() else {}
 expected=len(tickers.split(','))
 return {'set':name,'tickers':tickers.split(','),'returncode':rc,'stdout':stdout,'stderr':stderr,'health':health,'passed':rc==0 and health.get('status')=='ok' and health.get('ok_ticker_count')==expected}
def main():
 ap=argparse.ArgumentParser(); ap.add_argument('--periods',type=int,default=3); ap.add_argument('--timeout-per-set',type=int,default=240); ap.add_argument('--sets',default=','.join(SETS.keys()),help='comma-separated set names or all'); args=ap.parse_args()
 names=list(SETS) if args.sets=='all' else [x.strip() for x in args.sets.split(',') if x.strip()]
 bad=[n for n in names if n not in SETS]
 if bad: raise SystemExit(f'unknown sets: {bad}')
 results=[run_set(n,SETS[n],args.periods,args.timeout_per_set) for n in names]
 out={'status':'ok' if all(r['passed'] for r in results) else 'failed','periods':args.periods,'results':results}
 OUT.mkdir(exist_ok=True); (OUT/'cafef_parser_regression.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps({'status':out['status'],'sets':[{ 'set':r['set'], 'passed':r['passed'], 'ok_ticker_count':r['health'].get('ok_ticker_count'), 'ticker_count':r['health'].get('ticker_count')} for r in results]},ensure_ascii=False,indent=2))
 return 0 if out['status']=='ok' else 2
if __name__=='__main__': raise SystemExit(main())
