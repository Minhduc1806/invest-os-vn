#!/usr/bin/env python
from __future__ import annotations
import argparse, json, shutil, subprocess
from datetime import datetime
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; LIVE=ROOT/'data_live'; OUT=ROOT/'outputs'
def now(): return datetime.now().astimezone().isoformat(timespec='seconds')
def main():
 ap=argparse.ArgumentParser(); ap.add_argument('--pdf',default='data_live/raw/cafef_pdfs/FPT_69f07307d02b4661764f99bf.pdf'); ap.add_argument('--page',type=int,default=6); args=ap.parse_args()
 exe=shutil.which('tesseract') or ('C:\\Program Files\\Tesseract-OCR\\tesseract.exe' if Path('C:/Program Files/Tesseract-OCR/tesseract.exe').exists() else None)
 result={'as_of':now(),'source':'Tesseract + OpenCV grid reconstruction','available':bool(exe),'tesseract_path':exe}
 if not exe:
  result['error']='tesseract executable missing; winget installer blocked by Windows installer lock, direct Mannheim download returned 403'
 else:
  import fitz, cv2, numpy as np
  doc=fitz.open(str(ROOT/args.pdf)); img=OUT/f'tesseract_page_{args.page}.png'; doc[args.page-1].get_pixmap(matrix=fitz.Matrix(3,3),alpha=False).save(str(img))
  mat=cv2.imread(str(img),0); th=cv2.threshold(mat,0,255,cv2.THRESH_BINARY_INV+cv2.THRESH_OTSU)[1]
  horiz=cv2.morphologyEx(th,cv2.MORPH_OPEN,cv2.getStructuringElement(cv2.MORPH_RECT,(60,1)))
  vert=cv2.morphologyEx(th,cv2.MORPH_OPEN,cv2.getStructuringElement(cv2.MORPH_RECT,(1,30)))
  grid=cv2.add(horiz,vert); contours,_=cv2.findContours(grid,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
  boxes=[cv2.boundingRect(c) for c in contours if cv2.contourArea(c)>100]
  text=subprocess.check_output([exe,str(img),'stdout','-l','vie+eng','--psm','6'],text=True,errors='replace',timeout=120)
  result.update({'image':str(img.relative_to(ROOT)),'grid_boxes':len(boxes),'text_head':text[:2000]})
 (LIVE/'tesseract_grid_probe.vn.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps(result,ensure_ascii=False,indent=2))
if __name__=='__main__': main()
