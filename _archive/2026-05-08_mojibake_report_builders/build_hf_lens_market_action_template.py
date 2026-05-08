from __future__ import annotations
import json, html, subprocess
from datetime import datetime
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'outputs'; LIVE=ROOT/'data_live'; DEST=Path(r'C:\Users\DUC\Desktop\InvestOS_VN_PDF_Reports')

def load(p):
    p=Path(p); return json.loads(p.read_text(encoding='utf-8')) if p.exists() else {}
def esc(x): return html.escape(str('' if x is None else x))
def val(x): return x is not None
def pct(x):
    try: return f'{float(x):+.2f}%'
    except Exception: return 'thiếu field'
def pct_plain(x):
    try: return f'{float(x):.2f}%'
    except Exception: return 'thiếu field'
def num(x,d=2):
    try: return f'{float(x):,.{d}f}'
    except Exception: return 'thiếu field'
def bil(x):
    try: return f'{float(x)/1_000_000_000:,.1f} tỷ'
    except Exception: return 'thiếu field'
def table(headers, rows):
    s='<table><tr>'+''.join(f'<th>{esc(h)}</th>' for h in headers)+'</tr>'
    for r in rows:
        s+='<tr>'+''.join(f'<td>{c if isinstance(c,str) and c.startswith("<") else esc(c)}</td>' for c in r)+'</tr>'
    return s+'</table>'
def top(rows,key,n=10,rev=True): return sorted([r for r in rows if r.get(key) is not None],key=lambda r:r.get(key) or 0,reverse=rev)[:n]
def chg(r):
    try: return (float(r.get('index_close'))/float(r.get('index_prev'))-1)*100
    except Exception: return None
def missing(obj, fields): return [f for f in fields if obj.get(f) is None]
def strongest_name(rows,key,rev=True):
    xs=top(rows,key,1,rev)
    return xs[0] if xs else {}

def sector_analysis(level4):
    if not level4: return '<li><b>Foreign flow/sector flow:</b> thiếu field industry_flows.</li>'
    li=[]
    net_buy=strongest_name(level4,'foreign_net_value_vnd',True); net_sell=strongest_name(level4,'foreign_net_value_vnd',False)
    pos=strongest_name(level4,'positive_money_flow_vnd',True); neg=strongest_name(level4,'negative_money_flow_vnd',True)
    up=top([r for r in level4 if chg(r) is not None],'_dummy',0)
    chgs=[(chg(r),r) for r in level4 if chg(r) is not None]
    best=max(chgs,key=lambda x:x[0])[1] if chgs else {}; worst=min(chgs,key=lambda x:x[0])[1] if chgs else {}
    if net_buy:
        li.append(f"Khối ngoại mua ròng mạnh nhất ở {net_buy.get('industry_name')} với {bil(net_buy.get('foreign_net_value_vnd'))}; bán ròng mạnh nhất ở {net_sell.get('industry_name')} với {bil(net_sell.get('foreign_net_value_vnd'))}. Dòng ngoại vì vậy phân hóa, không đủ đọc một chiều risk-on/risk-off nếu chỉ nhìn chỉ số.")
    else: li.append('thiếu field foreign_net_value_vnd theo ngành')
    if pos:
        li.append(f"Money flow dương lớn nhất ở {pos.get('industry_name')} ({bil(pos.get('positive_money_flow_vnd'))}); áp lực tiền âm lớn nhất ở {neg.get('industry_name')} ({bil(neg.get('negative_money_flow_vnd'))}). Nhóm hút tiền mạnh cần được ưu tiên hơn nhóm chỉ tăng giá nhưng value thấp.")
    else: li.append('thiếu field positive_money_flow_vnd/negative_money_flow_vnd')
    if best:
        li.append(f"Ngành kéo tốt nhất theo chỉ số là {best.get('industry_name')} ({pct(chg(best))}); ngành chặn thị trường rõ nhất là {worst.get('industry_name')} ({pct(chg(worst))}). Đây là điểm kiểm tra breadth ngành: nếu leader ít nhưng laggard nhiều, mua đuổi chỉ số rủi ro cao.")
    else: li.append('thiếu field index_close/index_prev để tính ngành kéo/chặn')
    pe_rows=[r for r in level4 if r.get('pe') and r.get('pb')]
    if pe_rows:
        rich=max(pe_rows,key=lambda r: float(r.get('pe') or 0)); cheap=min(pe_rows,key=lambda r: float(r.get('pe') or 999999))
        li.append(f"Định giá ngành có số: P/E cao nhất {rich.get('industry_name')} PE {num(rich.get('pe'),1)}, PB {num(rich.get('pb'),1)}; P/E thấp nhất {cheap.get('industry_name')} PE {num(cheap.get('pe'),1)}, PB {num(cheap.get('pb'),1)}. PE/PB chỉ nên dùng để lọc rủi ro định giá, không thay thế tín hiệu dòng tiền.")
    else: li.append('thiếu field pe/pb theo ngành')
    return '<li><b>Foreign flow/sector flow:</b> '+' '.join(li)+'</li>'

