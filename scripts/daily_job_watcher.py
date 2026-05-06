#!/usr/bin/env python
from __future__ import annotations
import json,sys
from datetime import datetime, timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT/'outputs'; LIVE=ROOT/'data_live'
def load(p):
 return json.loads(p.read_text(encoding='utf-8')) if p.exists() else {}
def parse_dt(v):
 try:
  t=str(v).replace('Z','+00:00'); d=datetime.fromisoformat(t); return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
 except Exception:
  return None
def jprint(obj):
 sys.stdout.reconfigure(encoding='utf-8', errors='replace')
 print(json.dumps(obj, ensure_ascii=False, indent=2))
def main():
 audit=load(OUT/'production_readiness_audit.json'); reg=load(OUT/'cafef_parser_regression.json'); market=load(LIVE/'market_snapshot.vn.json')
 failures=[]
 if audit.get('completion_pct')!=100: failures.append(f"completion_pct={audit.get('completion_pct')}")
 not_done=[l['name'] for l in audit.get('layers',[]) if not l.get('done')]
 if not_done: failures.append('layers_not_done='+','.join(not_done))
 if reg.get('status')!='ok': failures.append(f"cafef_regression={reg.get('status')}")
 market_as_of=parse_dt(market.get('as_of')); stale=market.get('stale')
 if stale is True: failures.append('market_snapshot_stale=true')
 elif market_as_of and (datetime.now().astimezone()-market_as_of).total_seconds()/60 > 30:
  failures.append('market_snapshot_stale>30m')
 status='failed' if failures else 'ok'
 out={'status':status,'failures':failures,'completion_pct':audit.get('completion_pct'),'not_done_layers':not_done,'cafef_regression':reg.get('status'),'market_snapshot_as_of':market.get('as_of'),'market_snapshot_stale':stale}
 (OUT/'daily_job_watch.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
 jprint(out)
 return 2 if failures else 0
if __name__=='__main__': raise SystemExit(main())
