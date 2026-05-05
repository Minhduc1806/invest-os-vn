#!/usr/bin/env python
from __future__ import annotations
import json, argparse
from datetime import datetime
from pathlib import Path
from typing import Any, Dict
ROOT=Path(__file__).resolve().parents[1]; LIVE=ROOT/'data_live'; OUT=ROOT/'outputs'
def save(p,x): p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf-8')
def md_table(h,rows):
 out=['| '+' | '.join(h)+' |','| '+' | '.join(['---']*len(h))+' |']
 for r in rows: out.append('| '+' | '.join(map(str,r))+' |')
 return '\n'.join(out)
def classify(b:Dict[str,Any])->tuple[str,list[str]]:
 c=b['close']; ma20=b.get('ma20',0); ma50=b.get('ma50',0); ma200=b.get('ma200',0); rsi=b.get('rsi14',50); vr=b.get('vol_ratio_20d',0); rs=b.get('rs_20d',0); ch=b.get('change_pct',0)
 reasons=[]
 if c<ma20 and ma20<ma50 and rs<-1.0: return 'avoid',['close<MA20','MA20<MA50','RS20 yếu']
 if c<ma20 and vr>1.2 and ch< -2: return 'distribution',['giảm dưới MA20 với volume cao']
 if c>ma20>ma50 and vr>=1.3 and ch>2 and rsi<75: return 'breakout',['close>MA20>MA50','volume xác nhận','giá tăng mạnh']
 if c>ma20>ma50 and 45<=rsi<=65 and abs(ch)<2: return 'trend_follow',['trend tăng ổn','RSI chưa quá nóng']
 if c>=ma20 and ma20>=ma50 and vr<1.0 and abs(ch)<1.5: return 'base_building',['nền trên MA20','volume chưa bùng nổ']
 if c>ma50 and c<ma20 and rsi>=40 and ch>0: return 'pullback',['pullback gần MA20','chưa gãy MA50']
 if c>ma20 and ma20<ma50 and ch>1 and vr>1: return 'reversal_attempt',['vượt MA20 nhưng MA20<MA50']
 if c>ma20 and ch<0 and vr>1.5: return 'failed_breakout',['giá trên MA20 nhưng bị bán volume cao']
 return 'avoid',['không đủ điều kiện setup']
def main():
 ap=argparse.ArgumentParser(); ap.add_argument('--input',default=str(LIVE/'fdata_investable_bars.json')); args=ap.parse_args()
 data=json.loads(Path(args.input).read_text(encoding='utf-8')); rows=[]
 for b in data.get('bars',[]):
  setup,reasons=classify(b); x={**b,'setup':setup,'setup_reasons':reasons}; rows.append(x)
 rows.sort(key=lambda x:({'breakout':0,'trend_follow':1,'pullback':2,'base_building':3,'reversal_attempt':4,'failed_breakout':5,'distribution':6,'avoid':7}.get(x['setup'],9),-x.get('liquidity_score',0)))
 res={'as_of':datetime.now().astimezone().isoformat(timespec='seconds'),'source':'technical_setup_engine','universe':'investable','count':len(rows),'setups':rows}
 save(OUT/'technical_setups_investable.json',res)
 md='# Technical Setups — Investable Universe\n\n'+md_table(['Ticker','Setup','Close','%','RS20','RSI','VolRatio','Reasons'],[[x['ticker'],x['setup'],x['close'],x['change_pct'],x['rs_20d'],x['rsi14'],x['vol_ratio_20d'],'; '.join(x['setup_reasons'])] for x in rows])
 (OUT/'technical_setups_investable.md').write_text(md,encoding='utf-8')
 print('OK technical setups')
if __name__=='__main__': main()
