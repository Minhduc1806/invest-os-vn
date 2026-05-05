#!/usr/bin/env python
from __future__ import annotations
import json,argparse
from datetime import datetime
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT/'outputs'
def save(p,x): p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf-8')
def md_table(h,rows):
 out=['| '+' | '.join(h)+' |','| '+' | '.join(['---']*len(h))+' |']
 for r in rows: out.append('| '+' | '.join(map(str,r))+' |')
 return '\n'.join(out)
def calibration():
 p=OUT/'backtest_calibration.json'
 if not p.exists(): return {'setup_modifiers':{},'sector_modifiers':{},'preferred_setups':[],'weak_setups':[],'preferred_sectors':[],'weak_sectors':[]}
 return json.loads(p.read_text(encoding='utf-8'))
def candidate_score(x, sector_map, cal=None):
 cal=cal or calibration(); sec=x.get('icb_level_2_name') or x.get('industry') or 'unknown'; sec_strength=sector_map.get(sec,0)
 setup_bonus={'breakout':18,'base_building':18,'trend_follow':12,'pullback':10,'reversal_attempt':3}.get(x.get('setup'),0)
 rr=min(x.get('rr_ratio',0)/3,1)*20; liq=min(x.get('liquidity_score',0)/100,1)*18
 rs=max(min((x.get('rs_20d',0)+2)/4,1),0)*12; sector=max(min((sec_strength+25)/75,1),0)*8; vol=min(x.get('vol_ratio_20d',0)/2,1)*8
 bt_setup=cal.get('setup_modifiers',{}).get(x.get('setup'),0); bt_sector=cal.get('sector_modifiers',{}).get(sec,0)
 penalty=8 if x.get('atr14_pct',0)>4 else 0
 return round(setup_bonus+rr+liq+rs+sector+vol+bt_setup+bt_sector-penalty,2)
def hard_reject(x, sector_map):
 r=[]; sec=x.get('icb_level_2_name') or x.get('industry') or 'unknown'; sec_strength=sector_map.get(sec,0)
 if x.get('volume',0)<50000: r.append('volume thấp')
 if x.get('atr14_pct',0)>6: r.append('spread/volatility quá xấu')
 if x.get('setup') in ['avoid','distribution','failed_breakout']: r.append('setup không giao dịch')
 if 'Quỹ' in str(x.get('industry','')) or x.get('ticker','').startswith(('E1','FUE')): r.append('ETF/quỹ không phải common stock')
 if x.get('close',0)<x.get('ma20',0) and x.get('setup')!='pullback': r.append('close dưới MA20')
 if x.get('rs_20d',0)<-1.5: r.append('RS20 quá yếu')
 if sec_strength<-15: r.append('sector quá yếu')
 return r
def market_regime():
 b=json.loads((OUT/'fdata_hose_breadth.json').read_text(encoding='utf-8')) if (OUT/'fdata_hose_breadth.json').exists() else {}
 br=b.get('breadth',{}); ad=br.get('adv_dec_ratio',1); above=br.get('above_ma20_pct',50)
 idx=b.get('indices',{}).get('VNINDEX',{}) or b.get('index_context',{}).get('VNINDEX',{})
 close=idx.get('close'); ma20=idx.get('ma20'); ma50=idx.get('ma50'); slope10=idx.get('ma20_slope_10d') or idx.get('ma20_slope')
 if close and ma20 and close<ma20: reg='risk_off'
 elif close and ma20 and ma50 and close>ma20>ma50 and (slope10 is None or slope10>0) and ad>1.0 and above>=45: reg='risk_on'
 elif ad<0.8 or above<40: reg='risk_off'
 else: reg='neutral'
 return {'regime':reg,'adv_dec_ratio':ad,'above_ma20_pct':above,'vnindex_close':close,'vnindex_ma20':ma20,'vnindex_ma50':ma50,'ma20_slope_10d':slope10,'trend_filter':'allow buys only if VNINDEX > MA20 > MA50 and MA20 slope 10d positive; VNINDEX below MA20 blocks buys'}

def regime_rules(regime):
 if regime=='risk_on': return {'allowed_setup':['breakout','trend_follow','pullback','base_building'],'blocked_setup':['avoid','distribution','failed_breakout'],'reason':'risk_on: ưu tiên breakout/trend_follow'}
 if regime=='neutral': return {'allowed_setup':['pullback','base_building','breakout_confirmed'],'blocked_setup':['weak_breakout','avoid','distribution','failed_breakout'],'reason':'neutral: ưu tiên pullback/base, breakout cần R/R >2.5'}
 return {'allowed_setup':['watch_only','risk_reduce'],'blocked_setup':['buy_now_candidate','buy_on_breakout','buy_on_pullback'],'reason':'risk_off: không mua mới, chỉ watch/giảm rủi ro'}
