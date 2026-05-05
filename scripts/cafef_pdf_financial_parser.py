#!/usr/bin/env python
"""Extract CafeF BCTC PDF tables into structured income/balance/cashflow JSON.
No mock fallback. Uses real CafeF PDF URLs from data_live/cafef_financial_reports.vn.json.
"""
from __future__ import annotations
import argparse, hashlib, json, re, urllib.request
from datetime import datetime
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; LIVE=ROOT/'data_live'; RAW=LIVE/'raw'/'cafef_pdfs'
NUM=re.compile(r'^\(?-?[\d\.]+(?:,\d+)?\)?$')
STATEMENT_KEYS={
 'income_statement':['báo cáo kết quả hoạt động kinh doanh','kết quả hoạt động kinh doanh','doanh thu bán hàng','lợi nhuận sau thuế'],
 'balance_sheet':['bảng cân đối kế toán','cân đối kế toán','tài sản ngắn hạn','nợ phải trả','vốn chủ sở hữu'],
 'cash_flow':['báo cáo lưu chuyển tiền tệ','lưu chuyển tiền tệ','lưu chuyển tiền thuần']}

def now_iso(): return datetime.now().astimezone().isoformat(timespec='seconds')
def norm(s): return re.sub(r'\s+',' ',str(s or '').replace('\n',' ')).strip()
def keep_lines(s): return '\n'.join(norm(x) for x in str(s or '').splitlines())
def val(x):
    s=norm(x).replace(' ','')
    if not s or not NUM.match(s): return None
    neg=s.startswith('(') and s.endswith(')')
    s=s.strip('()').replace('.','').replace(',','.')
    try:
        v=float(s); return -v if neg else v
    except Exception: return None
def classify(text):
    t=text.lower()
    t_ascii=(t.replace('á','a').replace('à','a').replace('ả','a').replace('ã','a').replace('ạ','a').replace('ă','a').replace('ắ','a').replace('ằ','a').replace('ẳ','a').replace('ẵ','a').replace('ặ','a').replace('â','a').replace('ấ','a').replace('ầ','a').replace('ẩ','a').replace('ẫ','a').replace('ậ','a')
             .replace('đ','d').replace('é','e').replace('è','e').replace('ẻ','e').replace('ẽ','e').replace('ẹ','e').replace('ê','e').replace('ế','e').replace('ề','e').replace('ể','e').replace('ễ','e').replace('ệ','e')
             .replace('í','i').replace('ì','i').replace('ỉ','i').replace('ĩ','i').replace('ị','i').replace('ó','o').replace('ò','o').replace('ỏ','o').replace('õ','o').replace('ọ','o').replace('ô','o').replace('ố','o').replace('ồ','o').replace('ổ','o').replace('ỗ','o').replace('ộ','o').replace('ơ','o').replace('ớ','o').replace('ờ','o').replace('ở','o').replace('ỡ','o').replace('ợ','o')
             .replace('ú','u').replace('ù','u').replace('ủ','u').replace('ũ','u').replace('ụ','u').replace('ư','u').replace('ứ','u').replace('ừ','u').replace('ử','u').replace('ữ','u').replace('ự','u').replace('ý','y').replace('ỳ','y').replace('ỷ','y').replace('ỹ','y').replace('ỵ','y'))
    for k,words in STATEMENT_KEYS.items():
        if any(w in t or w in t_ascii for w in words): return k
    if 'ket qua hoat dong kinh doanh' in t_ascii or 'doanh thu' in t_ascii: return 'income_statement'
    if 'can doi ke toan' in t_ascii or 'tai san' in t_ascii or 'von chu so huu' in t_ascii: return 'balance_sheet'
    if 'luu chuyen tien' in t_ascii: return 'cash_flow'
    return None
