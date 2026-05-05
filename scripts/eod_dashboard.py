#!/usr/bin/env python
from __future__ import annotations
import json,html
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT/'outputs'
def table(rows,cols,cls=''):
 s=f'<table class="{cls}"><tr>'+''.join(f'<th>{c}</th>' for c in cols)+'</tr>'
 for r in rows: s+='<tr>'+''.join(f'<td>{html.escape(str(r.get(c,"")))}</td>' for c in cols)+'</tr>'
 return s+'</table>'
def main():
 gate=json.loads((OUT/'trade_candidates_final.json').read_text(encoding='utf-8'))
 pf=json.loads((OUT/'portfolio_action_report.json').read_text(encoding='utf-8')) if (OUT/'portfolio_action_report.json').exists() else {}
 bt=json.loads((OUT/'historical_backtest.json').read_text(encoding='utf-8')) if (OUT/'historical_backtest.json').exists() else {}
 css='body{font-family:Arial;margin:24px;background:#f7f8fa;color:#111}.card{background:white;border-radius:12px;padding:16px;margin:14px 0;box-shadow:0 1px 6px #ddd}table{border-collapse:collapse;width:100%;font-size:13px}th,td{border-bottom:1px solid #eee;padding:6px;text-align:left}.A{border-left:6px solid #0a7}.B{border-left:6px solid #d90}.R{border-left:6px solid #c33}.pill{display:inline-block;padding:4px 8px;border-radius:99px;background:#eee}'
 html_doc=f'<html><head><meta charset="utf-8"><style>{css}</style></head><body><h1>DUC AI Investment OS — EOD Dashboard</h1>'
 reg=gate.get('market_regime',{}).get('regime')
 no_buy = reg!='risk_on'
 html_doc+=f"<div class='card'><b>Market regime</b>: <span class='pill'>{reg}</span> — {gate.get('regime_rule',{}).get('reason')}<h2>{'NO NEW BUY' if no_buy else 'BUY ALLOWED BY REGIME'}</h2><p>{'Chỉ quản trị danh mục: giữ mã mạnh hơn thị trường, giảm mã gãy stop/yếu hơn VNINDEX.' if no_buy else 'Chỉ mua theo entry condition và risk budget.'}</p></div>"
 html_doc+="<div class='card A'><h2>Tier A</h2>"+table(gate.get('tier_a',[]),['ticker','action_type','candidate_score','rr_ratio','entry_condition'])+'</div>'
 html_doc+="<div class='card B'><h2>Tier B</h2>"+table(gate.get('tier_b',[])[:20],['ticker','action_type','candidate_score','rr_ratio','entry_condition'])+'</div>'
 html_doc+="<div class='card'><h2>Portfolio</h2>"+table(pf.get('holdings',[]),['ticker','sector','weight_pct','bucket','action','target_weight_pct'])+'</div>'
 html_doc+="<div class='card'><h2>Backtest summary</h2><pre>"+html.escape(json.dumps(bt.get('summary',{}),ensure_ascii=False,indent=2))+'</pre></div>'
 html_doc+='</body></html>'
 (OUT/'eod_vn_report.html').write_text(html_doc,encoding='utf-8')
 digest=f"VN EOD\nRegime: {reg}\n{'NO NEW BUY - chỉ quản trị danh mục' if no_buy else 'BUY ALLOWED - theo entry condition'}\nTier A: {', '.join(x['ticker'] for x in gate.get('tier_a',[])[:8]) or 'None'}\nTier B: {', '.join(x['ticker'] for x in gate.get('tier_b',[])[:8]) or 'None'}\nPortfolio risks: {'; '.join(pf.get('concentration_risks',[])[:3]) or 'None'}\nBacktest T+20 TierA: {bt.get('summary',{}).get('Tier A',{}).get('T+20',{})}\nKhông mua đuổi."
 (OUT/'telegram_digest.txt').write_text(digest,encoding='utf-8')
 print('OK dashboard')
if __name__=='__main__': main()
