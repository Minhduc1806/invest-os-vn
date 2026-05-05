#!/usr/bin/env python
from __future__ import annotations
import json, shutil, subprocess, sys
from datetime import datetime
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; LIVE=ROOT/'data_live'
def now(): return datetime.now().astimezone().isoformat(timespec='seconds')
def main():
 r={'as_of':now(),'engines':{}}
 # RapidOCR
 try:
  import rapidocr_onnxruntime, onnxruntime
  r['engines']['rapidocr_onnxruntime']={'available':True,'module':str(rapidocr_onnxruntime),'onnxruntime':onnxruntime.__version__}
 except Exception as e: r['engines']['rapidocr_onnxruntime']={'available':False,'error':str(e)}
 # PaddleOCR / PP-Structure
 try:
  import paddleocr
  ok=True; err=None
  try:
   import paddle
   paddle_ver=paddle.__version__
  except Exception as e:
   ok=False; err='paddle runtime missing; Python 3.14 has no paddlepaddle wheel'
   paddle_ver=None
  r['engines']['paddleocr_ppstructure']={'available':ok,'paddleocr_version':getattr(paddleocr,'__version__',None),'paddle_version':paddle_ver,'error':err}
 except Exception as e: r['engines']['paddleocr_ppstructure']={'available':False,'error':str(e)}
 # Tesseract
 exe=shutil.which('tesseract') or ('C:\\Program Files\\Tesseract-OCR\\tesseract.exe' if Path('C:/Program Files/Tesseract-OCR/tesseract.exe').exists() else None)
 if exe:
  try: ver=subprocess.check_output([exe,'--version'],text=True,errors='replace',timeout=10).splitlines()[0]
  except Exception as e: ver=str(e)
  r['engines']['tesseract']={'available':True,'path':exe,'version':ver}
 else:
  r['engines']['tesseract']={'available':False,'error':'not installed or not on PATH; winget installer hung/was terminated'}
 (LIVE/'ocr_engine_probe.vn.json').write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps(r,ensure_ascii=False,indent=2))
if __name__=='__main__': main()
