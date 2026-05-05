#!/usr/bin/env python
from __future__ import annotations
import argparse, json
from datetime import datetime
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; LIVE=ROOT/'data_live'; OUT=ROOT/'outputs'
def now(): return datetime.now().astimezone().isoformat(timespec='seconds')
def main():
 ap=argparse.ArgumentParser(); ap.add_argument('--pdf',default='data_live/raw/cafef_pdfs/FPT_69f07307d02b4661764f99bf.pdf'); ap.add_argument('--pages',default='6,11,16,21,26'); args=ap.parse_args()
 import fitz
 from paddleocr import PPStructureV3, PaddleOCR
 doc=fitz.open(str(ROOT/args.pdf)); pages=[int(x) for x in args.pages.split(',') if x.strip()]
 out=[]; OUT.mkdir(exist_ok=True)
 try: engine=PPStructureV3()
 except Exception as e: engine=None; struct_error=str(e)
 ocr=PaddleOCR(lang='en')
 for pno in pages:
  page=doc[pno-1]; img=OUT/f'paddle_page_{pno}.png'; page.get_pixmap(matrix=fitz.Matrix(3,3),alpha=False).save(str(img))
  rec={'page':pno,'image':str(img.relative_to(ROOT))}
  if engine:
   try:
    res=engine.predict(str(img)); rec['ppstructure_items']=len(res) if res else 0; rec['ppstructure_raw_head']=str(res)[:1000]
   except Exception as e: rec['ppstructure_error']=str(e)
  else: rec['ppstructure_error']=struct_error
  try:
   ores=ocr.predict(str(img)); rec['ocr_raw_head']=str(ores)[:1000]
  except Exception as e: rec['ocr_error']=str(e)
  out.append(rec)
 result={'as_of':now(),'source':'PaddleOCR/PP-Structure','pdf':args.pdf,'results':out}
 (LIVE/'paddle_structure_probe.vn.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps(result,ensure_ascii=False,indent=2)[:4000])
if __name__=='__main__': main()