def derivatives_analysis(rows):
    if not rows: return '<li><b>Derivatives:</b> thiếu field rows trong derivatives_live.vn.json.</li>'
    near=sorted(rows,key=lambda r: (-(r.get('fireant_volume') or 0), r.get('symbol') or ''))[0]
    miss=missing(near,['future_close','vn30_close','basis','basis_pct','open_interest','oi_change','foreign_net_qty','foreign_net_value'])
    parts=[]
    parts.append(f"Hợp đồng gần/active {near.get('symbol')} đóng {num(near.get('future_close'))}, VN30 cơ sở {num(near.get('vn30_close'))}, basis {num(near.get('basis'))} điểm ({pct_plain(near.get('basis_pct'))}).")
    if val(near.get('basis')):
        basis=float(near.get('basis'))
        if basis>0: parts.append('Basis dương cho thấy futures đang premium so với VN30, nghiêng kỳ vọng ngắn hạn tích cực nhưng chưa đủ xác nhận nếu OI co lại.')
        elif basis<0: parts.append('Basis âm cho thấy futures discount so với VN30, nghiêng phòng thủ/risk-off proxy.')
        else: parts.append('Basis gần 0 cho thấy futures không trả premium rõ cho nhịp tăng.')
    if val(near.get('oi_change')):
        oi=float(near.get('oi_change') or 0)
        if oi>0: parts.append(f"OI tăng {num(oi,0)} hợp đồng: vị thế mở rộng, tín hiệu đáng chú ý nếu đi cùng basis cùng chiều.")
        elif oi<0: parts.append(f"OI giảm {num(oi,0)} hợp đồng: dòng vị thế đang co lại, nhịp basis/giá thiếu xác nhận đòn bẩy mới.")
        else: parts.append('OI không đổi: thiếu xác nhận vị thế mới.')
    if val(near.get('foreign_net_qty')) or val(near.get('foreign_net_value')):
        fq=float(near.get('foreign_net_qty') or 0); fv=float(near.get('foreign_net_value') or 0)
        bias='lực cản risk-on vì khối ngoại đang net short/bán ròng phái sinh' if fq<0 or fv<0 else ('hỗ trợ risk-on nhẹ vì khối ngoại net long/mua ròng phái sinh' if fq>0 or fv>0 else 'trung tính vì khối ngoại không net đáng kể')
        parts.append(f"Khối ngoại phái sinh net {num(near.get('foreign_net_qty'),0)} hợp đồng, giá trị {bil(near.get('foreign_net_value'))}; đọc là {bias}.")
    if miss: parts.append('Thiếu field '+', '.join(miss)+'.')
    return '<li><b>Derivatives:</b> '+' '.join(parts)+'</li>'

