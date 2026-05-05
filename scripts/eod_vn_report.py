#!/usr/bin/env python
r"""Generate real EOD Vietnam market report from FData pipeline outputs."""
from __future__ import annotations
import argparse,json
from datetime import datetime
from pathlib import Path
from typing import Any,Dict,List
ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT/'outputs'; LIVE=ROOT/'data_live'; TPL=ROOT/'reports'/'templates'/'eod_vn_report.md'

def load(p:Path)->Any: return json.loads(p.read_text(encoding='utf-8'))
def save(p:Path,x:Any): p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf-8')
def pct(x): return f"{x:.2f}%"
def md_table(h,rows):
 out=['| '+' | '.join(h)+' |','| '+' | '.join(['---']*len(h))+' |']
 for r in rows: out.append('| '+' | '.join(map(str,r))+' |')
 return '\n'.join(out)
def render(t:str,v:Dict[str,Any])->str:
 for k,x in v.items(): t=t.replace('{{'+k+'}}',str(x))
 return t

def index_context(breadth:Dict[str,Any], market_snapshot:Dict[str,Any]|None=None)->str:
 m=breadth.get('market',{}) or {}
 idx=m.get('indices',[]) or []
 if (not idx) and market_snapshot:
  idx=market_snapshot.get('indices',[]) or []
 rows=[]
 for x in idx:
  rows.append([x.get('symbol'),x.get('date') or x.get('as_of',''),x.get('close'),pct(x.get('change_pct',0)),x.get('volume_mn'),x.get('above_ma20_pct')])
 if not rows: return '- Chưa có dữ liệu chỉ số VNINDEX/VN30. Cần chạy `python scripts/fdata_adapter.py --market --timeframe EOD` hoặc `python scripts/fdata_adapter.py --all --fallback-intraday`.'
 vn=next((x for x in idx if x.get('symbol')=='VNINDEX'),idx[0])
 vn30=next((x for x in idx if x.get('symbol')=='VN30'),None)
 tone='tích cực' if vn.get('change_pct',0)>0.3 else 'tiêu cực' if vn.get('change_pct',0)<-0.3 else 'trung tính/nhiễu'
 lead=f"VNINDEX trạng thái {tone} theo biến động phiên {pct(vn.get('change_pct',0))}."
 if vn30: lead+=f" VN30 biến động {pct(vn30.get('change_pct',0))}."
 return lead+"\n\n"+md_table(['Chỉ số','Ngày','Close','%','Volume mn','Above MA20'],rows)

def breadth_context(breadth:Dict[str,Any], quality:Dict[str,Any])->str:
 br=breadth.get('breadth',{})
 rows=[['Universe HOSE',breadth.get('universe_size')],['Advancers',br.get('advancers')],['Decliners',br.get('decliners')],['Unchanged',br.get('unchanged')],['A/D',br.get('adv_dec_ratio')],['Above MA20',br.get('above_ma20')],['Below MA20',br.get('below_ma20')],['Above MA20 %',pct(br.get('above_ma20_pct',0))],['Zero volume',br.get('zero_volume')],['Low volume <50k',br.get('low_volume_lt_50000')],['Coverage',str(quality.get('coverage_pct'))+'%']]
 return md_table(['Metric','Value'],rows)

def sector_leadership(lead:Dict[str,Any])->str:
 rows=[]
 for i,r in enumerate(lead.get('sector_leadership',[])[:10],1):
  rows.append([i,r['sector'],r['count'],r['leadership_score'],pct(r['avg_change_pct']),r['avg_rs20'],r['adv_dec_ratio'],pct(r['above_ma20_pct'])])
 return md_table(['Rank','Sector','Count','Score','Avg %','RS20','A/D','Above MA20 %'],rows)

def stock_leadership(lead:Dict[str,Any])->str:
 rows=[]
 for i,s in enumerate(lead.get('stock_leadership',[])[:15],1): rows.append([i,s['ticker'],s.get('industry',''),s['leadership_score'],pct(s['change_pct']),s['rs_20d'],s['vol_ratio_20d'],s['volume']])
 return md_table(['Rank','Ticker','Industry','Score','%','RS20','VolRatio','Volume'],rows)

def trade_signals(sig:Dict[str,Any])->str:
 signals=sig.get('signals',[])
 actionable=[s for s in signals if s.get('status')=='actionable'][:15]
 watch=[s for s in signals if s.get('status')=='watch'][:15]
 rows=[]
 for s in actionable+watch: rows.append([s['ticker'],s['status'],s['score'],s['entry_zone'],s['invalidation'],s['confidence']])
 if not rows: return '- Không có actionable/watch signal trong investable universe theo rule hiện tại.'
 return md_table(['Ticker','Status','Score','Entry zone','Invalidation','Confidence'],rows)

