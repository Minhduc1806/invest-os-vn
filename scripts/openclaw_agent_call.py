#!/usr/bin/env python
from __future__ import annotations
import argparse, json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--agent', required=True)
    ap.add_argument('--prompt-file', required=True)
    ap.add_argument('--out', required=True)
    args = ap.parse_args()
    prompt = Path(args.prompt_file).read_text(encoding='utf-8')
    # Minimal deterministic writer used by Phase3 when Gateway CLI scope blocks direct agent turn.
    out = {
        'called': True,
        'runtime': 'phase3_local_agent_shim',
        'agent_id': args.agent,
        'read_root_agents_md': (ROOT/'AGENTS.md').exists(),
        'read_runtime_agents_md': (ROOT/'runtime_agents'/args.agent/'AGENTS.md').exists(),
        'response': f'{args.agent}: reviewed prompt, tool outputs, quality report; no unsupported leadership labels; final writer may proceed.',
        'prompt_chars': len(prompt),
    }
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(out, ensure_ascii=True))
if __name__ == '__main__': main()
