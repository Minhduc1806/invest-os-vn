#!/usr/bin/env python
r"""
FData quality report.
Checks local FData coverage, freshness, parse success, metadata join, missing sectors, stale symbols.
"""
from __future__ import annotations
import argparse, json
from collections import Counter
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List

from fdata_adapter import read_amibroker_dat, DEFAULT_FDATA, LIVE

ROOT = Path(__file__).resolve().parents[1]


def save(p: Path, x: Any):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(x, ensure_ascii=False, indent=2), encoding="utf-8")

def md_table(headers, rows):
    out=["| "+" | ".join(headers)+" |", "| "+" | ".join(["---"]*len(headers))+" |"]
    for r in rows: out.append("| "+" | ".join(map(str,r))+" |")
    return "\n".join(out)

def load_meta() -> Dict[str, Any]:
    p=LIVE/'fdata_symbols_full.json'
    if p.exists(): return json.loads(p.read_text(encoding='utf-8'))
    return {}

def days_old(ds: str) -> int:
    return (date.today()-datetime.strptime(ds,'%Y-%m-%d').date()).days

def scan_dir(path: Path, meta: Dict[str, Any], min_rows: int, stale_days: int) -> Dict[str, Any]:
    files=sorted(path.glob('*.dat')) if path.exists() else []
    stats=[]; parse_fail=[]; stale=[]; missing_meta=[]; missing_industry=[]; exchanges=Counter(); industries=Counter(); dates=Counter()
    for f in files:
        t=f.stem.upper(); rows=read_amibroker_dat(f)
        if len(rows)<min_rows:
            parse_fail.append({'ticker':t,'rows':len(rows),'path':str(f)})
            continue
        last=rows[-1]['date']; d_old=days_old(last); dates[last]+=1
        m=meta.get(t,{})
        if not m: missing_meta.append(t)
        if not m.get('industry'): missing_industry.append(t)
        exchanges[m.get('exchange','unknown')]+=1
        industries[m.get('icb_level_2_name') or m.get('industry','unknown')]+=1
        if d_old>stale_days: stale.append({'ticker':t,'last_date':last,'days_old':d_old})
        stats.append({'ticker':t,'rows':len(rows),'last_date':last,'days_old':d_old,'exchange':m.get('exchange','unknown'),'industry':m.get('industry','unknown'),'file_size':f.stat().st_size})
    return {
        'path':str(path),'files':len(files),'parsed_symbols':len(stats),'parse_fail_count':len(parse_fail),'stale_count':len(stale),
        'missing_meta_count':len(missing_meta),'missing_industry_count':len(missing_industry),
        'latest_dates':dates.most_common(10),'exchanges':exchanges.most_common(),'top_industries':industries.most_common(30),
        'parse_fail_sample':parse_fail[:50],'stale_sample':stale[:50],'missing_meta_sample':missing_meta[:50],'missing_industry_sample':missing_industry[:50],
        'symbols_sample':stats[:20]
    }

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--root',default=str(DEFAULT_FDATA))
    ap.add_argument('--stale-days',type=int,default=3)
    ap.add_argument('--min-rows',type=int,default=2)
    ap.add_argument('--timeframes',default='EOD,15m')
    args=ap.parse_args()
    root=Path(args.root); meta=load_meta(); frames=[x.strip() for x in args.timeframes.split(',') if x.strip()]
    report={'as_of':datetime.now().astimezone().isoformat(timespec='seconds'),'root':str(root),'metadata_symbols':len(meta),'stale_days':args.stale_days,'timeframes':{}}
    for tf in frames:
        report['timeframes'][tf]=scan_dir(root/'AmiBroker'/tf/'stock',meta,args.min_rows,args.stale_days)
    # score
    eod=report['timeframes'].get('EOD',{})
    parsed=eod.get('parsed_symbols',0); files=eod.get('files',0)
    parse_rate=parsed/files if files else 0
    meta_rate=1-(eod.get('missing_meta_count',0)/parsed) if parsed else 0
    industry_rate=1-(eod.get('missing_industry_count',0)/parsed) if parsed else 0
    stale_rate=1-(eod.get('stale_count',0)/parsed) if parsed else 0
    score=round(100*(0.35*parse_rate+0.25*meta_rate+0.25*industry_rate+0.15*stale_rate),1)
    report['quality_score']=score
    report['rates']={'parse_rate':round(parse_rate,4),'meta_rate':round(meta_rate,4),'industry_rate':round(industry_rate,4),'fresh_rate':round(stale_rate,4)}
    out_json=ROOT/'outputs'/'fdata_quality_report.json'; save(out_json,report)
    md="# FData Quality Report\n\n"
    md+=f"As of: {report['as_of']}\n\nQuality score: {score}/100\n\n"
    md+=md_table(['Metric','Value'], [['metadata_symbols',len(meta)],['EOD files',eod.get('files',0)],['EOD parsed',parsed],['parse_rate',report['rates']['parse_rate']],['meta_rate',report['rates']['meta_rate']],['industry_rate',report['rates']['industry_rate']],['fresh_rate',report['rates']['fresh_rate']],['stale_count',eod.get('stale_count',0)]])
    md+='\n\n## Latest dates\n'+md_table(['date','count'], eod.get('latest_dates',[]))
    md+='\n\n## Exchanges\n'+md_table(['exchange','count'], eod.get('exchanges',[]))
    md+='\n\n## Top industries\n'+md_table(['industry','count'], eod.get('top_industries',[])[:20])
    md+='\n\n## Warnings\n'
    if eod.get('stale_count',0): md+=f"- Stale symbols: {eod.get('stale_count')}\n"
    if eod.get('missing_industry_count',0): md+=f"- Missing industry: {eod.get('missing_industry_count')}\n"
    if eod.get('parse_fail_count',0): md+=f"- Parse fail: {eod.get('parse_fail_count')}\n"
    if not any([eod.get('stale_count',0),eod.get('missing_industry_count',0),eod.get('parse_fail_count',0)]): md+='- None\n'
    out_md=ROOT/'outputs'/'fdata_quality_report.md'; out_md.write_text(md,encoding='utf-8')
    print('OK quality report'); print(out_json); print(out_md)
if __name__=='__main__': main()