def main():
    now=datetime.now().astimezone(); date=now.strftime('%Y-%m-%d')
    breadth=load(OUT/'fdata_hose_breadth.json'); sig=load(OUT/'stock_signal_scan_investable.json'); pf=load(OUT/'portfolio_action_report.json')
    fire=load(LIVE/'fireant_foreign_flow.vn.json'); deriv=load(LIVE/'derivatives_live.vn.json')
    br=(breadth.get('breadth') or {}) if isinstance(breadth,dict) else {}; indices=(breadth.get('market') or {}).get('indices') or []
    idx={x.get('symbol'):x for x in indices}; vn=idx.get('VNINDEX',{}); vn30=idx.get('VN30',{}); hnx=idx.get('HNXINDEX',{}); up=idx.get('UPCOM') or idx.get('UPCOMINDEX',{})
    signals=sig.get('signals',[]) if isinstance(sig,dict) else []
    watch=[s for s in signals if s.get('status')=='watch'][:8]; ideas=[s for s in signals if s.get('status') in ('idea','actionable')][:8]
    picked=(watch+ideas)[:14]
    no_actionable_note=''
    if not picked:
        picked=sorted(signals,key=lambda s: s.get('score') or 0,reverse=True)[:14]
        no_actionable_note='<div class="card"><b>Không có tín hiệu mua/watch đạt chuẩn trong lần scan này.</b> Toàn bộ signal đang ở trạng thái avoid, nên bảng dưới là nhóm điểm cao nhất để theo dõi rủi ro/loại trừ, không phải danh sách mua.</div>'
    sig_rows=[]
    for s in picked:
        ev=s.get('risk_evidence') or s.get('evidence') or 'thiếu field evidence'
        if isinstance(ev,list): ev='; '.join(str(x) for x in ev[:3])
        sig_rows.append([s.get('ticker'),s.get('status'),s.get('score'),s.get('entry_zone'),s.get('invalidation'),ev])
    industries=fire.get('industry_flows',[]) if isinstance(fire,dict) else []; level4=[r for r in industries if r.get('level')==4]
    sector_rows=[]
    for r in top(level4,'value_vnd',10):
        sector_rows.append([r.get('industry_name'),pct(chg(r)),bil(r.get('value_vnd')),bil(r.get('foreign_net_value_vnd')),bil(r.get('positive_money_flow_vnd')),bil(r.get('negative_money_flow_vnd')),r.get('pe') if r.get('pe') is not None else 'thiếu field pe',r.get('pb') if r.get('pb') is not None else 'thiếu field pb'])
    deriv_rows=[]; drows=deriv.get('rows') or []
    for r in drows[:12]: deriv_rows.append([r.get('date'),r.get('symbol'),r.get('vndirect_code'),num(r.get('future_close')),num(r.get('vn30_close')),num(r.get('basis')),pct_plain(r.get('basis_pct')),num(r.get('fireant_volume'),0),bil(r.get('fireant_value')),num(r.get('open_interest'),0),num(r.get('oi_change'),0),num(r.get('foreign_net_qty'),0),bil(r.get('foreign_net_value'))])
    css='''@page{size:A4;margin:14mm 12mm}body{font-family:Arial,"Segoe UI",sans-serif;font-size:11px;line-height:1.45;color:#111}h1{font-size:23px;margin:0 0 6px}h2{font-size:16px;margin-top:20px;border-bottom:1px solid #ddd;padding-bottom:4px}h3{font-size:13px;margin:12px 0 4px}.meta{color:#555}.card{background:#f7f9fb;border:1px solid #e2e6ea;border-radius:8px;padding:10px 12px;margin:10px 0}.agent{page-break-inside:avoid;border:1px solid #e5e5e5;border-radius:7px;padding:9px;margin:8px 0}.tag{display:inline-block;background:#eef3ff;border:1px solid #ccd8ff;border-radius:10px;padding:1px 6px;margin-right:4px;font-size:9px}ul{margin:4px 0 8px 18px;padding:0}li{margin:3px 0}table{border-collapse:collapse;width:100%;font-size:10px}td,th{border:1px solid #ddd;padding:5px;text-align:left;vertical-align:top}th{background:#f1f3f5}.warn{color:#9a6700;font-weight:bold}.ok{color:#087f23;font-weight:bold}'''
    html_doc=f"<html><head><meta charset='utf-8'><style>{css}</style></head><body>"
    html_doc+=f"<h1>InvestOS VN — Báo cáo thị trường & hành động ngày {date} (bản nâng cấp Hedge Fund Lens)</h1>"
    html_doc+=f"<div class='meta'>PDF tiếng Việt | Mẫu chuẩn: invest-os-vn-bao-cao-thi-truong-hanh-dong-HF-lens-2026-05-07 | Tạo lúc {now.isoformat(timespec='seconds')}</div>"
    html_doc+=f"<div class='card'><b>Kết luận nhanh:</b> VNINDEX đóng cửa {num(vn.get('close'))} điểm, {pct(vn.get('change_pct'))}; VN30 {pct(vn30.get('change_pct'))}. HOSE có {br.get('advancers')} mã tăng / {br.get('decliners')} mã giảm, A/D {br.get('adv_dec_ratio')}, above MA20 {br.get('above_ma20_pct')}%. Bối cảnh nghiêng hồi kỹ thuật có chọn lọc hơn là risk-on rộng.</div>"
    html_doc+='<h2>1. Số liệu chỉ số chính</h2>'+table(['Chỉ số','Đóng cửa','Thay đổi','Khối lượng','Nguồn'],[['VNINDEX',num(vn.get('close')),pct(vn.get('change_pct')),num(vn.get('volume_mn'),1)+' triệu cp','market index feed'],['VN30',num(vn30.get('close')),pct(vn30.get('change_pct')),num(vn30.get('volume_mn'),1)+' triệu cp','market index feed'],['HNXINDEX',num(hnx.get('close')),pct(hnx.get('change_pct')),num(hnx.get('volume_mn'),1)+' triệu cp','market index feed'],['UPCOMINDEX',num(up.get('close')),pct(up.get('change_pct')),num(up.get('volume_mn'),1)+' triệu cp','market index feed']])
    html_doc+='<h2>2. Nhận định thị trường</h2><ul>'
    html_doc+=f"<li><b>Xu hướng ngắn hạn:</b> VNINDEX {pct(vn.get('change_pct'))}, VN30 {pct(vn30.get('change_pct'))}. Nếu VNINDEX tăng mạnh hơn VN30, lực kéo không chỉ nằm ở bluechip; nếu VN30 yếu hơn nhưng breadth xấu, nhịp tăng thiếu nền lan tỏa.</li>"
    html_doc+=f"<li><b>Độ rộng:</b> HOSE {br.get('advancers')} tăng / {br.get('decliners')} giảm, A/D {br.get('adv_dec_ratio')}, above MA20 {br.get('above_ma20_pct')}%. Breadth yếu hơn chỉ số, nên giải ngân mới phải ưu tiên mã có RS/volume xác nhận và điểm hủy rõ.</li>"
    html_doc+=sector_analysis(level4)
    html_doc+=derivatives_analysis(drows)+'</ul>'
    html_doc+='<h2>3. Tín hiệu cổ phiếu đáng chú ý</h2>'+no_actionable_note+table(['Mã','Trạng thái','Score','Vùng mua','Điểm hủy','Cơ sở'],sig_rows)
    html_doc+='<h2>4. Danh mục hiện tại</h2><ul>'+f"<li>NAV {pf.get('nav') or 'thiếu field nav'}; cash {pf.get('cash_pct')}; total PnL {pf.get('total_pnl_pct')}.</li>"
    for r in (pf.get('risks') or []): html_doc+=f'<li>Rủi ro: {esc(r)}</li>'
    html_doc+='<li>Hành động: ưu tiên risk budget/cash buffer trước khi mở vị thế mới.</li></ul>'
    html_doc+='<h2>5. Native multi-agent lens — phân tích chi tiết kiểu hedge fund</h2>'
    active=sorted(drows,key=lambda r: r.get('fireant_volume') or 0,reverse=True)[0] if drows else {}
    nb=strongest_name(level4,'foreign_net_value_vnd',True); ns=strongest_name(level4,'foreign_net_value_vnd',False); mf=strongest_name(level4,'positive_money_flow_vnd',True); mn=strongest_name(level4,'negative_money_flow_vnd',True)
    adv=br.get('advancers'); dec=br.get('decliners'); ad=br.get('adv_dec_ratio'); ma20=br.get('above_ma20_pct')
    nav=pf.get('nav_vnd') or pf.get('nav') or 'thiếu field nav_vnd'; cash=pf.get('cash_vnd') if pf.get('cash_vnd') is not None else 'thiếu field cash_vnd'; cash_pct=(float(cash)/float(nav)*100) if isinstance(cash,(int,float)) and isinstance(nav,(int,float)) and nav else None
    agents=[
      {'name':'1. Market Strategist','tag':'Tích cực có điều kiện','thesis':f"VNINDEX {pct(vn.get('change_pct'))} lên {num(vn.get('close'))}, mạnh hơn VN30 {pct(vn30.get('change_pct'))}; nhưng HOSE chỉ {adv} tăng / {dec} giảm, A/D {ad}, above MA20 {ma20}%. Đây là nhịp hồi chỉ số trong breadth yếu, chưa phải risk-on rộng.",'cross':f"Risk lens phải giữ kỷ luật vì breadth {ad} < 1; derivatives lens cũng không xác nhận mạnh khi {active.get('symbol','VN30F')} basis {num(active.get('basis'))} điểm nhưng OI Δ {num(active.get('oi_change'),0)}.",'trigger':f"Chỉ nâng exposure khi A/D vượt 1.0 và above MA20 >50%; nếu A/D còn quanh {ad} hoặc VN30 mất vùng {num(vn30.get('close'))}, ưu tiên giữ tiền/không mở thêm."},
      {'name':'2. Macro Strategist','tag':'Trung tính-thận trọng','thesis':f"Market regime trong portfolio report là {pf.get('market_regime','thiếu field market_regime')}; cash hệ thống {bil(cash) if isinstance(cash,(int,float)) else cash}, danh mục 100% PNJ cho thấy khả năng hấp thụ shock thấp hơn bình thường.",'cross':f"Market lens thấy chỉ số tăng, nhưng sector flow lại có bán ròng mạnh ở {ns.get('industry_name','thiếu ngành')} {bil(ns.get('foreign_net_value_vnd'))}; điều này không ủng hộ mở beta vĩ mô đại trà.",'trigger':f"Chỉ chuyển từ neutral sang risk-on khi foreign net ngành trụ không còn âm sâu và breadth >50% MA20; nếu BĐS còn bị bán ròng {bil(ns.get('foreign_net_value_vnd'))}, giữ view chọn lọc."},
      {'name':'3. Rates / Fixed Income Analyst','tag':'Giữ risk vừa phải','thesis':f"Nhóm nhạy lãi suất bị kiểm tra bởi dòng tiền: {mn.get('industry_name','thiếu ngành')} có money flow âm {bil(mn.get('negative_money_flow_vnd'))}; nếu là nhóm đòn bẩy, rủi ro chi phí vốn vẫn nằm trong giá.",'cross':f"Real Estate lens không được chase vì {ns.get('industry_name','thiếu ngành')} bị khối ngoại bán ròng {bil(ns.get('foreign_net_value_vnd'))} và PE/PB của nhóm này trong bảng ngành cao hơn mặt bằng nhiều nơi.",'trigger':f"Không tăng tỷ trọng BĐS/thép nếu money flow âm ngành vẫn > {bil(mn.get('negative_money_flow_vnd'))} hoặc foreign net còn âm; chỉ xem xét khi dòng tiền âm co lại và giá giữ MA20."},
      {'name':'4. Fundamental Analyst','tag':'Chọn lọc chất lượng','thesis':f"Không có tín hiệu mua/watch đạt chuẩn: {len(signals)} signals đều bị avoid trong scan hiện tại. Cơ bản phải là bộ lọc chính, không dùng bounce +1.12% của VNINDEX để mua cổ phiếu yếu.",'cross':f"Quant lens đang cảnh báo tránh mua mới; Portfolio lens cũng có cash {bil(cash) if isinstance(cash,(int,float)) else cash} và concentration PNJ 100%, nên cổ phiếu chỉ có câu chuyện giá nhưng thiếu earnings/cashflow phải loại.",'trigger':"Chỉ đưa mã vào shortlist nếu status khác avoid, score >0.5, có evidence về MA20/MA50/RS20D và thesis cơ bản không xấu; nếu thiếu evidence thì ghi thiếu field, không tự suy luận."},
      {'name':'5. Banking Sector Analyst','tag':'Dẫn dắt cần xác nhận','thesis':f"Money flow dương mạnh nhất nằm ở {mf.get('industry_name','thiếu ngành')} với {bil(mf.get('positive_money_flow_vnd'))}; nếu đây là ngân hàng, dòng tiền đang chọn nhóm trụ, nhưng VN30 chỉ {pct(vn30.get('change_pct'))} thấp hơn VNINDEX {pct(vn.get('change_pct'))}, nên bank chưa kéo toàn thị trường áp đảo.",'cross':f"Market lens vẫn cần breadth; nếu bank hút tiền nhưng HOSE A/D chỉ {ad}, dòng tiền có thể đang xoay trụ chứ chưa lan tỏa sang midcap.",'trigger':f"Overweight bank chỉ khi {mf.get('industry_name','ngành dẫn')} tiếp tục giữ money flow dương > {bil(mf.get('positive_money_flow_vnd'))} và VN30 outperform VNINDEX; ngược lại chỉ giữ watchlist."},
      {'name':'6. Real Estate Sector Analyst','tag':'Tránh mua đuổi','thesis':f"{ns.get('industry_name','Bất động sản')} là điểm yếu lớn: foreign net {bil(ns.get('foreign_net_value_vnd'))}, money flow âm {bil(ns.get('negative_money_flow_vnd'))}, và biến động ngành {pct(chg(ns))}. Đây là cụm số không ủng hộ chase.",'cross':f"Rates lens cũng không ủng hộ nhóm đòn bẩy; Market lens cho thấy breadth yếu {adv}/{dec}, nên BĐS chỉ được trade nếu có setup riêng rất sạch.",'trigger':f"Không mua BĐS khi foreign net còn âm quanh {bil(ns.get('foreign_net_value_vnd'))}; chỉ cân nhắc nếu ngành đảo lên, money flow âm co mạnh, và mã riêng vượt MA20 kèm volume thật."},
      {'name':'7. Steel / Materials Analyst','tag':'Watchlist chu kỳ','thesis':f"Cyclicals cần breadth và thanh khoản lan tỏa, nhưng hiện HOSE {adv} tăng / {dec} giảm và above MA20 {ma20}%. Điều kiện này chưa đủ cho thesis hàng hóa/vật liệu diện rộng.",'cross':f"Quant scan không có watch/actionable; Risk lens giữ hạn mức vì danh mục không có cash buffer. Vì vậy thép/vật liệu chỉ nên là watch, không phải allocation mới.",'trigger':f"Chỉ kích hoạt khi A/D >1, above MA20 >50%, và mã thép/vật liệu có score >0.5; nếu signal vẫn avoid 0.05 thì bỏ qua."},
      {'name':'8. Equity Technical Analyst','tag':'Không có setup đạt chuẩn','thesis':f"Scan trả {len(signals)} signals nhưng không có watch/idea/actionable; nhóm cao nhất vẫn status avoid, score 0.05, nhiều evidence volume ratio 0. Đây là tín hiệu kỹ thuật rất yếu cho mua mới.",'cross':f"Market bounce +{pct(vn.get('change_pct'))} không đủ bẻ tín hiệu kỹ thuật vì breadth {ad} và above MA20 {ma20}% còn xấu; Portfolio lens cũng không có cash.",'trigger':"Không mở vị thế từ bảng signal hiện tại. Chỉ trade khi xuất hiện status watch/idea, score >=0.55, volume ratio >1.5 và invalidation không quá xa entry."},
      {'name':'9. Quant Researcher','tag':'Model cảnh báo tránh mua','thesis':f"Distribution tín hiệu cực lệch: {len(signals)} mã, không có watch/idea/actionable sau filter investable. Nếu model chỉ trả avoid, output đúng là risk filter chứ không phải buy list.",'cross':f"Technical lens xác nhận thiếu setup; Market lens cho thấy chỉ số tăng nhưng breadth yếu, nên quant không được ép chọn top avoid thành khuyến nghị mua.",'trigger':"Ngày tới cần kiểm tra vì sao volume ratio nhiều mã bằng 0; nếu do data stale thì ghi thiếu/quality warning, nếu data đúng thì giữ no-new-buy."},
      {'name':'10. Derivatives Strategist','tag':'Basis dương nhưng OI co','thesis':f"{active.get('symbol','thiếu symbol')} basis {num(active.get('basis'))} điểm ({pct_plain(active.get('basis_pct'))}), OI Δ {num(active.get('oi_change'),0)}, foreign net {num(active.get('foreign_net_qty'),0)} hợp đồng / {bil(active.get('foreign_net_value'))}. Premium nhỏ nhưng OI giảm và ngoại âm làm tín hiệu risk-on yếu.",'cross':f"Market lens thấy VNINDEX tăng, nhưng derivatives không xác nhận đòn bẩy mới vì OI co {num(active.get('oi_change'),0)}; Risk lens vì vậy không nên tăng gross exposure.",'trigger':f"Bullish hơn khi basis >0 duy trì và OI Δ chuyển dương; bearish nếu basis về âm hoặc foreign net tiếp tục dưới {num(active.get('foreign_net_qty'),0)} hợp đồng."},
      {'name':'11. Risk Manager','tag':'Không mở rủi ro mới','thesis':f"Danh mục NAV {bil(nav) if isinstance(nav,(int,float)) else nav}, cash {bil(cash) if isinstance(cash,(int,float)) else cash} ({num(cash_pct,1) if cash_pct is not None else 'thiếu field cash_pct'}%), holding PNJ 100%. Rủi ro lớn nhất là concentration + không có dry powder.",'cross':f"Technical/Quant không có setup mua; derivatives có OI giảm; sector flow phân hóa. Các lens không đủ đồng thuận để tăng rủi ro danh mục.",'trigger':"Không mua mới khi cash 0%. Giảm rủi ro nếu PNJ vi phạm thesis/stop riêng; chỉ mở lệnh mới sau khi tạo cash buffer tối thiểu 10%."},
      {'name':'12. Portfolio Advisor','tag':'Tái cân bằng trước','thesis':f"Portfolio report no_new_buy={pf.get('no_new_buy')}; concentration risks: {'; '.join(pf.get('concentration_risks') or [])}. Trạng thái này ưu tiên quản trị danh mục hơn săn tín hiệu mới.",'cross':f"Risk Manager đồng thuận cash 0%; Technical lens không có actionable signal, nên mua thêm sẽ làm danh mục yếu hơn về optionality.",'trigger':"Bước 1 là xác định mức giảm PNJ/tạo cash; bước 2 mới xem watchlist. Nếu cash chưa lên >=10% NAV, mọi signal mới chỉ để theo dõi."},
      {'name':'13. Wealth Asset Manager','tag':'Phòng thủ chủ động','thesis':f"Tài sản đang 100% một mã và cash 0%, trong khi thị trường breadth yếu {adv}/{dec}. Với wealth lens, rủi ro sequencing quan trọng hơn bắt nhịp tăng một phiên.",'cross':f"Market/Derivatives cho thấy hồi nhưng xác nhận yếu; Portfolio/Risk cho thấy không có buffer. Vì vậy allocation phải chuyển từ tối đa hóa upside sang bảo toàn quyền chọn.",'trigger':"Ưu tiên tái lập cash buffer 10-20% NAV; chỉ dùng phần nhỏ cho lệnh có R/R rõ, không dùng margin trong bối cảnh A/D <1."},
      {'name':'14. Investment Data Designer','tag':'Data quality gate','thesis':f"Report có số cụ thể cho breadth ({adv}/{dec}, above MA20 {ma20}%), sector flow ({mf.get('industry_name','thiếu ngành')} money+ {bil(mf.get('positive_money_flow_vnd'))}) và derivatives ({active.get('symbol','thiếu symbol')} basis {num(active.get('basis'))}). Không được thay các số này bằng mô tả pipeline.",'cross':"Các lens đang phụ thuộc vào 3 lớp số: breadth, sector/foreign flow, derivatives/OI. Nếu một field thiếu, report phải nêu đúng field thiếu để analyst không hiểu nhầm thành giá trị 0.",'trigger':"Trước khi publish, chạy check cấm placeholder và check mỗi agent có số cụ thể trong thesis/cross/trigger; nếu thiếu thì fail build thay vì xuất PDF rỗng."}
    ]
    for a in agents:
        html_doc+=f"<div class='agent'><h3>{esc(a['name'])}</h3><div><span class='tag'>{esc(a['tag'])}</span></div><ul><li><b>Luận điểm:</b> {esc(a['thesis'])}</li><li><b>Đọc chéo với lens khác:</b> {esc(a['cross'])}</li><li><b>Trigger hành động:</b> {esc(a['trigger'])}</li></ul></div>"
    html_doc+='<h2>6. Sector flow / foreign flow</h2>'+table(['Ngành','%','GTGD','NN ròng','Money +','Money -','P/E','P/B'],sector_rows)
    html_doc+='<h2>7. VN30 derivatives / basis / OI</h2>'+table(['Ngày','Symbol','VND code','F close','VN30 close','Basis','Basis %','Vol','Value','OI','OI Δ','Foreign net qty','Foreign net value'],deriv_rows)
    html_doc+='<h2>8. Kết luận giao dịch phiên kế tiếp</h2><ul><li><b>Base case:</b> hồi kỹ thuật có chọn lọc; ưu tiên mã mạnh hơn thị trường và có thanh khoản thật.</li><li><b>Bull trigger:</b> VN30 giữ đà, VNINDEX không mất hỗ trợ ngắn hạn, breadth cải thiện, sector/foreign flow không xấu.</li><li><b>Bear trigger:</b> VN30 đảo chiều, basis/OI xấu, top signal thủng invalidation, cash/concentration không được xử lý.</li><li><b>Portfolio action:</b> mỗi lệnh mới có stop, size theo ATR, không vượt risk budget.</li></ul></body></html>'
    OUT.mkdir(exist_ok=True); DEST.mkdir(parents=True,exist_ok=True)
    out_html=OUT/f'invest-os-vn-bao-cao-hanh-dong-HF-lens-data-rich-{date}.html'; out_pdf=DEST/f'invest-os-vn-bao-cao-hanh-dong-HF-lens-data-rich-{date}.pdf'
    out_html.write_text(html_doc,encoding='utf-8')
    chrome=Path(r'C:\Program Files\Google\Chrome\Application\chrome.exe')
    subprocess.run([str(chrome),'--headless','--disable-gpu','--no-sandbox',f'--print-to-pdf={out_pdf}',out_html.resolve().as_uri()],check=True)
    print(out_pdf)
if __name__=='__main__': main()
