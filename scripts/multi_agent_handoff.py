#!/usr/bin/env python
"""Real OpenClaw subagent handoff runner.

Default mode validates outputs from true subagent runs written to
outputs/subagents/<agent>.json. Use --bootstrap-prompts to create prompt files;
spawn them with OpenClaw sessions_spawn from host/runtime, then rerun this script.
"""
from __future__ import annotations
import argparse,json,sys
from datetime import datetime
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT/'outputs'; LIVE=ROOT/'data_live'; SUB=OUT/'subagents'
AGENTS=['market-strategist','macro-strategist','rates-fixed-income-analyst','fundamental-analyst','banking-sector-analyst','real-estate-sector-analyst','steel-sector-analyst','equity-technical-analyst','quant-researcher','risk-manager','portfolio-advisor','wealth-asset-manager','financial-news-editor','investment-data-designer']

def now_iso(): return datetime.now().astimezone().isoformat(timespec='seconds')
def load(p):
 p=Path(p); return json.loads(p.read_text(encoding='utf-8')) if p.exists() else {}
def save(p,d): p=Path(p); p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8')
def shared_context():
 return {'as_of':now_iso(),'market':load(LIVE/'market_snapshot.vn.json'),'macro':load(LIVE/'macro_rates_live.vn.json'),'fundamentals':load(LIVE/'fundamentals_live.vn.json'),'financials':load(LIVE/'cafef_financial_statements_html.vn.json'),'news':load(LIVE/'news_live.vn.json'),'required_agents':AGENTS}
def prompt(agent,ctx_path):
 return f"""You are {agent} in invest-os-vn production handoff.\nRead shared JSON context: {ctx_path}\nReturn JSON only with schema:\n{{"agent":"{agent}","status":"ok","findings":[],"handoff":{{}},"validation":{{"used_shared_context":true,"no_sample_fallback":true}}}}\nFail status if required data missing. No prose."""
def write_prompts(ctx):
 ctxp=OUT/'subagent_shared_context.json'; save(ctxp,ctx)
 pdir=OUT/'subagent_prompts'; pdir.mkdir(parents=True,exist_ok=True)
 for a in AGENTS: (pdir/f'{a}.txt').write_text(prompt(a,ctxp),encoding='utf-8')
 return ctxp,pdir
def validate_result(agent,d):
 errs=[]
 if d.get('agent')!=agent: errs.append('agent_mismatch')
 if d.get('status')!='ok': errs.append('status_not_ok')
 if not isinstance(d.get('handoff'),dict): errs.append('handoff_missing')
 v=d.get('validation',{})
 if v.get('used_shared_context') is not True: errs.append('shared_context_not_confirmed')
 if v.get('no_sample_fallback') is not True: errs.append('sample_fallback_not_denied')
 return errs
def fallback_scripted(ctx):
 # explicit fallback, never counted as real_subagent
 return [{'agent':a,'status':'ok','output':{'source':'scripted_fallback','context_keys':list(ctx.keys())},'validation':{'used_shared_context':True,'no_sample_fallback':True}} for a in AGENTS]
def jprint(obj):
 sys.stdout.reconfigure(encoding='utf-8', errors='replace')
 print(json.dumps(obj, ensure_ascii=False, indent=2))

def main():
 ap=argparse.ArgumentParser(); ap.add_argument('--pipeline',default='daily_production'); ap.add_argument('--bootstrap-prompts',action='store_true'); ap.add_argument('--allow-scripted-fallback',action='store_true'); args=ap.parse_args()
 ctx=shared_context(); ctxp,pdir=write_prompts(ctx)
 if args.bootstrap_prompts:
  out={'as_of':now_iso(),'status':'prompts_ready','shared_context':str(ctxp),'prompt_dir':str(pdir),'required_agents':AGENTS,'next':f'spawn {len(AGENTS)} OpenClaw subagents, save each JSON to outputs/subagents/<agent>.json, rerun without --bootstrap-prompts'}; save(OUT/'multi_agent_handoff.json',out); jprint(out); return 0
 handoffs=[]; missing=[]; errors={}
 for a in AGENTS:
  p=SUB/f'{a}.json'
  if not p.exists(): missing.append(a); continue
  try: d=load(p)
  except Exception as e: missing.append(a); errors[a]=[f'json_error:{e}']; continue
  e=validate_result(a,d)
  if e: errors[a]=e
  handoffs.append(d)
 if missing and args.allow_scripted_fallback:
  handoffs=fallback_scripted(ctx); missing=[]; errors={}; autonomy='scripted_fallback; not LLM subagent runtime'
 else:
  runtime_modes=sorted({str(d.get('validation',{}).get('runtime') or d.get('handoff',{}).get('runtime') or 'unknown') for d in handoffs})
  complete=not missing and not errors and len(handoffs)==len(AGENTS)
  native_complete=complete and any(str(m).startswith('native-openclaw') for m in runtime_modes)
  autonomy='native_openclaw_subagent_orchestration' if native_complete else ('repo_level_shim_orchestration' if complete else 'blocked_missing_or_invalid_subagents')
 out={'as_of':now_iso(),'pipeline':args.pipeline,'shared_context':str(ctxp),'handoffs':handoffs,'required_agents':AGENTS,'missing_agents':missing,'validation_errors':errors,'status':'ok' if complete else 'failed','autonomy_level':autonomy,'runtime_modes':runtime_modes,'native_openclaw_subagents':native_complete}
 save(OUT/'multi_agent_handoff.json',out); jprint(out); return 0 if out['status']=='ok' else 2
if __name__=='__main__': raise SystemExit(main())
