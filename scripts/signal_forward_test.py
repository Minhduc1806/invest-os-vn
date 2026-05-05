#!/usr/bin/env python
from __future__ import annotations
import json,argparse,statistics
from datetime import datetime
from pathlib import Path
from fdata_adapter import read_amibroker_dat
ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT/'outputs'
def save(p,x): p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf-8')
def md_table(h,rows):
 out=['| '+' | '.join(h)+' |','| '+' | '.join(['---']*len(h))+' |']
 for r in rows: out.append('| '+' | '.join(map(str,r))+' |')
 return '\n'.join(out)
def eval_one(sig):
 rows=read_amibroker_dat(Path(sig['raw_path'])); idx=next((i for i,r in enumerate(rows) if r['date']==sig['date']),None)
 if idx is None: return None
 entry=sig['close']; stop=sig.get('stop_loss') or entry*0.95; t1=sig.get('target_1') or entry*1.05
 out={'ticker':sig['ticker'],'tier':sig.get('tier'),'entry_date':sig['date'],'entry':entry,'stop':stop,'target_1':t1,'horizons':{}}
 future=rows[idx+1:idx+21]
 for h in [1,3,5,20]:
  w=future[:h]
  if not w: continue
  close=w[-1]['close']; maxh=max(r['high'] for r in w); minl=min(r['low'] for r in w)
  out['horizons'][f'T+{h}']={'return_pct':round((close/entry-1)*100,2),'mae_pct':round((minl/entry-1)*100,2),'mfe_pct':round((maxh/entry-1)*100,2),'target_hit':maxh>=t1,'stop_hit':minl<=stop}
 return out
def summarize(items,h):
 vals=[x['horizons'][h]['return_pct'] for x in items if h in x['horizons']]
 if not vals: return {'n':0}
 wins=sum(1 for v in vals if v>0); target=sum(1 for x in items if h in x['horizons'] and x['horizons'][h]['target_hit']); stop=sum(1 for x in items if h in x['horizons'] and x['horizons'][h]['stop_hit'])
 mae=[x['horizons'][h]['mae_pct'] for x in items if h in x['horizons']]
 return {'n':len(vals),'avg_return_pct':round(statistics.mean(vals),2),'win_rate_pct':round(wins/len(vals)*100,2),'target_hit_pct':round(target/len(vals)*100,2),'stop_hit_pct':round(stop/len(vals)*100,2),'avg_mae_pct':round(statistics.mean(mae),2)}
def main():
 ap=argparse.ArgumentParser(); ap.add_argument('--input',default=str(OUT/'trade_candidates_final.json')); args=ap.parse_args()
 d=json.loads(Path(args.input).read_text(encoding='utf-8'))
 sigs=[]
 for x in d.get('tier_a',[]): sigs.append({**x,'tier':'Tier A'})
 for x in d.get('tier_b',[])[:30]: sigs.append({**x,'tier':'Tier B'})
 tests=[r for s in sigs if (r:=eval_one(s))]
 summary={h:summarize(tests,h) for h in ['T+1','T+3','T+5','T+20']}
 res={'as_of':datetime.now().astimezone().isoformat(timespec='seconds'),'source':'signal_forward_test','note':'Uses current generated signals and future bars if available in local FData history; for latest date future may be empty until later sessions.','summary':summary,'items':tests}
 save(OUT/'signal_forward_test.json',res)
 md='# Signal Forward Test\n\n'+md_table(['Horizon','N','Avg return %','Win rate %','Target hit %','Stop hit %','Avg MAE %'],[[h,s.get('n',0),s.get('avg_return_pct'),s.get('win_rate_pct'),s.get('target_hit_pct'),s.get('stop_hit_pct'),s.get('avg_mae_pct')] for h,s in summary.items()])
 md+='\n\n## Items\n'+md_table(['Ticker','Tier','Entry date','Entry','T+1','T+3','T+5','T+20'],[[x['ticker'],x['tier'],x['entry_date'],x['entry'],x['horizons'].get('T+1',{}).get('return_pct'),x['horizons'].get('T+3',{}).get('return_pct'),x['horizons'].get('T+5',{}).get('return_pct'),x['horizons'].get('T+20',{}).get('return_pct')] for x in tests])
 (OUT/'signal_forward_test.md').write_text(md,encoding='utf-8')
 print('OK signal forward test')
if __name__=='__main__': main()
