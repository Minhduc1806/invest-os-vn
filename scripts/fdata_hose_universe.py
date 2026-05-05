#!/usr/bin/env python
r"""
Build full HOSE/HSX listed stock universe from local FData.
No liquidity filtering. Includes all symbols with exchange=HSX and type=stock that have EOD .dat.
"""
from __future__ import annotations
import argparse, json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from fdata_adapter import DEFAULT_FDATA, LIVE, read_amibroker_dat, bar_from_rows, index_ret20, fdata_base, load_metadata

ROOT=Path(__file__).resolve().parents[1]

def save(p:Path,x:Any):
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf-8')

def md_table(headers, rows):
    out=["| "+" | ".join(headers)+" |", "| "+" | ".join(["---"]*len(headers))+" |"]
    for r in rows: out.append("| "+" | ".join(map(str,r))+" |")
    return "\n".join(out)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--root',default=str(DEFAULT_FDATA))
    ap.add_argument('--timeframe',default='EOD')
    args=ap.parse_args()
    root=Path(args.root); base=fdata_base(root,args.timeframe); stock_dir=base/'stock'
    meta=load_metadata(root); idx_ret=index_ret20(base)
    hose_symbols=sorted([t for t,m in meta.items() if m.get('exchange')=='HSX' and m.get('type')=='stock'])
    bars=[]; missing=[]; insufficient=[]
    for t in hose_symbols:
        p=stock_dir/f'{t}.dat'
        if not p.exists():
            missing.append(t); continue
        rows=read_amibroker_dat(p)
        if len(rows)<2:
            insufficient.append(t); continue
        b=bar_from_rows(t,rows,idx_ret,meta.get(t,{}),str(p))
        b['listed_exchange']='HOSE'
        b['fdata_exchange']='HSX'
        bars.append(b)
    dates={}
    for b in bars: dates[b['date']]=dates.get(b['date'],0)+1
    by_sector={}
    for b in bars:
        sec=b.get('icb_level_2_name') or b.get('industry') or 'unknown'
        by_sector[sec]=by_sector.get(sec,0)+1
    result={'as_of':datetime.now().astimezone().isoformat(timespec='seconds'),'source':'fdata_hose_all_listed','timeframe':args.timeframe,'exchange':'HOSE','fdata_exchange':'HSX','listed_symbols_count':len(hose_symbols),'bars_count':len(bars),'missing_dat_count':len(missing),'insufficient_count':len(insufficient),'last_dates':sorted(dates.items(),key=lambda x:x[1],reverse=True),'sector_counts':sorted(by_sector.items(),key=lambda x:x[1],reverse=True),'bars':bars,'missing_dat':missing,'insufficient':insufficient}
    save(LIVE/'fdata_hose_all_bars.json',result)
    save(ROOT/'outputs'/'fdata_hose_all_bars.json',result)
    md='# FData HOSE All Listed Universe\n\n'
    md+=f"As of: {result['as_of']}\n\nExchange: HOSE (FData HSX)\n\nListed symbols from metadata: {len(hose_symbols)}\nParsed bars: {len(bars)}\nMissing DAT: {len(missing)}\nInsufficient: {len(insufficient)}\n\n"
    md+='## Latest dates\n'+md_table(['date','count'],result['last_dates'][:10])
    md+='\n\n## Sector counts\n'+md_table(['sector','count'],result['sector_counts'])
    md+='\n\n## Sample bars\n'+md_table(['ticker','industry','date','close','change_pct','volume'],[[b['ticker'],b.get('industry',''),b['date'],b['close'],b['change_pct'],b['volume']] for b in bars[:50]])
    (ROOT/'outputs'/'fdata_hose_all_bars.md').write_text(md,encoding='utf-8')
    print('OK HOSE all listed')
    print('listed',len(hose_symbols),'bars',len(bars),'missing',len(missing),'insufficient',len(insufficient))
    print(LIVE/'fdata_hose_all_bars.json')
    print(ROOT/'outputs'/'fdata_hose_all_bars.md')
if __name__=='__main__': main()
