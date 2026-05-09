#!/usr/bin/env python
from __future__ import annotations

import argparse
import html
import json
import re
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs"
LIVE = ROOT / "data_live"
BANNED_PATTERNS = ["�", "NgA", "t���", "D?", "Lu?n", "bA�o", "d��"]


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def esc(value: Any) -> str:
    return html.escape(str("" if value is None else value))


def val(value: Any) -> bool:
    return value is not None


def pct(value: Any, signed: bool = True) -> str:
    try:
        fmt = "+.2f" if signed else ".2f"
        return f"{float(value):{fmt}}%"
    except Exception:
        return "missing field"


def num(value: Any, digits: int = 2) -> str:
    try:
        return f"{float(value):,.{digits}f}"
    except Exception:
        return "missing field"


def bil(value: Any) -> str:
    try:
        return f"{float(value) / 1_000_000_000:,.1f} tỷ"
    except Exception:
        return "missing field"


def table(headers: list[str], rows: list[list[Any]]) -> str:
    body = "<table><tr>" + "".join(f"<th>{esc(h)}</th>" for h in headers) + "</tr>"
    for row in rows:
        body += "<tr>" + "".join(f"<td>{cell if isinstance(cell, str) and cell.startswith('<') else esc(cell)}</td>" for cell in row) + "</tr>"
    return body + "</table>"


def top(rows: list[dict[str, Any]], key: str, n: int = 10, reverse: bool = True) -> list[dict[str, Any]]:
    return sorted([row for row in rows if row.get(key) is not None], key=lambda row: row.get(key) or 0, reverse=reverse)[:n]


def change_pct(row: dict[str, Any]) -> float | None:
    try:
        return (float(row.get("index_close")) / float(row.get("index_prev")) - 1) * 100
    except Exception:
        return None


def strongest(rows: list[dict[str, Any]], key: str, reverse: bool = True) -> dict[str, Any]:
    found = top(rows, key, 1, reverse)
    return found[0] if found else {}


def missing_fields(obj: dict[str, Any], fields: list[str]) -> list[str]:
    return [field for field in fields if obj.get(field) is None]


def sector_analysis(level4: list[dict[str, Any]]) -> str:
    if not level4:
        return "<li><b>Foreign flow/sector flow:</b> missing field industry_flows.</li>"
    net_buy = strongest(level4, "foreign_net_value_vnd", True)
    net_sell = strongest(level4, "foreign_net_value_vnd", False)
    pos = strongest(level4, "positive_money_flow_vnd", True)
    neg = strongest(level4, "negative_money_flow_vnd", True)
    chgs = [(change_pct(row), row) for row in level4 if change_pct(row) is not None]
    best = max(chgs, key=lambda item: item[0])[1] if chgs else {}
    worst = min(chgs, key=lambda item: item[0])[1] if chgs else {}
    parts: list[str] = []
    if net_buy:
        parts.append(f"Khối ngoại mua ròng mạnh nhất ở {net_buy.get('industry_name')} với {bil(net_buy.get('foreign_net_value_vnd'))}; bán ròng mạnh nhất ở {net_sell.get('industry_name')} với {bil(net_sell.get('foreign_net_value_vnd'))}.")
    else:
        parts.append("missing field foreign_net_value_vnd theo ngành")
    if pos:
        parts.append(f"Money flow dương lớn nhất ở {pos.get('industry_name')} ({bil(pos.get('positive_money_flow_vnd'))}); money flow âm lớn nhất ở {neg.get('industry_name')} ({bil(neg.get('negative_money_flow_vnd'))}).")
    else:
        parts.append("missing field positive_money_flow_vnd/negative_money_flow_vnd")
    if best:
        parts.append(f"Ngành kéo tốt nhất theo chỉ số là {best.get('industry_name')} ({pct(change_pct(best))}); ngành chặn rõ nhất là {worst.get('industry_name')} ({pct(change_pct(worst))}).")
    else:
        parts.append("missing field index_close/index_prev để tính ngành kéo/chặn")
    return "<li><b>Foreign flow/sector flow:</b> " + " ".join(parts) + "</li>"


