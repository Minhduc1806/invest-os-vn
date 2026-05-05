#!/usr/bin/env python
r"""
Run 4-step FData daily pipeline:
1) Refresh metadata + HOSE full universe + investable universe.
2) Build HOSE quality + breadth + leadership.
3) Run signal scanner in both modes: hose_all + investable.
4) Generate daily index report linking all outputs.
"""
from __future__ import annotations
import argparse, json, subprocess, sys, os
from datetime import datetime
from pathlib import Path
from typing import List

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'outputs'

def run(cmd:List[str]):
    print('RUN',' '.join(cmd))
    env=os.environ.copy(); env['PYTHONIOENCODING']='utf-8'
    r=subprocess.run(cmd,cwd=ROOT,text=True,capture_output=True,encoding='utf-8',errors='replace',env=env)
    if r.stdout: print(r.stdout)
    if r.stderr: print(r.stderr,file=sys.stderr)
    if r.returncode!=0: raise SystemExit(r.returncode)

def read_json(p:Path):
    return json.loads(p.read_text(encoding='utf-8')) if p.exists() else {}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--tickers',default='FPT,MWG,VCB,SSI')
    ap.add_argument('--min-price',default='5')
    ap.add_argument('--min-volume',default='50000')
    ap.add_argument('--min-liquidity-score',default='25')
    args=ap.parse_args()
    py=sys.executable
    # 1
    run([py,'scripts/fdata_proto_tool.py','--sample',args.tickers])
    run([py,'scripts/fdata_hose_universe.py','--timeframe','EOD'])
    run([py,'scripts/fdata_universe_filter.py','--min-price',args.min_price,'--min-volume',args.min_volume,'--min-liquidity-score',args.min_liquidity_score])
    # 2
    run([py,'scripts/fdata_hose_quality_report.py'])
    run([py,'scripts/fdata_hose_breadth.py'])
    run([py,'scripts/hose_leadership_engine.py','--top','50'])
    # 3
    run([py,'scripts/run_pipeline.py','--config','orchestrator.yaml','--pipeline','stock_signal_scan','--live','--universe','hose_all'])
    run([py,'scripts/run_pipeline.py','--config','orchestrator.yaml','--pipeline','stock_signal_scan','--live','--universe','investable'])
    run([py,'scripts/resistance_support_engine.py'])
    run([py,'scripts/technical_setup_engine.py'])
    run([py,'scripts/risk_reward_engine.py'])
    run([py,'scripts/signal_quality_gate.py'])
    run([py,'scripts/portfolio_layer.py'])
    run([py,'scripts/historical_backtest_engine.py','--months','12','--max-symbols','500','--save-all-signals'])
    run([py,'scripts/trailing_stop_full_replay.py'])
    run([py,'scripts/rolling_stop_rule_backtest.py','--max-symbols','150'])
    run([py,'scripts/portfolio_action_report.py'])
    run([py,'scripts/eod_vn_report.py'])
    # 4
    hose=read_json(OUT/'fdata_hose_all_bars.json')
    qual=read_json(OUT/'fdata_hose_quality_report.json')
    inv=read_json(OUT/'fdata_investable_universe.json')
    sig_h=read_json(OUT/'stock_signal_scan_hose_all.json')
    sig_i=read_json(OUT/'stock_signal_scan_investable.json')
    summary={
        'as_of':datetime.now().astimezone().isoformat(timespec='seconds'),
        'steps':['metadata_hose_investable','quality_breadth_leadership','signals_two_modes','daily_index'],
        'hose':{'listed':hose.get('listed_symbols_count'),'bars':hose.get('bars_count'),'missing_dat':hose.get('missing_dat_count'),'latest_dates':hose.get('last_dates')},
        'quality':{'coverage_pct':qual.get('coverage_pct'),'zero_volume':qual.get('zero_volume_count'),'low_volume_lt_50000':qual.get('low_volume_lt_50000_count'),'missing_industry':qual.get('missing_industry_count')},
        'investable':{'input':inv.get('input_universe'),'kept':inv.get('kept_count'),'excluded':inv.get('excluded_count'),'keep_rate':inv.get('keep_rate')},
        'signals':{'hose_all':{'universe':sig_h.get('universe_size'),'signals':len(sig_h.get('signals',[])),'actionable':sig_h.get('summary',{}).get('actionable',[])},'investable':{'universe':sig_i.get('universe_size'),'signals':len(sig_i.get('signals',[])),'actionable':sig_i.get('summary',{}).get('actionable',[])}},
        'files':['outputs/fdata_hose_quality_report.md','outputs/fdata_hose_breadth.md','outputs/hose_leadership.md','outputs/stock_signal_report_hose_all.md','outputs/stock_signal_report_investable.md']
    }
    (OUT/'fdata_daily_all_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    md='# FData Daily All Summary\n\n'
    md+=f"As of: {summary['as_of']}\n\n"
    md+='## 1. HOSE full universe\n'
    md+=f"- Listed metadata: {summary['hose']['listed']}\n- Parsed bars: {summary['hose']['bars']}\n- Missing DAT: {summary['hose']['missing_dat']}\n\n"
    md+='## 2. Quality / breadth / leadership\n'
    md+=f"- Coverage: {summary['quality']['coverage_pct']}%\n- Zero volume: {summary['quality']['zero_volume']}\n- Low volume <50k: {summary['quality']['low_volume_lt_50000']}\n- Missing industry: {summary['quality']['missing_industry']}\n\n"
    md+='## 3. Signal modes\n'
    md+=f"- hose_all: {summary['signals']['hose_all']['universe']} symbols, {summary['signals']['hose_all']['signals']} signals\n"
    md+=f"- investable: {summary['signals']['investable']['universe']} symbols, {summary['signals']['investable']['signals']} signals\n\n"
    md+='## 4. Files\n'+'\n'.join('- '+f for f in summary['files'])+'\n'
    (OUT/'fdata_daily_all_summary.md').write_text(md,encoding='utf-8')
    print('OK daily all'); print(OUT/'fdata_daily_all_summary.md')
if __name__=='__main__': main()
