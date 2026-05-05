#!/usr/bin/env python
from __future__ import annotations
import json,argparse,math
from datetime import datetime
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT/'outputs'
def save(p,x): p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf-8')
def pf(x): return f'{x:.2f}'
def md_table(h,rows):
 out=['| '+' | '.join(h)+' |','| '+' | '.join(['---']*len(h))+' |']
 for r in rows: out.append('| '+' | '.join(map(str,r))+' |')
 return '\n'.join(out)
def rr_for(x, sr_map):
 c=x['close']; atr=x.get('atr14_pct',2.5); setup=x['setup']; liq=x.get('liquidity_score',50); sr=sr_map.get(x['ticker'],{})
 entry_low=c*0.98; entry_high=c*1.01
 mult={'breakout':1.8,'trend_follow':1.6,'pullback':1.4,'base_building':1.5,'reversal_attempt':2.0,'failed_breakout':1.2,'distribution':1.0,'avoid':1.0}.get(setup,1.5)
 support=sr.get('support_nearest') or c*(1-max(atr*mult/100,0.035))
 resistance=sr.get('resistance_nearest') or c*(1+atr*2/100)
 next_res=sr.get('next_resistance') or sr.get('rolling_high_60d') or resistance*1.08
 high20=sr.get('rolling_high_20d') or resistance; high60=sr.get('rolling_high_60d') or next_res; high120=sr.get('rolling_high_120d') or next_res
 stop=min(c*(1-max(atr*mult/100,0.035)), support*0.985)
 risk=c-stop
 atr_t1=c+risk*1.5; atr_t2=c+risk*2.5
 # true targets use nearby resistance/swing high first, then ATR expansion if breakout already above resistance
 dist_res=(resistance/c-1) if c else 0
 swing=sr.get('swing_high_60d') or atr_t2
 if setup=='breakout':
  if c > resistance*1.01:
   t1=max(next_res, high60, atr_t1); entry_condition='buy_now_candidate if breakout holds above old resistance with volume > 1.3x'
  else:
   t1=max(next_res, high60, resistance*1.06, atr_t1); entry_condition=f'buy_on_breakout: chỉ mua nếu đóng cửa > {resistance:.2f} và volume > 1.3x'
 elif setup in ['pullback','trend_follow','base_building']:
  near_support=(c/support-1) if support else 9; near_res=(resistance/c-1) if c else 9
  if near_res < 0.03:
   t1=max(next_res, high60, atr_t1); entry_condition=f'buy_on_breakout: giá sát kháng cự, chỉ mua nếu đóng cửa > {resistance:.2f} và volume > 1.3x'
  elif near_support <= 0.04:
   t1=min(resistance, atr_t2) if resistance>c else max(next_res, atr_t1); entry_condition=f'buy_on_pullback: mua gần hỗ trợ {support:.2f}, không mua đuổi'
  else:
   t1=max(resistance, high20, atr_t1); entry_condition=f'watch_only: chờ pullback về hỗ trợ {support:.2f} hoặc vượt kháng cự {resistance:.2f}'
 else:
  t1=min(resistance, atr_t1); entry_condition='watch_only/avoid: setup chưa đủ điều kiện'
 t2=max(swing, t1+risk) if setup in ['breakout','trend_follow'] else max(t1+risk, atr_t2)
 rr=(t1-c)/risk if risk>0 else 0
 action_type='buy_now_candidate' if ('buy_now_candidate' in entry_condition and rr>=2) else 'buy_on_breakout' if entry_condition.startswith('buy_on_breakout') else 'buy_on_pullback' if entry_condition.startswith('buy_on_pullback') else 'watch_only' if setup not in ['avoid','distribution','failed_breakout'] else 'avoid'
 atr_risk='high' if atr>5 else 'medium' if atr>3 else 'low'
 liquidity_risk='high' if liq<35 else 'medium' if liq<55 else 'low'
 pos=0 if setup in ['avoid','distribution','failed_breakout'] else 0.25 if atr_risk=='high' or liquidity_risk=='high' else 0.5 if rr<2 else 1.0
 return {**x,'support_nearest':sr.get('support_nearest'),'resistance_nearest':sr.get('resistance_nearest'),'next_resistance':next_res,'rolling_high_20d':high20,'rolling_high_60d':high60,'rolling_high_120d':high120,'swing_high_60d':sr.get('swing_high_60d'),'entry_zone':f'{entry_low:.2f}-{entry_high:.2f}','entry_condition':entry_condition,'action_type':action_type,'stop_loss':round(stop,2),'target_1':round(t1,2),'target_2':round(t2,2),'rr_ratio':round(rr,2),'rr_strength':'strong' if rr>=2 else 'weak' if rr<1.5 else 'acceptable','atr_risk':atr_risk,'liquidity_risk':liquidity_risk,'invalidation':f'Đóng cửa dưới {stop:.2f} hoặc setup {setup} thất bại với volume cao.','position_sizing_suggestion':f'{pos}% NAV risk budget unit'}
def main():
 ap=argparse.ArgumentParser(); ap.add_argument('--input',default=str(OUT/'technical_setups_investable.json')); args=ap.parse_args()
 data=json.loads(Path(args.input).read_text(encoding='utf-8'))
 sr_path=OUT/'resistance_support_investable.json'; sr_map={}
 if sr_path.exists():
  sr=json.loads(sr_path.read_text(encoding='utf-8')); sr_map={x['ticker']:x for x in sr.get('items',[])}
 rows=[rr_for(x,sr_map) for x in data['setups']]
 res={'as_of':datetime.now().astimezone().isoformat(timespec='seconds'),'source':'risk_reward_engine','universe':'investable','count':len(rows),'items':rows}
 save(OUT/'risk_reward_investable.json',res)
 md='# Risk / Reward — Investable Universe\n\n'+md_table(['Ticker','Action','Setup','Entry condition','Stop','Resistance','T1','T2','R/R','Strength','Sizing'],[[x['ticker'],x['action_type'],x['setup'],x['entry_condition'],x['stop_loss'],x.get('resistance_nearest'),x['target_1'],x['target_2'],x['rr_ratio'],x['rr_strength'],x['position_sizing_suggestion']] for x in rows])
 (OUT/'risk_reward_investable.md').write_text(md,encoding='utf-8')
 print('OK risk reward')
if __name__=='__main__': main()
