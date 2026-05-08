from __future__ import annotations
import json, html, subprocess
from datetime import datetime
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'outputs'; LIVE=ROOT/'data_live'
DEST=Path(r'C:\Users\DUC\Desktop\InvestOS_VN_PDF_Reports')

def load(p):
    p=Path(p); return json.loads(p.read_text(encoding='utf-8')) if p.exists() else {}
def esc(x): return html.escape(str('' if x is None else x))
def pct(x):
    try: return f'{float(x):.2f}%'
    except Exception: return 'N/A'
def bil(x):
    try: return f'{float(x)/1_000_000_000:,.1f} tỷ'
    except Exception: return 'N/A'
def num(x,d=2):
    try: return f'{float(x):,.{d}f}'
    except Exception: return 'N/A'
def table(headers, rows):
    s='<table><tr>'+''.join(f'<th>{esc(h)}</th>' for h in headers)+'</tr>'
    for r in rows: s+='<tr>'+''.join(f'<td>{c if isinstance(c,str) and c.startswith("<") else esc(c)}</td>' for c in r)+'</tr>'
    return s+'</table>'
def top(rows,key,n=10,rev=True):
    return sorted([r for r in rows if r.get(key) is not None], key=lambda r:r.get(key) or 0, reverse=rev)[:n]

