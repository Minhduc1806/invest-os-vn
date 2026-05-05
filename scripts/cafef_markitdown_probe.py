#!/usr/bin/env python
"""Probe MarkItDown extraction quality for CafeF financial PDFs."""
from __future__ import annotations
import argparse, json
from datetime import datetime
from pathlib import Path
from markitdown import MarkItDown
ROOT=Path(__file__).resolve().parents[1]; LIVE=ROOT/'data_live'; OUT=ROOT/'outputs'
def now_iso(): return datetime.now().astimezone().isoformat(timespec='seconds')
def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--structured',default='data_live/cafef_financial_statements_structured.vn.json'); args=ap.parse_args()
    d=json.loads((ROOT/args.structured).read_text(encoding='utf-8'))
    md=MarkItDown(); results=[]
    OUT.mkdir(exist_ok=True)
    for doc in d.get('documents',[]):
        p=ROOT/doc.get('pdf_path','')
        try:
            res=md.convert(str(p)); text=res.text_content or ''
            out_md=OUT/f"markitdown_{doc.get('ticker')}_{doc.get('document',{}).get('id')}.md"
            out_md.write_text(text,encoding='utf-8')
            results.append({'ticker':doc.get('ticker'),'pdf_path':str(p.relative_to(ROOT)),'markdown_path':str(out_md.relative_to(ROOT)),'chars':len(text),'status':'ok' if text.strip() else 'empty_output'})
        except Exception as e:
            results.append({'ticker':doc.get('ticker'),'pdf_path':str(p),'chars':0,'status':'error','error':str(e)})
    out={'as_of':now_iso(),'source':'microsoft/markitdown','results':results,'parse_quality':{'required_passed':any(r.get('chars',0)>0 for r in results),'warnings':[f"{r['ticker']}:{r['status']}" for r in results if r.get('status')!='ok']}}
    (LIVE/'cafef_markitdown_probe.vn.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(out,ensure_ascii=False,indent=2))
if __name__=='__main__': main()
