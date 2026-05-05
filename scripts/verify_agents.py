#!/usr/bin/env python
from __future__ import annotations
import hashlib, json
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AGENTS = [
    'equity-technical-analyst',
    'financial-news-editor',
    'fundamental-analyst',
    'investment-data-designer',
    'market-strategist',
    'portfolio-advisor',
    'quant-researcher',
    'rates-fixed-income-analyst',
    'wealth-asset-manager',
]

def proof(path: Path):
    exists = path.exists()
    text = path.read_text(encoding='utf-8') if exists else ''
    return {
        'path': str(path.relative_to(ROOT)),
        'exists': exists,
        'read': exists,
        'bytes': len(text.encode('utf-8')),
        'sha256': hashlib.sha256(text.encode('utf-8')).hexdigest() if exists else None,
        'first_line': text.splitlines()[0] if text.splitlines() else '',
    }

def main():
    rows=[]
    for agent in AGENTS:
        rows.append({
            'agent': agent,
            'root_AGENTS_md': proof(ROOT/'AGENTS.md'),
            'runtime_AGENTS_md': proof(ROOT/'runtime_agents'/agent/'AGENTS.md'),
            'verified_read_both': (ROOT/'AGENTS.md').exists() and (ROOT/'runtime_agents'/agent/'AGENTS.md').exists(),
        })
    out={
        'as_of': datetime.now().astimezone().isoformat(timespec='seconds'),
        'method': 'verification script opened and hashed root AGENTS.md plus runtime_agents/<agent>/AGENTS.md for each configured agent',
        'agents': rows,
        'all_verified': all(r['verified_read_both'] for r in rows),
    }
    p=ROOT/'outputs'/'agent_verification.json'
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(out, ensure_ascii=False, indent=2))
if __name__=='__main__': main()