def tier_for(x, sector_map, regime_info, cal):
 regime=regime_info['regime']; r=hard_reject(x,sector_map); score=candidate_score(x,sector_map,cal); sec=x.get('icb_level_2_name') or x.get('industry') or 'unknown'; x={**x,'candidate_score':score,'market_regime':regime,'regime_rule':regime_rules(regime),'backtest_setup_modifier':cal.get('setup_modifiers',{}).get(x.get('setup'),0),'backtest_sector_modifier':cal.get('sector_modifiers',{}).get(sec,0)}
 if regime=='risk_off' and x.get('action_type') in ['buy_now_candidate','buy_on_breakout','buy_on_pullback']:
  return 'Watch',x,['blocked_by_trend_filter: VNINDEX dưới MA20 hoặc breadth yếu, không mua mới']
 if regime=='neutral' and x.get('action_type') in ['buy_now_candidate','buy_on_breakout','buy_on_pullback']:
  return 'Watch',x,['NO NEW BUY: market neutral, chỉ watch/quản trị danh mục']
 if r: return 'Rejected',x,r
 bt_ok=(x.get('setup') in cal.get('preferred_setups',[]) and sec in cal.get('preferred_sectors',[]))
 if x.get('rr_ratio',0)>=2 and x.get('setup') in ['breakout','base_building','trend_follow'] and x.get('liquidity_score',0)>=50 and bt_ok:
  x={**x,'expected_horizon':'T+10','stop_rule':'trailing_low3_after_T3','holding_rule':'Tier A: T+10 max horizon; sau T+3 trailing stop theo low 3 phiên gần nhất; nếu bị đá ra sớm không vào lại nếu chưa có signal mới'}
  return 'Tier A',x,[]
 if x.get('setup') in ['breakout','trend_follow','pullback','base_building','reversal_attempt'] and x.get('rr_ratio',0)>=1.2:
  x={**x,'expected_horizon':'T+5 / confirm only','holding_rule':'Tier B: conditional/short watch; không giữ T+10 mặc định, chỉ nâng khi thành Tier A'}
  return 'Tier B',x,[x.get('entry_condition','cần xác nhận')]
 x={**x,'expected_horizon':'watch only','holding_rule':'Không mua'}
 return 'Watch',x,[x.get('entry_condition','watch_only'), 'R/R chưa đủ mạnh']
def main():
 ap=argparse.ArgumentParser(); ap.add_argument('--rr',default=str(OUT/'risk_reward_investable.json')); ap.add_argument('--leadership',default=str(OUT/'hose_leadership.json')); args=ap.parse_args()
 rr=json.loads(Path(args.rr).read_text(encoding='utf-8')); lead=json.loads(Path(args.leadership).read_text(encoding='utf-8'))
 sector_map={s['sector']:s['leadership_score'] for s in lead.get('sector_leadership',[])}
 tier_a=[]; tier_b=[]; watch=[]; rejected=[]
 regime=market_regime(); cal=calibration()
 for item in rr['items']:
  tier,x,reasons=tier_for(item,sector_map,regime,cal)
  if tier=='Tier A': tier_a.append(x)
  elif tier=='Tier B': tier_b.append({**x,'conditions':reasons})
  elif tier=='Rejected': rejected.append({**x,'reject_reasons':reasons})
  else: watch.append({**x,'conditions':reasons})
 tier_a.sort(key=lambda x:x['candidate_score'],reverse=True); tier_b.sort(key=lambda x:x['candidate_score'],reverse=True); watch.sort(key=lambda x:x['candidate_score'],reverse=True)
 passed=(tier_a+tier_b)[:10]
 res={'as_of':datetime.now().astimezone().isoformat(timespec='seconds'),'source':'signal_quality_gate','universe':'investable','market_regime':regime,'regime_rule':regime_rules(regime['regime']),'backtest_calibration':cal,'tier_a_count':len(tier_a),'tier_b_count':len(tier_b),'watch_count':len(watch),'rejected_count':len(rejected),'passed':passed,'tier_a':tier_a[:10],'tier_b':tier_b[:20],'watchlist':watch[:50],'rejected':rejected[:300]}
 save(OUT/'trade_candidates_final.json',res)
 md='# Trade Candidates Final — 3-Tier Quality Gate\n\n'+f"Market regime: {regime['regime']} | Rule: {regime_rules(regime['regime'])['reason']}\n\nTier A: {len(tier_a)} | Tier B: {len(tier_b)} | Watch: {len(watch)} | Rejected: {len(rejected)}\n\n"
 md+='## Tier A\n'+(md_table(['Ticker','Action','Score','R/R','Horizon','Entry condition'],[[x['ticker'],x['action_type'],x['candidate_score'],x['rr_ratio'],x.get('expected_horizon'),x['entry_condition']] for x in tier_a[:10]]) if tier_a else '- None')
 md+='\n\n## Tier B — conditional / short watch\n'+(md_table(['Ticker','Action','Score','R/R','Horizon','Condition'],[[x['ticker'],x['action_type'],x['candidate_score'],x['rr_ratio'],x.get('expected_horizon'),'; '.join(x.get('conditions',[]))] for x in tier_b[:20]]) if tier_b else '- None')
 md+='\n\n## Watch\n'+(md_table(['Ticker','Setup','Score','R/R','Condition'],[[x['ticker'],x['setup'],x['candidate_score'],x['rr_ratio'],'; '.join(x.get('conditions',[]))] for x in watch[:30]]) if watch else '- None')
 md+='\n\n## Rejected sample\n'+md_table(['Ticker','Setup','R/R','Reasons'],[[x['ticker'],x['setup'],x.get('rr_ratio'),' ; '.join(x.get('reject_reasons',[]))] for x in rejected[:80]])
 (OUT/'trade_candidates_final.md').write_text(md,encoding='utf-8')
 print('OK quality gate')
if __name__=='__main__': main()
