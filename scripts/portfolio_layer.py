#!/usr/bin/env python
from __future__ import annotations
import json,argparse
from datetime import datetime
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT/'outputs'; MOCK=ROOT/'mock_data'
def save(p,x): p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf-8')
def md_table(h,rows):
 out=['| '+' | '.join(h)+' |','| '+' | '.join(['---']*len(h))+' |']
 for r in rows: out.append('| '+' | '.join(map(str,r))+' |')
 return '\n'.join(out)
def main():
 ap=argparse.ArgumentParser(); ap.add_argument('--portfolio',default=str(MOCK/'portfolio_sample.json')); ap.add_argument('--candidates',default=str(OUT/'trade_candidates_final.json')); args=ap.parse_args()
 pf=json.loads(Path(args.portfolio).read_text(encoding='utf-8')); cand=json.loads(Path(args.candidates).read_text(encoding='utf-8'))
 passed={x['ticker']:x for x in cand.get('passed',[])}; watch={x['ticker']:x for x in cand.get('watchlist',[])}
 cash=pf.get('cash_vnd',0); positions=[]; actions=[]; total=cash
 for p in pf.get('positions',[]): total+=p['quantity']*p['last_price']
 for p in pf.get('positions',[]):
  val=p['quantity']*p['last_price']; w=val/total*100 if total else 0; t=p['ticker']
  if t in passed: act='GIỮ / có thể gia tăng nếu đúng entry, không vượt max position'
  elif t in watch: act='GIỮ quan sát, chưa mua thêm'
  else: act='GIẢM/không tăng nếu yếu hơn Top10 hoặc bị loại quality gate'
  positions.append({'ticker':t,'value_vnd':val,'weight_pct':round(w,2),'in_top10':t in passed,'in_watch':t in watch,'action':act})
 for t,x in passed.items():
  if not any(p['ticker']==t for p in positions): actions.append({'ticker':t,'action':'CHỜ MUA','suggested_weight_pct':min(5, max(2, x.get('candidate_score',50)/20)),'entry_zone':x['entry_zone']})
 res={'as_of':datetime.now().astimezone().isoformat(timespec='seconds'),'source':'portfolio_layer','account_id':pf.get('account_id'),'nav_vnd':total,'cash_vnd':cash,'positions':positions,'new_buy_watch':actions[:10]}
 save(OUT/'portfolio_actions.json',res)
 md='# Portfolio Layer\n\n'+f"NAV: {total:,.0f} | Cash: {cash:,.0f}\n\n"
 md+='## Holdings actions\n'+md_table(['Ticker','Weight %','Top10','Watch','Action'],[[p['ticker'],p['weight_pct'],p['in_top10'],p['in_watch'],p['action']] for p in positions])
 md+='\n\n## New buy watch from Top10\n'+md_table(['Ticker','Action','Suggested weight %','Entry'],[[a['ticker'],a['action'],round(a['suggested_weight_pct'],2),a['entry_zone']] for a in actions[:10]])
 (OUT/'portfolio_actions.md').write_text(md,encoding='utf-8')
 print('OK portfolio layer')
if __name__=='__main__': main()