def derivatives_active_row(rows: list[dict[str, Any]]) -> dict[str, Any]:
    latest_date = max([str(row.get("date") or "") for row in rows], default="")
    latest = [row for row in rows if str(row.get("date") or "") == latest_date] or rows
    return sorted(latest, key=lambda row: (row.get("fireant_volume") or row.get("vndirect_volume") or 0), reverse=True)[0] if latest else {}


def derivatives_analysis(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "<li><b>Derivatives:</b> missing field rows trong derivatives_live.vn.json.</li>"
    active = derivatives_active_row(rows)
    miss = missing_fields(active, ["future_close", "vn30_close", "basis", "basis_pct", "open_interest", "oi_change", "foreign_net_qty", "foreign_net_value"])
    parts = [f"Hợp đồng active {active.get('symbol')} đóng {num(active.get('future_close'))}, VN30 cơ sở {num(active.get('vn30_close'))}, basis {num(active.get('basis'))} điểm ({pct(active.get('basis_pct'), signed=False)})."]
    if val(active.get("basis")):
        basis = float(active.get("basis") or 0)
        parts.append("Basis dương: futures premium, kỳ vọng ngắn hạn tích cực nhưng cần OI xác nhận." if basis > 0 else "Basis âm: futures discount, proxy phòng thủ/risk-off." if basis < 0 else "Basis gần 0: không có premium rõ.")
    if val(active.get("oi_change")):
        oi_change = float(active.get("oi_change") or 0)
        parts.append(f"OI tăng {num(oi_change, 0)} hợp đồng: vị thế mở rộng." if oi_change > 0 else f"OI giảm {num(oi_change, 0)} hợp đồng: vị thế co lại." if oi_change < 0 else "OI không đổi: thiếu xác nhận vị thế mới.")
    if val(active.get("foreign_net_qty")) or val(active.get("foreign_net_value")):
        foreign_qty = float(active.get("foreign_net_qty") or 0)
        foreign_value = float(active.get("foreign_net_value") or 0)
        bias = "cản risk-on vì khối ngoại net short/bán ròng phái sinh" if foreign_qty < 0 or foreign_value < 0 else "hỗ trợ risk-on nhẹ vì khối ngoại net long/mua ròng phái sinh" if foreign_qty > 0 or foreign_value > 0 else "trung tính"
        parts.append(f"Khối ngoại phái sinh net {num(active.get('foreign_net_qty'), 0)} hợp đồng, giá trị {bil(active.get('foreign_net_value'))}; đọc là {bias}.")
    if miss:
        parts.append("Missing field " + ", ".join(miss) + ".")
    return "<li><b>Derivatives:</b> " + " ".join(parts) + "</li>"


def build_html() -> str:
    now = datetime.now().astimezone()
    date = now.strftime("%Y-%m-%d")
    breadth = load(OUT / "fdata_hose_breadth.json")
    signals = load(OUT / "stock_signal_scan_investable.json")
    portfolio = load(OUT / "portfolio_action_report.json") or load(OUT / "portfolio_daily.json")
    fireant = load(LIVE / "fireant_foreign_flow.vn.json")
    derivatives = load(LIVE / "derivatives_live.vn.json")
    eod = load(OUT / "eod_market_brief.json")

    br = (breadth.get("breadth") or {}) if isinstance(breadth, dict) else {}
    indices = (breadth.get("market") or {}).get("indices") or [] if isinstance(breadth, dict) else []
    idx = {item.get("symbol"): item for item in indices if isinstance(item, dict)}
    vn = idx.get("VNINDEX", {})
    vn30 = idx.get("VN30", {})
    hnx = idx.get("HNXINDEX", {})
    upcom = idx.get("UPCOM") or idx.get("UPCOMINDEX") or {}

    signal_rows_src = signals.get("signals", []) if isinstance(signals, dict) else []
    picked = [s for s in signal_rows_src if s.get("status") in {"watch", "idea", "actionable"}][:14]
    no_actionable_note = ""
    if not picked:
        picked = sorted(signal_rows_src, key=lambda s: s.get("score") or 0, reverse=True)[:14]
        no_actionable_note = "<div class='card'><b>Không có tín hiệu mua/watch đạt chuẩn.</b> Bảng dưới là nhóm điểm cao nhất để theo dõi, không phải danh sách mua.</div>"
    sig_rows = []
    for sig in picked:
        evidence = sig.get("risk_evidence") or sig.get("evidence") or "missing field evidence"
        if isinstance(evidence, list):
            evidence = "; ".join(str(x) for x in evidence[:3])
        sig_rows.append([sig.get("ticker"), sig.get("status"), sig.get("score"), sig.get("entry_zone"), sig.get("invalidation"), evidence])

    industries = fireant.get("industry_flows", []) if isinstance(fireant, dict) else []
    level4 = [row for row in industries if row.get("level") == 4]
    sector_rows = [[row.get("industry_name"), pct(change_pct(row)), bil(row.get("value_vnd")), bil(row.get("foreign_net_value_vnd")), bil(row.get("positive_money_flow_vnd")), bil(row.get("negative_money_flow_vnd")), row.get("pe") if row.get("pe") is not None else "missing field pe", row.get("pb") if row.get("pb") is not None else "missing field pb"] for row in top(level4, "value_vnd", 10)]

    drows = derivatives.get("rows", []) if isinstance(derivatives, dict) else []
    active = derivatives_active_row(drows)
    derivative_rows = [[row.get("date"), row.get("symbol"), row.get("vndirect_code"), num(row.get("future_close")), num(row.get("vn30_close")), num(row.get("basis")), pct(row.get("basis_pct"), signed=False), num(row.get("fireant_volume"), 0), bil(row.get("fireant_value")), num(row.get("open_interest"), 0), num(row.get("oi_change"), 0), num(row.get("foreign_net_qty"), 0), bil(row.get("foreign_net_value")), bil(row.get("prop_net_value"))] for row in drows[:16]]

    adv = br.get("advancers")
    dec = br.get("decliners")
    ad = br.get("adv_dec_ratio")
    ma20 = br.get("above_ma20_pct")
    nav = portfolio.get("nav_vnd") or portfolio.get("nav")
    cash = portfolio.get("cash_vnd")
    cash_pct = (float(cash) / float(nav) * 100) if isinstance(cash, (int, float)) and isinstance(nav, (int, float)) and nav else portfolio.get("cash_pct")
    net_buy = strongest(level4, "foreign_net_value_vnd", True)
    net_sell = strongest(level4, "foreign_net_value_vnd", False)
    pos_flow = strongest(level4, "positive_money_flow_vnd", True)
    neg_flow = strongest(level4, "negative_money_flow_vnd", True)
    thesis = eod.get("market_thesis") or f"VNINDEX {pct(vn.get('change_pct'))}, VN30 {pct(vn30.get('change_pct'))}; breadth {adv}/{dec}, A/D {ad}."

    css = """@page{size:A4;margin:14mm 12mm}body{font-family:Arial,'Segoe UI',sans-serif;font-size:11px;line-height:1.45;color:#111}h1{font-size:23px;margin:0 0 6px}h2{font-size:16px;margin-top:20px;border-bottom:1px solid #ddd;padding-bottom:4px}h3{font-size:13px;margin:12px 0 4px}.meta{color:#555}.card{background:#f7f9fb;border:1px solid #e2e6ea;border-radius:8px;padding:10px 12px;margin:10px 0}.agent{page-break-inside:avoid;border:1px solid #e5e5e5;border-radius:7px;padding:9px;margin:8px 0}.tag{display:inline-block;background:#eef3ff;border:1px solid #ccd8ff;border-radius:10px;padding:1px 6px;margin-right:4px;font-size:9px}ul{margin:4px 0 8px 18px;padding:0}li{margin:3px 0}table{border-collapse:collapse;width:100%;font-size:9.2px}td,th{border:1px solid #ddd;padding:4px;text-align:left;vertical-align:top}th{background:#f1f3f5}.warn{color:#9a6700;font-weight:bold}.ok{color:#087f23;font-weight:bold}"""
    html_doc = f"<html><head><meta charset='utf-8'><style>{css}</style></head><body>"
    html_doc += f"<h1>InvestOS VN — Báo cáo thị trường & hành động ngày {date} (HF lens full PDF)</h1>"
    html_doc += f"<div class='meta'>Tạo lúc {now.isoformat(timespec='seconds')} | Source: validated outputs + data_live/derivatives_live.vn.json</div>"
    html_doc += f"<div class='card'><b>Kết luận nhanh:</b> {esc(thesis)} Derivatives active: {esc(active.get('symbol'))} basis {num(active.get('basis'))} điểm, OI Δ {num(active.get('oi_change'), 0)}, foreign net {num(active.get('foreign_net_qty'), 0)} hợp đồng.</div>"
    html_doc += "<h2>1. Số liệu chỉ số chính</h2>" + table(["Chỉ số", "Đóng cửa", "Thay đổi", "Khối lượng", "Nguồn"], [["VNINDEX", num(vn.get("close")), pct(vn.get("change_pct")), num(vn.get("volume_mn"), 1) + " triệu cp", "market index feed"], ["VN30", num(vn30.get("close")), pct(vn30.get("change_pct")), num(vn30.get("volume_mn"), 1) + " triệu cp", "market index feed"], ["HNXINDEX", num(hnx.get("close")), pct(hnx.get("change_pct")), num(hnx.get("volume_mn"), 1) + " triệu cp", "market index feed"], ["UPCOMINDEX", num(upcom.get("close")), pct(upcom.get("change_pct")), num(upcom.get("volume_mn"), 1) + " triệu cp", "market index feed"]])
    html_doc += "<h2>2. Nhận định thị trường</h2><ul>"
    html_doc += f"<li><b>Xu hướng ngắn hạn:</b> VNINDEX {pct(vn.get('change_pct'))}, VN30 {pct(vn30.get('change_pct'))}. Nếu breadth yếu hơn chỉ số, mua đuổi rủi ro cao.</li>"
    html_doc += f"<li><b>Độ rộng:</b> HOSE {adv} tăng / {dec} giảm, A/D {ad}, above MA20 {ma20}%.</li>"
    html_doc += sector_analysis(level4)
    html_doc += derivatives_analysis(drows) + "</ul>"
    html_doc += "<h2>3. Tín hiệu cổ phiếu đáng chú ý</h2>" + no_actionable_note + table(["Mã", "Trạng thái", "Score", "Vùng mua", "Điểm hủy", "Cơ sở"], sig_rows)
    html_doc += f"<h2>4. Danh mục hiện tại</h2><ul><li>NAV {bil(nav) if isinstance(nav, (int, float)) else esc(nav or 'missing field nav')}; cash {bil(cash) if isinstance(cash, (int, float)) else esc(cash or 'missing field cash_vnd')} ({num(cash_pct, 1) if cash_pct is not None else 'missing field cash_pct'}%).</li>"
    for risk in portfolio.get("risks") or portfolio.get("concentration_risks") or []:
        html_doc += f"<li>Rủi ro: {esc(risk)}</li>"
    html_doc += "<li>Hành động: ưu tiên risk budget/cash buffer trước khi mở vị thế mới.</li></ul>"

    agents = [
        ("Market Strategist", "Tích cực có điều kiện", f"VNINDEX {pct(vn.get('change_pct'))}, VN30 {pct(vn30.get('change_pct'))}; breadth {adv}/{dec}, A/D {ad}. Derivatives {active.get('symbol')} basis {num(active.get('basis'))}.", "Chỉ nâng exposure khi breadth và basis/OI cùng xác nhận."),
        ("Macro Strategist", "Trung tính-thận trọng", f"Sector foreign buy strongest: {net_buy.get('industry_name', 'missing sector')} {bil(net_buy.get('foreign_net_value_vnd'))}; sell strongest: {net_sell.get('industry_name', 'missing sector')} {bil(net_sell.get('foreign_net_value_vnd'))}.", "Không mở beta đại trà khi sector foreign flow còn phân hóa."),
        ("Rates / Fixed Income Analyst", "Giữ risk vừa phải", f"Money flow âm lớn nhất {neg_flow.get('industry_name', 'missing sector')} {bil(neg_flow.get('negative_money_flow_vnd'))}.", "Nhóm đòn bẩy chỉ được xem lại khi money flow âm co rõ."),
        ("Fundamental Analyst", "Chọn lọc chất lượng", f"Signal scan có {len(signal_rows_src)} mã; setup đạt watch/idea/actionable: {len([s for s in signal_rows_src if s.get('status') in {'watch','idea','actionable'}])}.", "Cơ bản chỉ là filter nếu technical setup đủ điều kiện."),
        ("Banking Sector Analyst", "Dẫn dắt cần xác nhận", f"Money flow dương lớn nhất {pos_flow.get('industry_name', 'missing sector')} {bil(pos_flow.get('positive_money_flow_vnd'))}; VN30 {pct(vn30.get('change_pct'))}.", "Overweight bank khi VN30 outperform và breadth cải thiện."),
        ("Real Estate Sector Analyst", "Tránh mua đuổi", f"Foreign sell strongest {net_sell.get('industry_name', 'missing sector')} {bil(net_sell.get('foreign_net_value_vnd'))}.", "Không chase nhóm bị ngoại bán ròng mạnh."),
        ("Equity Technical Analyst", "Chờ setup sạch", f"Picked signals: {len(picked)}; top status {picked[0].get('status') if picked else 'none'}, score {picked[0].get('score') if picked else 'none'}.", "Không mở lệnh nếu status vẫn avoid/watch yếu."),
        ("Quant Researcher", "Model risk filter", f"Universe size {signals.get('universe_size', len(signal_rows_src)) if isinstance(signals, dict) else len(signal_rows_src)}; no-actionable note active={bool(no_actionable_note)}.", "Không ép top avoid thành buy list."),
        ("Derivatives Strategist", "Basis/OI gate", f"{active.get('symbol', 'missing symbol')} basis {num(active.get('basis'))} ({pct(active.get('basis_pct'), signed=False)}), OI {num(active.get('open_interest'), 0)}, OI Δ {num(active.get('oi_change'), 0)}, foreign net {num(active.get('foreign_net_qty'), 0)} hợp đồng / {bil(active.get('foreign_net_value'))}.", "Bullish hơn khi basis >0 và OI Δ chuyển dương; bearish khi basis âm hoặc foreign net tiếp tục âm."),
        ("Risk Manager", "Không mở rủi ro thiếu xác nhận", f"NAV {bil(nav) if isinstance(nav, (int, float)) else nav}; cash {bil(cash) if isinstance(cash, (int, float)) else cash}; derivatives OI Δ {num(active.get('oi_change'), 0)}.", "Không tăng gross exposure nếu cash buffer thấp hoặc derivatives không xác nhận."),
        ("Portfolio Advisor", "Tái cân bằng trước", f"Cash pct {num(cash_pct, 1) if cash_pct is not None else 'missing field'}%; risks count {len(portfolio.get('risks') or [])}.", "Tạo cash buffer trước, sau đó mới xét watchlist."),
        ("Investment Data Designer", "Data quality gate", f"Report dùng breadth {adv}/{dec}, sector flow {pos_flow.get('industry_name', 'missing sector')} money+ {bil(pos_flow.get('positive_money_flow_vnd'))}, derivatives {active.get('symbol')} basis {num(active.get('basis'))}.", "Nếu thiếu field, fail/ghi missing field; không thay bằng mô tả pipeline."),
    ]
    html_doc += "<h2>5. Native multi-agent lens — phân tích chi tiết</h2>"
    for name, tag, agent_thesis, trigger in agents:
        html_doc += f"<div class='agent'><h3>{esc(name)}</h3><span class='tag'>{esc(tag)}</span><ul><li><b>Luận điểm:</b> {esc(agent_thesis)}</li><li><b>Trigger hành động:</b> {esc(trigger)}</li></ul></div>"
    html_doc += "<h2>6. Sector flow / foreign flow</h2>" + table(["Ngành", "%", "GTGD", "NN ròng", "Money +", "Money -", "P/E", "P/B"], sector_rows)
    html_doc += "<h2>7. VN30 derivatives / basis / OI</h2>" + table(["Ngày", "Symbol", "VND code", "F close", "VN30", "Basis", "Basis %", "Vol", "Value", "OI", "OI Δ", "Foreign net qty", "Foreign net value", "Prop net value"], derivative_rows)
    html_doc += "<h2>8. Kết luận giao dịch phiên kế tiếp</h2><ul><li><b>Base case:</b> hồi kỹ thuật có chọn lọc; ưu tiên mã mạnh hơn thị trường và có thanh khoản thật.</li><li><b>Bull trigger:</b> breadth cải thiện, VN30 không yếu hơn, basis/OI tích cực.</li><li><b>Bear trigger:</b> VN30 đảo chiều, basis âm, OI/foreign flow xấu, top signal thủng invalidation.</li><li><b>Portfolio action:</b> mỗi lệnh mới có stop, size theo ATR, không vượt risk budget.</li></ul>"
    html_doc += "<p><b>Disclaimer:</b> Thông tin hỗ trợ quyết định, không phải khuyến nghị đầu tư cá nhân hóa bắt buộc mua/bán.</p></body></html>"
    return html_doc


def sanity_check(text: str) -> list[str]:
    issues = [f"banned_pattern:{pat}" for pat in BANNED_PATTERNS if pat in text]
    required = ["Derivatives Strategist", "VN30 derivatives", "basis", "OI Δ", "Foreign net"]
    for token in required:
        if token not in text:
            issues.append(f"missing_required_token:{token}")
    if not re.search(r"<table>", text):
        issues.append("missing_tables")
    return issues


def chrome_path() -> Path | None:
    candidates = [
        Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
        Path(r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"),
        Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
        Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
    ]
    return next((path for path in candidates if path.exists()), None)


def main() -> int:
    ap = argparse.ArgumentParser(description="Build production HF lens full HTML/PDF report with derivatives wired in")
    ap.add_argument("--out-dir", default=str(OUT))
    ap.add_argument("--basename", default="invest-os-vn-hf-lens-full-derivatives")
    ap.add_argument("--no-pdf", action="store_true")
    args = ap.parse_args()
    now = datetime.now().astimezone()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    html_path = out_dir / f"{args.basename}-{now:%Y-%m-%d}.html"
    pdf_path = out_dir / f"{args.basename}-{now:%Y-%m-%d}.pdf"
    html_doc = build_html()
    issues = sanity_check(html_doc)
    if issues:
        raise SystemExit("FULL_REPORT_SANITY_FAILED: " + ",".join(issues))
    html_path.write_text(html_doc, encoding="utf-8")
    print(f"FULL_REPORT_HTML_READY {html_path} size={html_path.stat().st_size}")
    if not args.no_pdf:
        chrome = chrome_path()
        if not chrome:
            raise SystemExit("PDF_RENDERER_NOT_FOUND: install Chrome/Edge or pass --no-pdf")
        subprocess.run([str(chrome), "--headless", "--disable-gpu", "--no-sandbox", f"--print-to-pdf={pdf_path}", html_path.resolve().as_uri()], check=True)
        if not pdf_path.exists() or pdf_path.stat().st_size <= 0:
            raise SystemExit("PDF_RENDER_FAILED")
        print(f"FULL_REPORT_PDF_READY {pdf_path} size={pdf_path.stat().st_size}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
