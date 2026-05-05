#!/usr/bin/env python
from __future__ import annotations
import json,argparse
from collections import Counter
from datetime import datetime
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT/'outputs'; MOCK=ROOT/'mock_data'
def save(p,x): p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf-8')
def md_table(h,rows):
 out=['| '+' | '.join(h)+' |','| '+' | '.join(['---']*len(h))+' |']
 for r in rows: out.append('| '+' | '.join(map(str,r))+' |')
 return '\n'.join(out)
def main():
 ap=argparse.ArgumentParser(); ap.add_argument('--portfolio',default=str(ROOT/'data_live'/'portfolio_real.json')); args=ap.parse_args()
 if not Path(args.portfolio).exists(): args.portfolio=str(MOCK/'portfolio_sample.json')
 pf=json.loads(Path(args.portfolio).read_text(encoding='utf-8')); gate=json.loads((OUT/'trade_candidates_final.json').read_text(encoding='utf-8'))
 regime=gate.get('market_regime',{}).get('regime'); no_new_buy=regime!='risk_on'
 tier_a={x['ticker']:x for x in gate.get('tier_a',[])}; tier_b={x['ticker']:x for x in gate.get('tier_b',[])}; watch={x['ticker']:x for x in gate.get('watchlist',[])}; rej={x['ticker']:x for x in gate.get('rejected',[])}
 cash=pf.get('cash_vnd',0); nav=cash+sum(p['quantity']*p['last_price'] for p in pf.get('positions',[])); holdings=[]; sector=Counter()
 for p in pf.get('positions',[]):
  val=p['quantity']*p['last_price']; w=val/nav*100 if nav else 0; t=p['ticker']; sector[p.get('sector','unknown')]+=w
  if t in tier_a: bucket='Tier A'; action='GIỮ / có thể gia tăng theo entry condition'; target=min(20,w+3)
  elif t in tier_b: bucket='Tier B'; action='GIỮ, chỉ mua thêm khi điều kiện xác nhận xảy ra'; target=w
  elif t in watch: bucket='Watch'; action='GIỮ nhỏ / không mua thêm'; target=min(w,10)
  elif t in rej: bucket='Rejected'; action='GIẢM rủi ro / không mua thêm'; target=max(0,w-5)
  else: bucket='Not ranked'; action='GIỮ nếu thesis riêng còn đúng, không tăng tỷ trọng từ hệ thống'; target=w
  holdings.append({'ticker':t,'sector':p.get('sector'),'weight_pct':round(w,2),'bucket':bucket,'action':action,'target_weight_pct':round(target,2)})
 new=[]
 for t,x in tier_a.items():
  if not any(h['ticker']==t for h in holdings): new.append({'ticker':t,'bucket':'Tier A','action':'WATCH ONLY - NO NEW BUY' if no_new_buy else 'CHỜ MUA theo entry condition','entry_condition':x.get('entry_condition'),'suggested_weight_pct':0 if no_new_buy else 5})
 conditional=[]
 for t,x in tier_b.items():
  if not any(h['ticker']==t for h in holdings): conditional.append({'ticker':t,'bucket':'Tier B','action':'CONDITIONAL WATCH - không mua mới nếu chưa lên Tier A','entry_condition':x.get('entry_condition'),'suggested_weight_pct':0})
 risks=[]
 for sec,w in sector.items():
  if w>35: risks.append(f'Tập trung ngành {sec}: {w:.1f}% NAV')
 if nav>0 and cash/nav<0.1: risks.append('Cash <10% NAV, hạn chế mua mới')
 if nav<=0: risks.append('Portfolio real chưa nhập NAV/cash/positions')
 res={'as_of':datetime.now().astimezone().isoformat(timespec='seconds'),'source':'portfolio_action_report','market_regime':regime,'no_new_buy':no_new_buy,'nav_vnd':nav,'cash_vnd':cash,'holdings':holdings,'new_buy_watch':new[:10],'conditional_watch':conditional[:20],'sector_weights':dict(sector),'concentration_risks':risks}
 save(OUT/'portfolio_action_report.json',res)
 md='# Portfolio Action Report\n\n'+f"NAV: {nav:,.0f} | Cash: {cash:,.0f}\n\n"
 md+='## Holdings\n'+md_table(['Ticker','Sector','Weight %','Bucket','Action','Target %'],[[h['ticker'],h['sector'],h['weight_pct'],h['bucket'],h['action'],h['target_weight_pct']] for h in holdings])
 md+='\n\n## New buy watch — Tier A only\n'+(md_table(['Ticker','Bucket','Suggested %','Entry condition'],[[x['ticker'],x['bucket'],x['suggested_weight_pct'],x['entry_condition']] for x in new[:10]]) if new else '- None')
 md+='\n\n## Conditional watch — Tier B, no sizing\n'+(md_table(['Ticker','Bucket','Suggested %','Entry condition'],[[x['ticker'],x['bucket'],x['suggested_weight_pct'],x['entry_condition']] for x in conditional[:20]]) if conditional else '- None')
 md+='\n\n## Sector concentration\n'+md_table(['Sector','Weight %'],[[k,round(v,2)] for k,v in sector.items()])
 md+='\n\n## Risks\n'+('\n'.join('- '+r for r in risks) if risks else '- None')
 (OUT/'portfolio_action_report.md').write_text(md,encoding='utf-8')
 print('OK portfolio action report')
if __name__=='__main__': main()
