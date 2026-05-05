#!/usr/bin/env python
r"""
FData protobuf-ish decoder tool.
Goal: recover full metadata from Common/symbols.dat + symbolInfo.dat without .proto schema.
Outputs:
  data_live/fdata_symbols_full.json
  data_live/fdata_proto_fieldmap.json
  data_live/fdata_sector_candidates.json
"""
from __future__ import annotations
import argparse, json, re, struct
from pathlib import Path
from typing import Any, Dict, List, Tuple

ROOT=Path(__file__).resolve().parents[1]
DEFAULT=Path(r"C:\Users\DUC\Documents\FDATA\Common")
LIVE=ROOT/'data_live'


def save(p:Path,o:Any):
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(o,ensure_ascii=False,indent=2),encoding='utf8')

def read_varint(b:bytes,i:int)->Tuple[int,int]:
    shift=0; val=0
    while i<len(b):
        c=b[i]; i+=1; val|=(c&0x7f)<<shift
        if not (c&0x80): return val,i
        shift+=7
        if shift>70: break
    raise ValueError('bad varint')

def printable(bs:bytes)->str:
    s=bs.decode('utf-8','ignore').strip('\x00\r\n\t ')
    good=sum(1 for ch in s if ch.isprintable())
    return s if s and good/max(1,len(s))>0.75 else ''

def parse_msg(b:bytes, depth=0, max_depth=3)->List[Dict[str,Any]]:
    out=[]; i=0
    while i<len(b):
        start=i
        try: key,i=read_varint(b,i)
        except Exception: break
        field=key>>3; wire=key&7
        item={'field':field,'wire':wire,'offset':start}
        try:
            if wire==0:
                v,i=read_varint(b,i); item['varint']=v
            elif wire==1:
                raw=b[i:i+8]; i+=8; item['fixed64_hex']=raw.hex()
                if len(raw)==8: item['double']=struct.unpack('<d',raw)[0]
            elif wire==2:
                ln,i=read_varint(b,i); raw=b[i:i+ln]; i+=ln
                item['len']=ln; item['text']=printable(raw); item['hex_head']=raw[:32].hex()
                if depth<max_depth and ln>1:
                    sub=parse_msg(raw,depth+1,max_depth)
                    if sub: item['sub']=sub[:50]
            elif wire==5:
                raw=b[i:i+4]; i+=4; item['fixed32_hex']=raw.hex()
                if len(raw)==4: item['float']=struct.unpack('<f',raw)[0]
            else:
                break
        except Exception:
            break
        if field==0: break
        out.append(item)
    return out

def split_len_messages(b:bytes)->List[bytes]:
    msgs=[]; i=0
    while i<len(b):
        try: ln,j=read_varint(b,i)
        except Exception: break
        if ln<=0 or j+ln>len(b):
            i+=1; continue
        msg=b[j:j+ln]
        # accept if parse starts sane
        fields=parse_msg(msg,0,1)
        if fields:
            msgs.append(msg); i=j+ln
        else:
            i+=1
    return msgs

def scalar_texts(fields:List[Dict[str,Any]], prefix='')->List[Tuple[str,str]]:
    arr=[]
    for f in fields:
        path=f'{prefix}{f["field"]}'
        if f.get('text'): arr.append((path,f['text']))
        if 'sub' in f: arr += scalar_texts(f['sub'], path+'.')
    return arr

def decode_icbs(common:Path)->Dict[str,Dict[str,Any]]:
    p=common/'ICBs.dat'
    out={}
    if not p.exists(): return out
    b=p.read_bytes(); i=0
    while i < len(b)-8:
        if b[i] != 0x0a:
            i += 1; continue
        try:
            ln=b[i+1]; msg=b[i+2:i+2+ln]
            if len(msg) < 8 or msg[0] != 0x0a: i += 1; continue
            lc=msg[1]; code=msg[2:2+lc].decode('utf-8','ignore')
            j=2+lc
            if j>=len(msg) or msg[j] != 0x10: i += 1; continue
            order,j2=read_varint(msg,j+1)
            if j2>=len(msg) or msg[j2] != 0x1a: i += 1; continue
            lname=msg[j2+1]; name=msg[j2+2:j2+2+lname].decode('utf-8','ignore')
            if re.fullmatch(r'\d{4}',code) and name:
                level = 1 if code.endswith('000') else 2 if code.endswith('00') else 3 if code.endswith('0') else 4
                out[code]={'icb_code':code,'icb_name':name,'icb_order':order,'icb_level':level}
            i += 2+ln
        except Exception:
            i += 1
    return out

def icb_hierarchy(code:str, icbs:Dict[str,Dict[str,Any]])->Dict[str,Any]:
    if not code: return {}
    c4=code[:4]
    parents=[]
    for c in [c4[0]+'000', c4[:2]+'00', c4[:3]+'0', c4]:
        if c in icbs and c not in [x.get('icb_code') for x in parents]: parents.append(icbs[c])
    out={}
    for p in parents:
        lvl=p['icb_level']; out[f'icb_level_{lvl}_code']=p['icb_code']; out[f'icb_level_{lvl}_name']=p['icb_name']
    if c4 in icbs:
        out['industry_code']=c4; out['industry']=icbs[c4]['icb_name']
    return out