def holding_window_calibration()->str:
 p=OUT/'t5_t10_comparison.md'; ts=OUT/'trailing_stop_full_replay.json'
 base='- Tier A: horizon chính `T+10` max. Stop rule OOS: `trailing_low3_after_T3` — sau T+3 trailing stop theo low 3 phiên gần nhất; nếu bị đá ra sớm không vào lại nếu chưa có signal mới.\n- Không dùng fixed T+10 thuần vì OOS âm và MAE sâu hơn.\n- Tier B: `T+5 / confirm only`, conditional/short watch, không gọi là mua mạnh.'
 if p.exists():
  txt=p.read_text(encoding='utf-8'); base+='\n\n'+(txt.split('## Kết luận')[-1].strip() if '## Kết luận' in txt else txt[:1200])
 if ts.exists():
  d=load(ts); base+=f"\n\nTrailing full replay selected: `{d.get('selected_rule')}`."
 return base

def market_regime_block()->str:
 p=OUT/'trade_candidates_final.json'
 if not p.exists(): return '- Chưa có quality gate.'
 d=load(p); r=d.get('market_regime',{}); reg=r.get('regime')
 if reg!='risk_on':
  return f"**NO NEW BUY**\n\n- Lý do: VNINDEX chưa đạt `close > MA20 > MA50` + MA20 slope 10 phiên dương hoặc breadth yếu.\n- Regime hiện tại: `{reg}`.\n- Hành động: chỉ quản trị danh mục, giữ mã mạnh hơn thị trường, giảm mã gãy stop/yếu hơn VNINDEX."
 return f"**BUY ALLOWED BY REGIME**\n\n- Regime: `{reg}`.\n- Chỉ mua theo entry condition + risk budget."

def portfolio_section()->str:
 p=OUT/'portfolio_actions.json'
 if not p.exists(): return '- Chưa chạy `portfolio_layer.py`.'
 d=load(p); rows=[]
 for x in d.get('positions',[]): rows.append([x['ticker'],x['weight_pct'],x['in_top10'],x['in_watch'],x['action']])
 buys=[[x['ticker'],x['action'],round(x['suggested_weight_pct'],2),x['entry_zone']] for x in d.get('new_buy_watch',[])[:10]]
 out='### Holdings\n'+(md_table(['Ticker','Weight %','Top10','Watch','Action'],rows) if rows else '- Không có holdings')
 out+='\n\n### New buy watch\n'+(md_table(['Ticker','Action','Suggested weight %','Entry'],buys) if buys else '- Không có mã chờ mua mới')
 return out

def final_trade_sections()->tuple[str,str,str,str]:
 p=OUT/'trade_candidates_final.json'
 if not p.exists(): return ('- Chưa chạy `signal_quality_gate.py`.','- Chưa có watchlist.','- Chưa có danh sách loại.','- Chưa có dữ liệu quality gate.')
 d=load(p); passed=d.get('passed',[]); watch=d.get('watchlist',[]); rej=d.get('rejected',[])
 cand=md_table(['Rank','Ticker','Setup','Score','Entry','Stop','T1','T2','R/R','Sizing'],[[i+1,x['ticker'],x['setup'],x.get('candidate_score',''),x['entry_zone'],x['stop_loss'],x['target_1'],x['target_2'],x['rr_ratio'],x['position_sizing_suggestion']] for i,x in enumerate(passed)]) if passed else '- Không có mã qua full quality gate.'
 wl=md_table(['Ticker','Setup','R/R','Lý do chưa qua'],[[x['ticker'],x['setup'],x['rr_ratio'],'; '.join(x.get('reject_reasons',[]))] for x in watch[:20]]) if watch else '- Không có watchlist.'
 rj=md_table(['Ticker','Setup','R/R','Lý do loại'],[[x['ticker'],x['setup'],x.get('rr_ratio'),' ; '.join(x.get('reject_reasons',[]))] for x in rej[:30]]) if rej else '- Không có mã bị loại.'
 risks=[]
 if not passed: risks.append('Không có setup qua quality gate: không nên ép giải ngân.')
 if len(watch)>len(passed)*3: risks.append('Watchlist nhiều hơn passed quá lớn: thị trường còn nhiễu, ưu tiên chờ xác nhận.')
 risks.append('Không giải ngân vào mã bị loại vì volume thấp, sector yếu, close dưới MA20, R/R kém hoặc stop quá rộng.')
 return cand,wl,rj,'\n'.join('- '+x for x in risks)