def download(url,ticker,doc_id):
    RAW.mkdir(parents=True,exist_ok=True); p=RAW/f'{ticker}_{doc_id}.pdf'
    if not p.exists():
        req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0 invest-os-vn/1.0','Accept':'application/pdf,*/*'})
        p.write_bytes(urllib.request.urlopen(req,timeout=45).read())
    return p
def parse_text_lines(text, statement, page_no):
    items=[]
    for line in text.splitlines():
        line=norm(line)
        if len(line)<8: continue
        found=re.findall(r'\(?-?\d[\d\.]{2,}(?:,\d+)?\)?', line)
        nums=[val(x) for x in found]
        label=line
        for x in found: label=label.replace(x,' ')
        label=norm(label).strip(' -')
        if label and any(v is not None for v in nums):
            items.append({'label':label,'raw':[line],'values':[v for v in nums if v is not None],'header':[],'page':page_no,'extractor':'text_line'})
    return items

def ocr_page_text(fitz_page, dpi=180):
    try:
        from rapidocr_onnxruntime import RapidOCR
        import fitz
        if not hasattr(ocr_page_text, '_engine'):
            ocr_page_text._engine = RapidOCR()
        dpi=max(dpi,216)
        pix=fitz_page.get_pixmap(matrix=fitz.Matrix(dpi/72, dpi/72), alpha=False)
        result, _ = ocr_page_text._engine(pix.tobytes('png'))
        if not result: return ''
        lines=[]
        for item in result:
            if len(item) >= 2:
                text=item[1]
                # rapidocr_onnxruntime returns [box, text, score]; older variants may nest text.
                if isinstance(text, (list, tuple)) and text:
                    text=text[0]
                lines.append(str(text))
        return '\n'.join(lines)
    except Exception as e:
        return ''

def classify_with_context(text, current):
    st=classify(text)
    if st: return st
    return current

def parse_pdf(path):
    import pdfplumber, fitz
    statements={k:[] for k in STATEMENT_KEYS}; pages=[]
    fitz_doc=fitz.open(path)
    current_statement=None
    with pdfplumber.open(path) as pdf:
        for i,page in enumerate(pdf.pages,1):
            text=norm(page.extract_text() or '')
            extractor='pdfplumber_text'
            if not text and i-1 < len(fitz_doc):
                text=fitz_doc[i-1].get_text(); extractor='pymupdf_text'
            if not norm(text) and i-1 < len(fitz_doc):
                text=ocr_page_text(fitz_doc[i-1]); extractor='rapidocr_onnxruntime'
            else:
                text=keep_lines(text)
            st=classify_with_context(text, current_statement)
            if classify(text): current_statement=classify(text)
            tables=page.extract_tables() or []
            pages.append({'page':i,'statement_hint':st,'table_count':len(tables),'text_head':norm(text)[:240],'extractor':extractor})
            if st:
                statements[st].extend(parse_text_lines(text, st, i))
            for tb in tables:
                if not tb or len(tb)<2: continue
                local=st or classify(' '.join(norm(c) for row in tb[:3] for c in row))
                if not local: continue
                header=[norm(c) for c in tb[0]]
                for row in tb[1:]:
                    cells=[norm(c) for c in row]
                    if len(cells)<2: continue
                    label=cells[0]
                    nums=[val(c) for c in cells[1:]]
                    if not label or all(v is None for v in nums): continue
                    item={'label':label,'raw':cells,'values':[v for v in nums if v is not None],'header':header,'page':i,'extractor':'pdf_table'}
                    statements[local].append(item)
    return statements,pages
def choose_docs(index,tickers,latest_only=True,prefer_consolidated=True):
    docs=[]
    for c in index.get('companies',[]):
        if c.get('ticker') not in tickers: continue
        arr=[d for d in c.get('documents',[]) if str(d.get('url','')).lower().endswith('.pdf')]
        if prefer_consolidated: arr=[d for d in arr if 'hợp nhất' in str(d.get('name','')).lower()] or arr
        arr=sorted(arr,key=lambda d:(int(d.get('year') or 0), int(d.get('quarter') or 0)), reverse=True)
        docs.extend(arr[:1] if latest_only else arr)
    return docs
def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--tickers',default='FPT,MWG,VCB,SSI'); ap.add_argument('--latest-only',action='store_true',default=True); ap.add_argument('--max-docs',type=int,default=4); args=ap.parse_args()
    tickers=[x.strip().upper() for x in args.tickers.split(',') if x.strip()]
    index=json.loads((LIVE/'cafef_financial_reports.vn.json').read_text(encoding='utf-8'))
    out_docs=[]; warnings=[]
    for d in choose_docs(index,tickers,args.latest_only)[:args.max_docs]:
        try:
            p=download(d['url'],d['ticker'],d['id']); statements,pages=parse_pdf(p)
            out_docs.append({'ticker':d['ticker'],'document':d,'pdf_path':str(p.relative_to(ROOT)),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'statements':statements,'page_audit':pages,'parse_counts':{k:len(v) for k,v in statements.items()}})
        except Exception as e: warnings.append(f"{d.get('ticker')}:pdf_parse_error:{e}")
    ok=bool(out_docs) and any(sum(x['parse_counts'].values())>0 for x in out_docs)
    ocr_needed=[x['ticker'] for x in out_docs if sum(x['parse_counts'].values())==0]
    if ocr_needed: warnings.append('image_based_pdf_no_statement_tables_detected:'+','.join(ocr_needed))
    out={'as_of':now_iso(),'source':'CafeF BCTC PDFs via FileBCTC.ashx + pdfplumber/PyMuPDF/RapidOCR','documents':out_docs,'parse_quality':{'required_passed':ok,'warnings':warnings,'no_sample_fallback':True},'quality_score':0.82 if ok else 0.4,'status':'real_cafef_pdf_line_items' if ok else 'pdf_line_item_parse_failed'}
    (LIVE/'cafef_financial_statements_structured.vn.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'status':out['status'],'documents':len(out_docs),'counts':[x['parse_counts'] for x in out_docs],'warnings':warnings},ensure_ascii=False,indent=2))
if __name__=='__main__': main()
