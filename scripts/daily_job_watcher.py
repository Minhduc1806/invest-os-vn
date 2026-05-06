#!/usr/bin/env python
from __future__ import annotations
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT/'outputs'
def load(p):
 return json.loads(p.read_text(encoding='utf-8')) if p.exists() else {}
def main():
 audit=load(OUT/'production_readiness_audit.json'); reg=load(OUT/'cafef_parser_regression.json')
 failures=[]
 if audit.get('completion_pct')!=100: failures.append(f"completion_pct={audit.get('completion_pct')}")
 not_done=[l['name'] for l in audit.get('layers',[]) if not l.get('done')]
 if not_done: failures.append('layers_not_done='+','.join(not_done))
 if reg.get('status')!='ok': failures.append(f"cafef_regression={reg.get('status')}")
 status='failed' if failures else 'ok'
 out={'status':status,'failures':failures,'completion_pct':audit.get('completion_pct'),'not_done_layers':not_done,'cafef_regression':reg.get('status')}
 (OUT/'daily_job_watch.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps(out,ensure_ascii=False,indent=2))
 return 2 if failures else 0
if __name__=='__main__': raise SystemExit(main())