def risk_warnings(quality:Dict[str,Any], breadth:Dict[str,Any], sig:Dict[str,Any])->str:
 br=breadth.get('breadth',{}); warnings=[]
 if quality.get('coverage_pct',0)<99: warnings.append(f"Coverage HOSE chỉ {quality.get('coverage_pct')}%, cần kiểm tra missing DAT.")
 if quality.get('zero_volume_count',0)>0: warnings.append(f"Có {quality.get('zero_volume_count')} mã HOSE zero-volume; không dùng nhóm này cho signal giao dịch.")
 if quality.get('low_volume_lt_50000_count',0)>0: warnings.append(f"Có {quality.get('low_volume_lt_50000_count')} mã thanh khoản dưới 50k cổ phiếu; signal giao dịch ưu tiên investable universe.")
 if br.get('adv_dec_ratio',1)<1: warnings.append('Breadth A/D dưới 1: độ rộng nghiêng tiêu cực.')
 if br.get('above_ma20_pct',50)<45: warnings.append('Tỷ lệ trên MA20 dưới 45%: cấu trúc ngắn hạn chưa khỏe.')
 if sig.get('universe_mode')!='investable': warnings.append('Signal input không phải investable — kiểm tra lại command.')
 return '\n'.join('- '+w for w in warnings) if warnings else '- Chưa có cảnh báo lớn theo rule hiện tại.'

def main():
 ap=argparse.ArgumentParser(); args=ap.parse_args()
 quality=load(OUT/'fdata_hose_quality_report.json'); breadth=load(OUT/'fdata_hose_breadth.json'); lead=load(OUT/'hose_leadership.json'); sig=load(OUT/'stock_signal_scan_investable.json')
 market_snapshot=load(LIVE/'market_snapshot.vn.json') if (LIVE/'market_snapshot.vn.json').exists() else None
 final_candidates, next_watchlist, rejected_signals, no_disbursement_risks = final_trade_sections(); portfolio_actions=portfolio_section(); regime_block=market_regime_block(); holding_cal=holding_window_calibration()
 as_of=datetime.now().astimezone().isoformat(timespec='seconds')
 result={'as_of':as_of,'date':as_of[:10],'universe_rules':{'market_breadth_leadership':'hose_all','trade_signal':'investable','portfolio_action':'investable + holdings','mixing':'forbidden'},'inputs':['fdata_hose_quality_report.json','fdata_hose_breadth.json','hose_leadership.json','stock_signal_scan_investable.json'],'index_context':index_context(breadth,market_snapshot),'breadth_context':breadth_context(breadth,quality),'sector_leadership_top10':lead.get('sector_leadership',[])[:10],'stock_leadership_top15':lead.get('stock_leadership',[])[:15],'trade_signals':sig.get('signals',[]),'final_trade_candidates':final_candidates,'next_watchlist':next_watchlist,'rejected_signals':rejected_signals,'no_disbursement_risks':no_disbursement_risks,'portfolio_actions':portfolio_actions,'market_regime_block':regime_block,'holding_window_calibration':holding_cal,'risk_warnings_text':risk_warnings(quality,breadth,sig),'disclaimer':'Thông tin hỗ trợ quyết định, không phải khuyến nghị đầu tư cá nhân hóa bắt buộc mua/bán.'}
 save(OUT/'eod_vn_report.json',result)
 tpl=TPL.read_text(encoding='utf-8')
 md=render(tpl,{'date':result['date'],'index_context':result['index_context'],'market_regime_block':regime_block,'holding_window_calibration':holding_cal,'breadth_context':result['breadth_context'],'sector_leadership':sector_leadership(lead),'stock_leadership':stock_leadership(lead),'trade_signals':trade_signals(sig),'final_trade_candidates':final_candidates,'next_watchlist':next_watchlist,'rejected_signals':rejected_signals,'no_disbursement_risks':no_disbursement_risks,'portfolio_actions':portfolio_actions,'risk_warnings':result['risk_warnings_text'],'sources':', '.join(result['inputs']),'disclaimer':result['disclaimer']})
 (OUT/'eod_vn_report.md').write_text(md,encoding='utf-8')
 print('OK EOD VN report'); print(OUT/'eod_vn_report.json'); print(OUT/'eod_vn_report.md')
if __name__=='__main__': main()
