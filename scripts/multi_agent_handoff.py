#!/usr/bin/env python
"""Deterministic multi-agent handoff loop using prior agent outputs as next-agent inputs."""
from __future__ import annotations
import json, argparse
from datetime import datetime
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT/'outputs'; LIVE=ROOT/'data_live'

def now_iso(): return datetime.now().astimezone().isoformat(timespec='seconds')
def load(p): return json.loads(Path(p).read_text(encoding='utf-8'))
def save(p,d): Path(p).parent.mkdir(exist_ok=True); Path(p).write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8')

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--pipeline',default='daily_production') ; args=ap.parse_args()
    market=load(LIVE/'market_snapshot.vn.json'); macro=load(LIVE/'macro_rates_live.vn.json'); fund=load(LIVE/'fundamentals_live.vn.json'); news=load(LIVE/'news_live.vn.json')
    handoffs=[]
    ms={'agent':'market-strategist','output':{'regime':'neutral','breadth':market.get('breadth'), 'indices':market.get('indices',[])[:3]}}
    handoffs.append(ms)
    rates={'agent':'rates-fixed-income-analyst','input_from':['market-strategist'],'output':{'policy_rate_pct':macro.get('rates',{}).get('policy_rate_pct',{}).get('value'),'deposit_confidence':macro.get('rates',{}).get('deposit_rates',{}).get('confidence')}}
    handoffs.append(rates)
    fund_out={'agent':'fundamental-analyst','input_from':['market-strategist','rates-fixed-income-analyst'],'output':{'deep_dive':fund.get('deep_dive',[])[:10],'limitation':'Finance statements empty in free vnstock; no full valuation'}}
    handoffs.append(fund_out)
    tech={'agent':'equity-technical-analyst','input_from':['market-strategist','fundamental-analyst'],'output':{'scan_file':'outputs/stock_signal_scan_investable.json'}}
    handoffs.append(tech)
    quant={'agent':'quant-researcher','input_from':['equity-technical-analyst'],'output':{'backtest_files':['outputs/historical_backtest.md','outputs/rolling_walk_forward_backtest.md']}}
    handoffs.append(quant)
    pf={'agent':'portfolio-advisor','input_from':['market-strategist','equity-technical-analyst','quant-researcher'],'output':{'portfolio_file':'outputs/portfolio_daily.json'}}
    handoffs.append(pf)
    wealth={'agent':'wealth-asset-manager','input_from':['portfolio-advisor','rates-fixed-income-analyst'],'output':{'asset_ledger_status':'not_live_configured'}}
    handoffs.append(wealth)
    editor={'agent':'financial-news-editor','input_from':[h['agent'] for h in handoffs],'output':{'news_count':len(news.get('items',[])),'digest_file':'outputs/telegram_digest.txt'}}
    handoffs.append(editor)
    designer={'agent':'investment-data-designer','input_from':[h['agent'] for h in handoffs],'output':{'dashboard_file':'outputs/dashboard.html','validation':'validated_json_only'}}
    handoffs.append(designer)
    out={'as_of':now_iso(),'pipeline':args.pipeline,'handoffs':handoffs,'status':'deterministic_handoff_loop_complete','autonomy_level':'scripted_autonomous; not LLM subagent runtime'}
    save(OUT/'multi_agent_handoff.json',out)
    print(json.dumps(out,ensure_ascii=False,indent=2))
if __name__=='__main__': main()