def main():
    now=datetime.now().astimezone(); date=now.strftime('%Y-%m-%d')
    eod=load(OUT/'eod_vn_report.json'); sig=load(OUT/'stock_signal_scan_investable.json')
    pf=load(OUT/'portfolio_action_report.json'); breadth=load(OUT/'fdata_hose_breadth.json')
    qual=load(OUT/'fdata_hose_quality_report.json'); fire=load(LIVE/'fireant_foreign_flow.vn.json')
    deriv=load(LIVE/'derivatives_live.vn.json')
    macro=load(LIVE/'macro_rates_live.json') or load(OUT/'macro_rates_live.json')
    br=breadth.get('breadth',{}) if isinstance(breadth,dict) else {}
    indices=(breadth.get('market') or {}).get('indices') or []
    idx={x.get('symbol'):x for x in indices}
    vn=idx.get('VNINDEX',{}); vn30=idx.get('VN30',{}); hnx=idx.get('HNXINDEX',{}); up=idx.get('UPCOM',{})
    signals=sig.get('signals',[]) if isinstance(sig,dict) else []
    watch=[s for s in signals if s.get('status')=='watch'][:8]
    ideas=[s for s in signals if s.get('status') in ('idea','actionable')][:12]
    industries=fire.get('industry_flows',[]) if isinstance(fire,dict) else []
    level4=[r for r in industries if r.get('level')==4]
    sector_rows=[]
    for r in top(level4,'value_vnd',10):
        chg=(r.get('index_close')/r.get('index_prev')-1)*100 if r.get('index_close') and r.get('index_prev') else None
        sector_rows.append([r.get('industry_name'),pct(chg),bil(r.get('value_vnd')),bil(r.get('foreign_net_value_vnd')),bil(r.get('positive_money_flow_vnd')),bil(r.get('negative_money_flow_vnd')),r.get('pe'),r.get('pb')])
    deriv_rows=[]
    for r in (deriv.get('rows') or [])[:12]:
        deriv_rows.append([r.get('date'),r.get('symbol'),r.get('vndirect_code'),num(r.get('future_close')),num(r.get('vn30_close')),num(r.get('basis')),pct(r.get('basis_pct')),num(r.get('fireant_volume'),0),bil(r.get('fireant_value')),num(r.get('open_interest'),0),num(r.get('oi_change'),0),num(r.get('foreign_net_qty'),0),bil(r.get('foreign_net_value')),bil(r.get('prop_net_value'))])
    sig_rows=[]
    for s in (watch+ideas)[:16]:
        ev=s.get('evidence') or s.get('risk_evidence') or ''
        sig_rows.append([s.get('ticker'),s.get('status'),s.get('score'),s.get('entry_zone'),s.get('invalidation'),ev])
    pf_rows=[]
    if pf:
        pf_rows=[['NAV',pf.get('nav') or pf.get('NAV')],['Cash %',pf.get('cash_pct')],['Total PnL %',pf.get('total_pnl_pct')],['Risks','; '.join(pf.get('risks',[]) or [])]]
    css='''@page{size:A4;margin:12mm 10mm}body{font-family:Arial,"Segoe UI",sans-serif;font-size:10.3px;line-height:1.42;color:#111}h1{font-size:22px;margin:0 0 6px}h2{font-size:15.5px;margin-top:18px;border-bottom:1px solid #ddd;padding-bottom:4px}h3{font-size:12.5px;margin:12px 0 4px}.meta{color:#555}.card{background:#f7f9fb;border:1px solid #e2e6ea;border-radius:8px;padding:10px 12px;margin:10px 0}.lens{page-break-inside:avoid;border:1px solid #ddd;border-radius:8px;padding:10px;margin:9px 0}.tag{display:inline-block;background:#eef3ff;border:1px solid #ccd8ff;border-radius:10px;padding:1px 6px;margin-right:4px;font-size:9px}ul{margin:4px 0 8px 18px;padding:0}li{margin:3px 0}table{border-collapse:collapse;width:100%;font-size:9.2px;margin:6px 0}td,th{border:1px solid #ddd;padding:5px;text-align:left;vertical-align:top}th{background:#f1f3f5}.pagebreak{page-break-before:always}.note{color:#555;font-size:9.5px}'''
    html_doc=f"<html><head><meta charset='utf-8'><style>{css}</style></head><body>"
    html_doc+=f"<h1>InvestOS VN — Báo cáo thị trường & hành động, Native Lens giàu dữ liệu</h1><div class='meta'>Ngày dữ liệu {date} | PDF tiếng Việt | cophieu68 baseline + FireAnt primary OHLCV/value/basis + VNDIRECT mapping/OI + vnstock/CafeF/SBV/WebGia bổ sung | Tạo lúc {now.isoformat(timespec='seconds')}</div>"
    html_doc+=f"<div class='card'><b>Kết luận CIO:</b> VNINDEX {num(vn.get('close'))} ({pct(vn.get('change_pct'))}), VN30 {num(vn30.get('close'))} ({pct(vn30.get('change_pct'))}). Breadth HOSE {br.get('advancers')} tăng / {br.get('decliners')} giảm, A/D {br.get('adv_dec_ratio')}, above MA20 {br.get('above_ma20_pct')}%. Phái sinh: dùng FireAnt làm nguồn chính OHLCV/value/basis, VNDIRECT bổ sung mapping + OI. Long/short chỉ dùng proxy, không coi là vị thế thật. Hành động: chọn lọc, giữ kỷ luật entry/invalidation, không risk-on đại trà.</div>"
    html_doc+='<h2>Dashboard số liệu dùng trong các lens</h2>'+table(['Nhóm dữ liệu','Số liệu chính','Ý nghĩa đầu tư'],[
        ['Chỉ số',f"VNINDEX {num(vn.get('close'))}, 1D {pct(vn.get('change_pct'))}; VN30 {num(vn30.get('close'))}, 1D {pct(vn30.get('change_pct'))}; HNX {pct(hnx.get('change_pct'))}, UPCOM {pct(up.get('change_pct'))}",'Large-cap/breadth cần đọc chung; tránh nhầm kéo chỉ số thành broad risk-on.'],
        ['Breadth',f"{br.get('advancers')} tăng / {br.get('decliners')} giảm; A/D {br.get('adv_dec_ratio')}; above MA20 {br.get('above_ma20_pct')}%; coverage {qual.get('coverage_pct')}%",'Nếu breadth không mở rộng, chỉ giải ngân chọn lọc.'],
        ['Signal scan',f"{len(signals)} tín hiệu; watch {len([s for s in signals if s.get('status')=='watch'])}; actionable {len([s for s in signals if s.get('status')=='actionable'])}",'Cơ hội kỹ thuật phải đi cùng entry zone và invalidation.'],
        ['Derivatives',f"{len(deriv.get('rows') or [])} dòng VN30F; basis tính bằng futures - VN30; OI từ VNDIRECT",'Basis/OI là lens hedge/risk appetite; long/short chỉ proxy.'],
        ['Danh mục',f"NAV {pf.get('nav') or 'N/A'}; cash {pf.get('cash_pct')}; PnL {pf.get('total_pnl_pct')}",'Constraint danh mục quyết định size trước khi thêm mã mới.']])
    html_doc+='<h2>Native multi-agent lens — hedge fund style, có số liệu support</h2>'
    lens=[
      ('1. Market Strategist','Tích cực có điều kiện',f"VNINDEX {num(vn.get('close'))}, VN30 {num(vn30.get('close'))}; breadth {br.get('advancers')}/{br.get('decliners')}, above MA20 {br.get('above_ma20_pct')}%. Base case: chọn lọc, không mua dàn trải nếu breadth yếu."),
      ('2. Macro / Rates Strategist','Rates hurdle',"Lãi suất và FX vẫn là hurdle cho beta cao. Dùng macro_rates_live/CafeF/SBV/WebGia làm context; không trả premium định giá nếu earnings/flow chưa xác nhận."),
      ('3. Sector Flow Analyst','FireAnt sector flow','FireAnt bổ sung value traded, money flow, foreign net, PE/PB theo ngành. Ưu tiên ngành có GTGD lớn, money flow dương, foreign net không bị bán áp đảo.'),
      ('4. Derivatives Strategist','VN30F basis/OI proxy','FireAnt là nguồn chính futures OHLCV/value/basis; VNDIRECT bổ sung mapping + openInterest. Long/short không có endpoint public sạch; proxy gồm foreign_net, prop_net_value, oi_change.'),
      ('5. Foreign Flow Analyst','NN mua/bán ròng','Foreign net theo ngành và futures dùng như dòng tiền xác nhận/discount conviction. Không coi foreign_net futures là long/short thật.'),
      ('6. Equity Technical Analyst','Trade chọn lọc, size theo ATR','Chỉ dùng setup có entry zone, invalidation và volume xác nhận. Không mua đuổi ngoài vùng entry.'),
      ('7. Quant Researcher','Signal hợp lệ nhưng phân phối hẹp',f"Universe có {len(signals)} tín hiệu; watch/actionable còn hẹp. Ranking dùng để ưu tiên research, không tự động mua toàn bộ idea."),
      ('8. Risk Manager','Constraint chính: concentration + cash','Portfolio risk/cash/concentration là gate trước khi mở vị thế mới. Mỗi lệnh phải có max loss và stop rõ.'),
      ('9. Portfolio Advisor','Tái cân bằng trước khi mở rộng','Nếu danh mục thiếu cash hoặc tập trung, ưu tiên giảm rủi ro hiện hữu trước khi thêm mã mới.'),
      ('10. Investment Data Designer','Data provenance rõ','Nguồn mới: FireAnt primary OHLCV/value/basis; VNDIRECT mapping + OI. Missing khác zero; proxy phải ghi caveat.')]
    for name,tag,body in lens:
        html_doc+=f"<div class='lens'><h3>{esc(name)}</h3><span class='tag'>{esc(tag)}</span><ul><li><b>Luận điểm:</b> {esc(body)}</li><li><b>Trigger hành động:</b> chỉ nâng rủi ro khi giá, breadth, flow và risk budget cùng xác nhận.</li></ul></div>"
    html_doc+='<h2>Sector flow — FireAnt</h2>'+table(['Ngành','%','GTGD','NN ròng','Money +','Money -','P/E','P/B'],sector_rows)
    html_doc+='<h2>VN30 derivatives / basis / OI</h2><div class="card"><b>Caveat:</b> FireAnt dùng cho OHLCV/value/basis. VNDIRECT dùng mapping + OI. Long/short chỉ là proxy từ foreign_net, prop_net_value, oi_change; không phải vị thế long/short thực.</div>'+table(['Ngày','Symbol','VND code','F close','VN30 close','Basis','Basis %','Vol','Value','OI','OI Δ','Foreign net qty','Foreign net value','Prop net value'],deriv_rows)
    html_doc+='<h2>Signal hành động / watchlist</h2>'+table(['Mã','Status','Score','Entry','Invalidation','Risk/Evidence'],sig_rows)
    if pf_rows: html_doc+='<h2>Portfolio constraint</h2>'+table(['Metric','Value'],pf_rows)
    html_doc+='<h2>Kết luận hành động phiên kế tiếp</h2><ul><li><b>Base case:</b> giữ bias chọn lọc; không risk-on đại trà.</li><li><b>Buy trigger:</b> VNINDEX/VN30 giữ trend, breadth cải thiện, ngành có flow tốt, setup có volume và invalidation rõ.</li><li><b>Risk-off trigger:</b> VN30 đảo chiều, basis/OI xấu đi, foreign net bán mạnh, VNINDEX mất hỗ trợ ngắn hạn.</li><li><b>Portfolio action:</b> xử lý cash/concentration trước; size theo ATR/invalidation.</li></ul>'
    html_doc+='</body></html>'
    OUT.mkdir(exist_ok=True); DEST.mkdir(parents=True,exist_ok=True)
    out_html=OUT/f'invest-os-vn-bao-cao-hanh-dong-HF-lens-data-rich-{date}.html'
    out_pdf=DEST/f'invest-os-vn-bao-cao-hanh-dong-HF-lens-data-rich-{date}.pdf'
    out_html.write_text(html_doc,encoding='utf-8')
    chrome=Path(r'C:\Program Files\Google\Chrome\Application\chrome.exe')
    subprocess.run([str(chrome),'--headless','--disable-gpu','--no-sandbox',f'--print-to-pdf={out_pdf}',out_html.resolve().as_uri()],check=True)
    print(out_pdf)
if __name__=='__main__': main()
