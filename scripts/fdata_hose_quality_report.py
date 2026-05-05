#!/usr/bin/env python
r"""HOSE universe quality report + missing symbol audit."""
from __future__ import annotations
import argparse,json
from collections import Counter
from datetime import datetime,date
from pathlib import Path
from typing import Any
ROOT=Path(__file__).resolve().parents[1]; LIVE=ROOT/'data_live'; OUT=ROOT/'outputs'

def save(p:Path,x:Any): p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf-8')
def md_table(h,rows):
 out=['| '+' | '.join(h)+' |','| '+' | '.join(['---']*len(h))+' |']
 for r in rows: out.append('| '+' | '.join(map(str,r))+' |')
 return '\n'.join(out)
def days_old(ds): return (date.today()-datetime.strptime(ds,'%Y-%m-%d').date()).days

def main():
 ap=argparse.ArgumentParser(); ap.add_argument('--input',default=str(LIVE/'fdata_hose_all_bars.json')); ap.add_argument('--stale-days',type=int,default=3); args=ap.parse_args()
 d=json.loads(Path(args.input).read_text(encoding='utf-8')); bars=d.get('bars',[])
 meta=json.loads((LIVE/'fdata_symbols_full.json').read_text(encoding='utf-8')) if (LIVE/'fdata_symbols_full.json').exists() else {}
 missing=d.get('missing_dat',[]); insufficient=d.get('insufficient',[])
 zero=[b for b in bars if b.get('volume',0)==0]; lowvol=[b for b in bars if b.get('volume',0)<50000]; stale=[b for b in bars if days_old(b['date'])>args.stale_days]
 missing_ind=[b for b in bars if not b.get('industry') or b.get('industry')=='unknown']
 dates=Counter(b['date'] for b in bars); sectors=Counter(b.get('icb_level_2_name') or b.get('industry') or 'unknown' for b in bars)
 exchanges=Counter(b.get('exchange','') for b in bars)
 # coverage: metadata HSX stock vs parsed bars, excluding known ETF/fund-like missing
 listed=d.get('listed_symbols_count',0); parsed=d.get('bars_count',len(bars)); coverage=round(parsed/max(1,listed)*100,2)
 result={'as_of':datetime.now().astimezone().isoformat(timespec='seconds'),'input':args.input,'exchange':'HOSE','listed_symbols':listed,'parsed_bars':parsed,'coverage_pct':coverage,'missing_dat':missing,'missing_dat_details':[meta.get(t,{'ticker':t}) for t in missing],'insufficient':insufficient,'latest_dates':dates.most_common(),'exchange_counts':exchanges.most_common(),'sector_counts':sectors.most_common(),'zero_volume_count':len(zero),'low_volume_lt_50000_count':len(lowvol),'stale_count':len(stale),'missing_industry_count':len(missing_ind),'zero_volume_sample':zero[:50],'low_volume_sample':lowvol[:50],'stale_sample':stale[:50],'missing_industry_sample':missing_ind[:50],'trust_summary':{'price_volume_coverage':'OK' if coverage>=99 else 'CHECK','freshness':'OK' if not stale else 'CHECK','metadata_join':'OK' if len(missing_ind)/max(1,len(bars))<0.05 else 'CHECK','notes':['Missing DAT currently includes ETF/VEOF/VESAF in metadata, likely fund/ETF records not ordinary listed stocks.' if set(missing).intersection({'ETF','VEOF','VESAF'}) else '']}}
 save(OUT/'fdata_hose_quality_report.json',result)
 md='# HOSE Data Quality Report\n\n'; md+=f"As of: {result['as_of']}\n\n"
 md+=md_table(['Metric','Value'],[['Listed metadata',listed],['Parsed bars',parsed],['Coverage %',coverage],['Missing DAT',len(missing)],['Insufficient',len(insufficient)],['Zero volume',len(zero)],['Low volume <50k',len(lowvol)],['Stale',len(stale)],['Missing industry',len(missing_ind)]])
 md+='\n\n## Latest dates\n'+md_table(['date','count'],result['latest_dates'])
 md+='\n\n## Missing DAT details\n'+md_table(['ticker','name','type','exchange','industry'],[[m.get('ticker'),m.get('name'),m.get('type'),m.get('exchange'),m.get('industry')] for m in result['missing_dat_details']])
 md+='\n\n## Sector counts\n'+md_table(['sector','count'],result['sector_counts'])
 md+='\n\n## Trust summary\n'+md_table(['Check','Status'],[[k,v] for k,v in result['trust_summary'].items() if k!='notes'])
 md+='\n\nNotes:\n'+'\n'.join('- '+n for n in result['trust_summary']['notes'] if n)
 (OUT/'fdata_hose_quality_report.md').write_text(md,encoding='utf-8')
 print('OK HOSE quality'); print(OUT/'fdata_hose_quality_report.md')
if __name__=='__main__': main()
