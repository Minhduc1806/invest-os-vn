#!/usr/bin/env python
from __future__ import annotations
import json,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT/'outputs'
def main():
 report=(OUT/'eod_vn_report.md').read_text(encoding='utf-8')
 data=json.loads((OUT/'trade_candidates_final.json').read_text(encoding='utf-8'))
 html='<html><head><meta charset="utf-8"><style>body{font-family:Arial;max-width:1000px;margin:auto;line-height:1.5} table{border-collapse:collapse}td,th{border:1px solid #ddd;padding:4px}</style></head><body>'+report.replace('\n','<br>')+'</body></html>'
 (OUT/'eod_vn_report.html').write_text(html,encoding='utf-8')
 tier_a=', '.join(x['ticker'] for x in data.get('tier_a',[])[:10]) or 'Không có'
 tier_b=', '.join(x['ticker'] for x in data.get('tier_b',[])[:10]) or 'Không có'
 digest=f"EOD VN digest\nTier A: {tier_a}\nTier B: {tier_b}\nXem full: outputs/eod_vn_report.md\nCảnh báo: chỉ hành động theo entry condition, không mua đuổi."
 (OUT/'telegram_digest.txt').write_text(digest,encoding='utf-8')
 print('OK digest/html')
if __name__=='__main__': main()
