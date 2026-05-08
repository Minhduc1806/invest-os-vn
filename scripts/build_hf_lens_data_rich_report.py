#!/usr/bin/env python
from __future__ import annotations

import argparse
import html
import json
import re
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


def pct(value: Any) -> str:
    try:
        number = float(value)
        return f"{number:.2f}%"
    except Exception:
        return "N/A"


def num(value: Any, digits: int = 2) -> str:
    try:
        return f"{float(value):,.{digits}f}"
    except Exception:
        return "N/A"


def bil(value: Any) -> str:
    try:
        return f"{float(value) / 1_000_000_000:,.1f} tỷ"
    except Exception:
        return "N/A"


def table(headers: list[str], rows: list[list[Any]]) -> str:
    body = "<table><tr>" + "".join(f"<th>{esc(h)}</th>" for h in headers) + "</tr>"
    for row in rows:
        body += "<tr>" + "".join(f"<td>{esc(cell)}</td>" for cell in row) + "</tr>"
    return body + "</table>"


def top(rows: list[dict[str, Any]], key: str, n: int = 10, reverse: bool = True) -> list[dict[str, Any]]:
    return sorted([row for row in rows if row.get(key) is not None], key=lambda row: row.get(key) or 0, reverse=reverse)[:n]


def build_html() -> str:
    now = datetime.now().astimezone()
    eod = load(OUT / "eod_market_brief.json")
    signals = load(OUT / "stock_signal_scan_investable.json")
    portfolio = load(OUT / "portfolio_daily.json")
    company = load(OUT / "company_deep_dive.json")
    fireant = load(LIVE / "fireant_foreign_flow.vn.json")
    derivatives = load(LIVE / "derivatives_live.vn.json")
    global_macro = load(LIVE / "global_macro_live.json")

    signal_rows_src = signals.get("signals") or []
    selected_signals = [s for s in signal_rows_src if s.get("status") in {"actionable", "watch", "idea"}]
    if not selected_signals:
        selected_signals = sorted(signal_rows_src, key=lambda s: s.get("score") or 0, reverse=True)[:10]
    signal_rows = [[s.get("ticker"), s.get("status"), s.get("score"), s.get("entry_zone"), s.get("invalidation"), s.get("confidence")] for s in selected_signals[:15]]

    industries = fireant.get("industry_flows") or []
    level4 = [row for row in industries if row.get("level") == 4]
    sector_rows = []
    for row in top(level4, "value_vnd", 12):
        change_pct = None
        if row.get("index_close") is not None and row.get("index_prev"):
            change_pct = (row["index_close"] / row["index_prev"] - 1) * 100
        sector_rows.append([
            row.get("industry_name"),
            pct(change_pct),
            bil(row.get("value_vnd")),
            bil(row.get("foreign_net_value_vnd")),
            bil(row.get("positive_money_flow_vnd")),
            bil(row.get("negative_money_flow_vnd")),
            row.get("pe"),
            row.get("pb"),
        ])

    derivative_rows = []
    for row in (derivatives.get("rows") or [])[:12]:
        derivative_rows.append([
            row.get("date"), row.get("symbol"), row.get("vndirect_code"), num(row.get("future_close")),
            num(row.get("vn30_close")), num(row.get("basis")), pct(row.get("basis_pct")),
            row.get("open_interest"), row.get("oi_change"), row.get("fireant_volume"), bil(row.get("fireant_value")),
            row.get("foreign_net_qty"), bil(row.get("foreign_net_value")), bil(row.get("prop_net_value")),
        ])

    gm = global_macro.get("indicators") or {}
    macro_rows = [[name, item.get("value"), item.get("date"), item.get("trend_approx"), item.get("source")] for name, item in gm.items()]
    portfolio_rows = [[p.get("ticker"), p.get("weight_pct"), bil(p.get("value_vnd")), pct(p.get("pnl_pct")), p.get("technical_status")] for p in portfolio.get("positions", [])]

    css = """
    @page{size:A4;margin:12mm 10mm}body{font-family:Arial,'Segoe UI',sans-serif;font-size:10.5px;line-height:1.45;color:#111}
    h1{font-size:22px;margin:0 0 6px}h2{font-size:15px;margin-top:16px;border-bottom:1px solid #ddd;padding-bottom:4px}
    .meta{color:#555}.card{background:#f7f9fb;border:1px solid #e2e6ea;border-radius:8px;padding:10px 12px;margin:10px 0}
    table{border-collapse:collapse;width:100%;font-size:9px;margin:6px 0}td,th{border:1px solid #ddd;padding:4px;text-align:left;vertical-align:top}th{background:#f1f3f5}
    """
    thesis = eod.get("market_thesis") or "missing field: eod_market_brief.market_thesis"
    html_doc = f"<html><head><meta charset='utf-8'><style>{css}</style></head><body>"
    html_doc += f"<h1>InvestOS VN — Báo cáo hành động HF lens data-rich</h1><div class='meta'>Tạo lúc {now.isoformat(timespec='seconds')}</div>"
    html_doc += f"<div class='card'><b>Luận điểm CIO:</b> {esc(thesis)}</div>"
    html_doc += "<h2>1. Global macro</h2>" + table(["Chỉ báo", "Giá trị", "Ngày", "Xu hướng", "Nguồn"], macro_rows)
    html_doc += "<h2>2. Market regime</h2>" + table(["Regime", "Risk appetite", "Confidence"], [[eod.get("market_regime", {}).get("regime"), eod.get("market_regime", {}).get("risk_appetite"), eod.get("confidence")]])
    html_doc += "<h2>3. Sector/foreign flow FireAnt</h2>" + table(["Ngành", "%", "GTGD", "NN ròng", "Money +", "Money -", "P/E", "P/B"], sector_rows)
    html_doc += "<h2>4. Stock signals</h2>" + table(["Ticker", "Status", "Score", "Entry", "Invalidation", "Confidence"], signal_rows)
    html_doc += "<h2>5. Portfolio</h2>" + table(["Ticker", "Weight %", "Value", "P&L %", "Technical"], portfolio_rows)
    html_doc += "<h2>6. Derivatives</h2>" + table(["Date", "Symbol", "VND code", "F close", "VN30", "Basis", "Basis %", "OI", "OI Δ", "Volume", "Value", "Foreign net qty", "Foreign net value", "Prop net value"], derivative_rows)
    html_doc += "<h2>7. Company deep dive</h2>" + table(["Ticker", "Business", "Financial quality", "Valuation", "Confidence"], [[company.get("ticker"), company.get("business"), company.get("financial_quality"), company.get("valuation"), company.get("confidence")]])
    html_doc += "<p><b>Disclaimer:</b> Thông tin hỗ trợ quyết định, không phải khuyến nghị đầu tư cá nhân hóa bắt buộc mua/bán.</p>"
    html_doc += "</body></html>"
    return html_doc


def sanity_check(text: str) -> list[str]:
    issues = [f"banned_pattern:{pat}" for pat in BANNED_PATTERNS if pat in text]
    if not re.search(r"<table>", text):
        issues.append("missing_tables")
    return issues


def main() -> int:
    ap = argparse.ArgumentParser(description="Build clean UTF-8 InvestOS VN HF lens report HTML")
    ap.add_argument("--out", default=str(OUT / "invest-os-vn-hf-lens-data-rich-clean.html"))
    args = ap.parse_args()
    html_doc = build_html()
    issues = sanity_check(html_doc)
    if issues:
        raise SystemExit("REPORT_SANITY_FAILED: " + ",".join(issues))
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html_doc, encoding="utf-8")
    print(f"REPORT_HTML_READY {out} size={out.stat().st_size}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
