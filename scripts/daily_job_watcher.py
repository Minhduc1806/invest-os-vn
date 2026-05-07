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
 audit=load(OUT/'production_readiness_audit.json'); reg=load(OUT/'cafef_parser_regression.json'); market=load(LIVE/'market_snapshot.vn.json'); cp68=load(LIVE/'cophieu68_market_data.vn.json'); fdata=load(LIVE/'fdata_investable_bars.json')
 failures=[]
 if audit.get('completion_pct')!=100: failures.append(f"completion_pct={audit.get('completion_pct')}")
 not_done=[l['name'] for l in audit.get('layers',[]) if not l.get('done')]
 if not_done: failures.append('layers_not_done='+','.join(not_done))
 if audit.get('source_policy')!='cophieu68_primary_legacy_fallback': failures.append('source_policy_not_cophieu68_primary')
 if not audit.get('cophieu68_primary_ok'): failures.append('cophieu68_primary_ok=false')
 market_as_of=parse_dt(market.get('as_of')); stale=market.get('stale')
 cp68_as_of=parse_dt(cp68.get('as_of')); cp68_ok=cp68.get('status')=='ok' and len((cp68.get('amibroker_ohlcv') or {}).get('bars') or [])>=1000
 cp68_fresh=bool(cp68_as_of and (datetime.now().astimezone()-cp68_as_of).total_seconds()/60 <= 30)
 if market.get('source')!='cophieu68_amibroker_ohlcv': failures.append(f"market_source={market.get('source')}")
 if fdata.get('source')!='cophieu68_amibroker_ohlcv': failures.append(f"ohlcv_source={fdata.get('source')}")
 if stale is True: failures.append('market_snapshot_stale=true')
 elif market_as_of and (datetime.now().astimezone()-market_as_of).total_seconds()/60 > 30 and not (cp68_ok and cp68_fresh):
  failures.append('market_snapshot_stale>30m')
 status='failed' if failures else 'ok'
 out={'status':status,'failures':failures,'completion_pct':audit.get('completion_pct'),'not_done_layers':not_done,'source_policy':audit.get('source_policy'),'cophieu68_primary_ok':audit.get('cophieu68_primary_ok'),'legacy_cafef_regression':reg.get('status'),'market_snapshot_as_of':market.get('as_of'),'market_snapshot_stale':stale,'market_source':market.get('source'),'ohlcv_source':fdata.get('source'),'cophieu68_as_of':cp68.get('as_of'),'cophieu68_market_snapshot_ok':cp68_ok}
 (OUT/'daily_job_watch.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
 jprint(out)
 return 2 if failures else 0
if __name__=='__main__': raise SystemExit(main())