def load_symbols(common:Path)->Dict[str,Dict[str,Any]]:
    b=(common/'symbols.dat').read_bytes(); out={}; icbs=decode_icbs(common)
    # symbols.dat is concatenated records without outer length. Record body:
    # \n <len> ticker \x1a <len> name \" <len> exchange [* <len> code] 2/\x32 <len> type
    i=0
    while i < len(b)-6:
        if b[i] != 0x0a:
            i += 1; continue
        try:
            lt=b[i+1]; t0=i+2; ticker=b[t0:t0+lt].decode('utf-8')
            j=t0+lt
            if not re.fullmatch(r'[A-Z0-9]{2,12}', ticker) or b[j] != 0x1a:
                i += 1; continue
            ln=b[j+1]; n0=j+2; name=b[n0:n0+ln].decode('utf-8','ignore')
            k=n0+ln
            if b[k] != 0x22:
                i += 1; continue
            le=b[k+1]; e0=k+2; exch=b[e0:e0+le].decode('utf-8','ignore')
            k=e0+le; code=''
            if k < len(b) and b[k] == 0x2a:
                lc=b[k+1]; c0=k+2; code=b[c0:c0+lc].decode('utf-8','ignore'); k=c0+lc
            typ=''
            if k < len(b) and b[k] in (0x32,):
                lty=b[k+1]; ty0=k+2; typ=b[ty0:ty0+lty].decode('utf-8','ignore'); k=ty0+lty
            rec={'ticker':ticker,'name':name,'exchange':exch,'type':typ,'code':code,'raw_offset':i}
            rec.update(icb_hierarchy(code, icbs))
            out[ticker]=rec
            i=k
        except Exception:
            i += 1
    return out

def enrich_symbol_info(common:Path, syms:Dict[str,Dict[str,Any]])->Tuple[Dict[str,Any],Dict[str,Any]]:
    b=(common/'symbolInfo.dat').read_bytes(); msgs=split_len_messages(b)
    fieldmap={}; sector_candidates={}
    # message split works for many records; fallback regex around ticker too
    for m in msgs:
        fs=parse_msg(m,0,2); texts=scalar_texts(fs); vals=[v for _,v in texts]
        ticker=None
        for v in vals:
            if v in syms: ticker=v; break
        if not ticker: continue
        meta=syms[ticker]
        meta.setdefault('info_texts',[]).extend([v for _,v in texts if v not in meta.get('raw_texts',[])])
        for path,v in texts:
            fieldmap.setdefault(path,{}).setdefault(v,0); fieldmap[path][v]+=1
        # candidates: URL/name/country/currency/exchange/industry-like labels
        for v in vals:
            if 'fialda.com' in v: meta['url']=v
            elif v in ['Vietnam','VN','VND']: pass
            elif len(v)>3 and v not in [ticker,meta.get('name'),meta.get('exchange'),meta.get('type')]:
                sector_candidates.setdefault(ticker,[]).append(v)
    # regex fallback finds URL/name around ticker
    for t,meta in syms.items():
        tb=t.encode(); idx=b.find(b'co-phieu/'+tb+b'/tongquan')
        if idx>=0:
            chunk=b[max(0,idx-80):idx+240].decode('utf-8','ignore')
            meta['url']=f'https://fwt.fialda.com/co-phieu/{t}/tongquan'
            m=re.search(r'tongquan:(.{4,100}?)(?:B\x00|J\x07|Vietnam|R\x03)',chunk)
            if m: meta['company_name']=m.group(1).strip()
    # shrink fieldmap examples
    fmap={k:sorted(v.items(), key=lambda x:x[1], reverse=True)[:30] for k,v in fieldmap.items()}
    return syms, {'fieldmap':fmap,'sector_candidates':sector_candidates}

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--common',default=str(DEFAULT)); ap.add_argument('--sample',default='FPT,MWG,VCB,SSI')
    args=ap.parse_args(); common=Path(args.common)
    icbs=decode_icbs(common)
    syms=load_symbols(common); syms,extra=enrich_symbol_info(common,syms)
    save(LIVE/'fdata_icbs.json',icbs)
    save(LIVE/'fdata_symbols_full.json',syms)
    save(LIVE/'fdata_proto_fieldmap.json',extra['fieldmap'])
    save(LIVE/'fdata_sector_candidates.json',extra['sector_candidates'])
    print('icbs',len(icbs),'symbols',len(syms),'wrote data_live/fdata_symbols_full.json')
    for t in [x.strip().upper() for x in args.sample.split(',') if x.strip()]: print(t, syms.get(t))
if __name__=='__main__': main()
