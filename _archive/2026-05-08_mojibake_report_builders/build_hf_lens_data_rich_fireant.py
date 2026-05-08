from __future__ import annotations
import json, html, subprocess
from datetime import datetime
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'outputs'; LIVE=ROOT/'data_live'
DEST=Path(r'C:\Users\DUC\Desktop\InvestOS_VN_PDF_Reports')

def load(p):
    return json.loads(Path(p).read_text(encoding='utf-8')) if Path(p).exists() else {}
def esc(x): return html.escape(str(x if x is not None else ''))
def pct(x):
    try:
        v=float(x); return f'{v:.2f}%'
    except Exception: return 'N/A'
def bil(x):
    try: return f'{float(x)/1_000_000_000:,.1f} tỷ'
    except Exception: return 'N/A'
def table(headers, rows):
    s='<table><tr>'+''.join(f'<th>{esc(h)}</th>' for h in headers)+'</tr>'
    for r in rows: s+='<tr>'+''.join(f'<td>{esc(c)}</td>' for c in r)+'</tr>'
    return s+'</table>'
def top(rows,key,n=10,rev=True):
    return sorted([r for r in rows if r.get(key) is not None], key=lambda r:r.get(key) or 0, reverse=rev)[:n]

def main():
    fire=load(LIVE/'fireant_foreign_flow.vn.json')
    eod=load(OUT/'eod_vn_report.json')
    sig=load(OUT/'stock_signal_scan_investable.json')
    gate=load(OUT/'trade_candidates_final.json')
    pf=load(OUT/'portfolio_action_report.json')
    breadth=load(OUT/'fdata_hose_breadth.json')
    qual=load(OUT/'fdata_hose_quality_report.json')
    hist=load(OUT/'historical_backtest.json')
    deriv=load(LIVE/'derivatives_live.vn.json')
    now=datetime.now().astimezone(); date=now.strftime('%Y-%m-%d')
    industries=fire.get('industry_flows',[]); level4=[r for r in industries if r.get('level')==4]
    stats=fire.get('ticker_trading_statistics',[]); fins=fire.get('financial_ratios',[])
    stat_by={r.get('symbol'):r for r in stats if r.get('symbol')}
    fin_by={r.get('symbol'):r for r in fins if r.get('symbol')}
    enriched=[]
    for sym,r in stat_by.items():
        z={'symbol':sym,**r}; z.update({('fin_'+k):v for k,v in fin_by.get(sym,{}).items() if k not in ('symbol','row_index','symbol_mapping_source')}); enriched.append(z)
    indices=(breadth.get('market') or {}).get('indices') or []
    br=breadth.get('breadth',{})
    signals=sig.get('signals',[])
    action=[s for s in signals if s.get('status')=='actionable'][:10]
    watch=[s for s in signals if s.get('status')=='watch'][:12]
    sector_rows=[]
    for r in top(level4,'value_vnd',12):
        chg=None
        if r.get('index_close') is not None and r.get('index_prev'): chg=(r['index_close']/r['index_prev']-1)*100
        sector_rows.append([r.get('industry_name'), pct(chg), bil(r.get('value_vnd')), bil(r.get('foreign_net_value_vnd')), bil(r.get('positive_money_flow_vnd')), bil(r.get('negative_money_flow_vnd')), r.get('pe'), r.get('pb')])
    foreign_buy=[[r.get('industry_name'),bil(r.get('foreign_net_value_vnd')),bil(r.get('foreign_buy_value_vnd')),bil(r.get('foreign_sell_value_vnd'))] for r in top(level4,'foreign_net_value_vnd',8,True)]
    foreign_sell=[[r.get('industry_name'),bil(r.get('foreign_net_value_vnd')),bil(r.get('foreign_buy_value_vnd')),bil(r.get('foreign_sell_value_vnd'))] for r in top(level4,'foreign_net_value_vnd',8,False)]
    mom=[[r.get('symbol'),pct((r.get('price_change_1w') or 0)*100),pct((r.get('price_change_1m') or 0)*100),pct((r.get('price_change_3m') or 0)*100),r.get('mfi_14d'),r.get('beta'),r.get('avg_volume_20d')] for r in top(enriched,'price_change_1m',15,True)]
    quality=[[r.get('symbol'),r.get('fin_eps'),pct((r.get('fin_roe') or 0)*100),pct((r.get('fin_roa') or 0)*100),pct((r.get('fin_profit_growth_ttm') or 0)*100),r.get('fin_debt_over_equity'),pct((r.get('fin_dividend_yield') or 0)*100)] for r in top([x for x in enriched if x.get('fin_roe') is not None],'fin_roe',15,True)]
    sig_rows=[[s.get('ticker'),s.get('status'),s.get('score'),s.get('entry_zone'),s.get('invalidation'),s.get('confidence')] for s in action+watch]
    idx_rows=[[x.get('symbol'),x.get('date') or x.get('as_of'),x.get('close'),pct(x.get('change_pct')),x.get('volume_mn'),x.get('above_ma20_pct')] for x in indices]
    deriv_rows=[]
    for r in (deriv.get('rows') or [])[:16]:
        deriv_rows.append([r.get('date'),r.get('symbol'),r.get('vndirect_code'),r.get('future_close'),r.get('vn30_close'),round(r.get('basis'),2) if r.get('basis') is not None else None,pct(r.get('basis_pct')),r.get('fireant_volume'),bil(r.get('fireant_value')),r.get('open_interest'),r.get('oi_change'),r.get('foreign_net_qty'),bil(r.get('foreign_net_value')),bil(r.get('prop_net_value'))])
    css="""@page{size:A4;margin:12mm 10mm}body{font-family:Arial,'Segoe UI',sans-serif;font-size:10.2px;line-height:1.42;color:#111}h1{font-size:21px;margin:0 0 6px}h2{font-size:15px;margin-top:17px;border-bottom:1px solid #ddd;padding-bottom:4px}h3{font-size:12.2px;margin:10px 0 4px}.meta{color:#555}.card{background:#f7f9fb;border:1px solid #e2e6ea;border-radius:8px;padding:10px 12px;margin:10px 0}.lens{page-break-inside:avoid;border:1px solid #ddd;border-radius:8px;padding:9px;margin:8px 0}.tag{display:inline-block;background:#eef3ff;border:1px solid #ccd8ff;border-radius:10px;padding:1px 6px;margin-right:4px;font-size:9px}table{border-collapse:collapse;width:100%;font-size:8.8px;margin:6px 0}td,th{border:1px solid #ddd;padding:4px;text-align:left;vertical-align:top}th{background:#f1f3f5}ul{margin:4px 0 8px 18px;padding:0}li{margin:3px 0}.warn{color:#9a5b00}.good{color:#0b6b3a}.bad{color:#8a1f11}.pagebreak{page-break-before:always}"""
    html_doc=f"<html><head><meta charset='utf-8'><style>{css}</style></head><body>"
    html_doc+=f"<h1>InvestOS VN - Báo cáo hành động HF lens data-rich + FireAnt</h1><div class='meta'>Ngày dữ liệu {date} | cophieu68 baseline + FireAnt public dashboard + CafeF/SBV/WebGia/vnstock | tạo lúc {now.isoformat(timespec='seconds')}</div>"
    html_doc+=f"<div class='card'><b>Kết luận CIO:</b> dữ liệu FireAnt đã bổ sung sector flow, foreign flow, GetTradingStatistics và financial ratios. Market breadth HOSE: {br.get('advancers')} tăng / {br.get('decliners')} giảm, A/D {br.get('adv_dec_ratio')}, above MA20 {br.get('above_ma20_pct')}%. Coverage {qual.get('coverage_pct')}%. Action: ưu tiên quản trị rủi ro + chọn lọc setup; không mua lan rộng nếu quality gate chưa cho passed list đủ mạnh.</div>"
    html_doc+='<h2>1. Dashboard chỉ số / breadth / signal</h2>'+table(['Chỉ số','Ngày','Close','%','Volume mn','Above MA20'],idx_rows)
    html_doc+=table(['Metric','Value'],[['HOSE parsed bars',qual.get('parsed_bars')],['Coverage %',qual.get('coverage_pct')],['Advancers',br.get('advancers')],['Decliners',br.get('decliners')],['A/D',br.get('adv_dec_ratio')],['Above MA20 %',br.get('above_ma20_pct')],['Investable signals',len(signals)],['Actionable',len([s for s in signals if s.get('status')=='actionable'])],['Watch',len([s for s in signals if s.get('status')=='watch'])]])
    html_doc+='<h2>2. FireAnt sector flow - data mới</h2>'+table(['Ngành','%','GTGD','NN ròng','Money +','Money -','P/E','P/B'],sector_rows)
    html_doc+='<h2>3. Foreign flow theo ngành</h2><h3>Top NN mua ròng</h3>'+table(['Ngành','NN ròng','NN mua','NN bán'],foreign_buy)+'<h3>Top NN bán ròng</h3>'+table(['Ngành','NN ròng','NN mua','NN bán'],foreign_sell)
    html_doc+='<h2>4. FireAnt GetTradingStatistics mapped symbol ↔ stats</h2>'+table(['Ticker','1W','1M','3M','MFI14','Beta','AvgVol20D'],mom)
    html_doc+='<h2>5. FireAnt financial ratios mapped symbol ↔ ratios</h2>'+table(['Ticker','EPS','ROE','ROA','Profit growth TTM','D/E','Dividend yield'],quality)
    html_doc+='<h2>6. VN30 derivatives / basis / OI</h2><div class="card">Nguồn chính: FireAnt cho OHLCV/value/basis. VNDIRECT bổ sung mapping + openInterest. Long/short không có endpoint public sạch; dùng proxy foreign_net, prop_net_value, oi_change và ghi caveat.</div>'+table(['Ngày','Symbol','VND code','F close','VN30 close','Basis','Basis %','Vol','Value','OI','OI Δ','Foreign net qty','Foreign net value','Prop net value'],deriv_rows)
    html_doc+='<h2>7. Signal hành động</h2>'+table(['Ticker','Status','Score','Entry','Invalidation','Confidence'],sig_rows)
    html_doc+='<h2>8. Hedge-fund native lens</h2>'
    lens=[
      ('Market Strategist','Bluechip/breadth lens','Dùng breadth HOSE và index context để tránh nhầm kéo chỉ số thành broad risk-on. Nếu A/D và above-MA20 không mở rộng, chỉ giải ngân chọn lọc.'),
      ('Macro/Rates Strategist','Rates hurdle','Deposit curve vẫn là hurdle cho beta cao; equity cần earnings/flow xác nhận thay vì chỉ nhìn giá.'),
      ('Sector Flow Analyst','FireAnt sector flow','Ưu tiên ngành có GTGD lớn, money flow dương và foreign net không xấu. Ngành bị NN bán ròng mạnh cần discount conviction.'),
      ('Foreign Flow Analyst','NN mua/bán ròng','FireAnt bổ sung foreign buy/sell theo ngành; đây là biến thiếu trong bản 2026-05-07.'),
      ('Quant Researcher','GetTradingStatistics','Momentum 1W/1M/3M, MFI14, beta, avg volume giúp rank ticker ngoài signal price-volume cũ.'),
      ('Fundamental Analyst','Financial ratios','EPS/ROE/ROA/growth/debt/dividend yield từ FireAnt giúp lọc quality/value trước khi vào setup kỹ thuật.'),
      ('Technical Analyst','Entry discipline','Chỉ dùng actionable/watch; không mua đuổi ngoài entry zone; invalidation phải có trước lệnh.'),
      ('Risk Manager','Portfolio constraint','Nếu portfolio concentration/cash xấu, giảm rủi ro hiện hữu quan trọng hơn thêm mã mới.'),
      ('Portfolio Advisor','Action plan','Passed list + watchlist là nguồn hành động; rejected list không ép mua vì muốn có trade.'),
      ('Derivatives Strategist','VN30F basis/OI proxy','FireAnt làm nguồn chính futures OHLCV/value và basis; VNDIRECT bổ sung contract mapping + OI. Long/short chỉ là proxy từ foreign_net, prop_net_value, oi_change; không coi là vị thế thật.'),
      ('Data Designer','Audit mapping','Không fake symbol: rows FireAnt giữ row_index và symbol_mapping_source=GetSymbols_order để audit.')]
    for name,tag,body in lens:
        html_doc+=f"<div class='lens'><h3>{esc(name)}</h3><span class='tag'>{esc(tag)}</span><ul><li>{esc(body)}</li></ul></div>"
    html_doc+='<h2>8. Backtest / rule note</h2><div class="card">Trailing stop/backtest files đã chạy hôm nay. Dùng output historical_backtest, trailing_stop_full_replay, rolling_stop_rule_backtest để kiểm tra holding window; không suy luận performance nếu sample hoặc OOS không đủ.</div>'
    html_doc+='<h2>9. Kết luận hành động phiên kế tiếp</h2><ul><li>Base case: chọn lọc, không risk-on đại trà.</li><li>Buy trigger: signal actionable/watch + ngành có flow tốt + không bị foreign sell áp đảo.</li><li>Risk-off trigger: VNINDEX mất MA5/MA20, breadth co lại, foreign net sell mạnh ở ngành nắm giữ.</li><li>Position sizing: size theo ATR/invalidation; ưu tiên khôi phục cash buffer nếu portfolio đang căng.</li></ul>'
    html_doc+='</body></html>'
    out_html=OUT/f'invest-os-vn-bao-cao-hanh-dong-HF-lens-data-rich-{date}.html'
    out_pdf=DEST/f'invest-os-vn-bao-cao-hanh-dong-HF-lens-data-rich-{date}.pdf'
    DEST.mkdir(parents=True,exist_ok=True); out_html.write_text(html_doc,encoding='utf-8')
    chrome=Path(r'C:\Program Files\Google\Chrome\Application\chrome.exe')
    if not chrome.exists(): raise SystemExit('Chrome not found')
    subprocess.run([str(chrome),'--headless','--disable-gpu','--no-sandbox',f'--print-to-pdf={out_pdf}',out_html.resolve().as_uri()],check=True)
    print(out_pdf)
if __name__=='__main__': main()
