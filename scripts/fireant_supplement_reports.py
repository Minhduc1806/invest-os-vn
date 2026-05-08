#!/usr/bin/env python
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
LIVE = ROOT / "data_live"
OUT = ROOT / "outputs"


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def save_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def pct(value: Any) -> str:
    try:
        number = float(value)
        return f"{number * 100:.2f}%" if abs(number) <= 1 else f"{number:.2f}%"
    except Exception:
        return "N/A"


def money_bil(value: Any) -> str:
    try:
        return f"{float(value) / 1_000_000_000:,.1f} tỷ"
    except Exception:
        return "N/A"


def table(headers: list[str], rows: list[list[Any]]) -> str:
    out = ["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"]
    out += ["| " + " | ".join(str(v) for v in row) + " |" for row in rows]
    return "\n".join(out)


def top_by(rows: list[dict[str, Any]], key: str, reverse: bool = True, n: int = 12) -> list[dict[str, Any]]:
    return sorted([row for row in rows if row.get(key) is not None], key=lambda row: row.get(key) or 0, reverse=reverse)[:n]


def build_summary(fire: dict[str, Any]) -> dict[str, Any]:
    industries = fire.get("industry_flows", [])
    level4 = [row for row in industries if row.get("level") == 4]
    stats = fire.get("ticker_trading_statistics", [])
    fins = fire.get("financial_ratios", [])
    prices = {row.get("symbol"): row for row in fire.get("ticker_realtime_prices", []) if row.get("symbol")}
    flows = {row.get("symbol"): row for row in fire.get("ticker_flows", []) if row.get("symbol")}

    stat_by_symbol = {row.get("symbol"): row for row in stats if row.get("symbol")}
    fin_by_symbol = {row.get("symbol"): row for row in fins if row.get("symbol")}
    enriched = []
    for symbol, stat_row in stat_by_symbol.items():
        row = {"symbol": symbol, **stat_row}
        if symbol in fin_by_symbol:
            row.update({f"fin_{k}": v for k, v in fin_by_symbol[symbol].items() if k not in {"symbol", "row_index", "symbol_mapping_source"}})
        if symbol in prices:
            row.update({f"px_{k}": v for k, v in prices[symbol].items() if k != "symbol"})
        if symbol in flows:
            row.update({f"flow_{k}": v for k, v in flows[symbol].items() if k != "symbol"})
        enriched.append(row)

    sector_rows = []
    for row in top_by(level4, "value_vnd", True, 15):
        change_pct = None
        if row.get("index_close") is not None and row.get("index_prev"):
            change_pct = (row["index_close"] / row["index_prev"] - 1) * 100
        sector_rows.append([
            row.get("industry_name"),
            f"{change_pct:.2f}%" if change_pct is not None else "N/A",
            money_bil(row.get("value_vnd")),
            money_bil(row.get("foreign_net_value_vnd")),
            money_bil(row.get("positive_money_flow_vnd")),
            money_bil(row.get("negative_money_flow_vnd")),
            row.get("pe"),
            row.get("pb"),
            money_bil(row.get("market_cap_vnd")),
        ])

    foreign_rows = [[row.get("industry_name"), money_bil(row.get("foreign_net_value_vnd")), money_bil(row.get("foreign_buy_value_vnd")), money_bil(row.get("foreign_sell_value_vnd"))] for row in top_by(level4, "foreign_net_value_vnd", True, 10)]
    foreign_sell_rows = [[row.get("industry_name"), money_bil(row.get("foreign_net_value_vnd")), money_bil(row.get("foreign_buy_value_vnd")), money_bil(row.get("foreign_sell_value_vnd"))] for row in top_by(level4, "foreign_net_value_vnd", False, 10)]
    momentum_rows = [[row.get("symbol"), pct(row.get("price_change_1w")), pct(row.get("price_change_1m")), pct(row.get("price_change_3m")), row.get("mfi_14d"), row.get("beta"), row.get("avg_volume_20d")] for row in top_by(enriched, "price_change_1m", True, 20)]
    valuation_rows = [[row.get("symbol"), row.get("fin_eps"), pct(row.get("fin_roe")), pct(row.get("fin_roa")), pct(row.get("fin_profit_growth_ttm")), row.get("fin_debt_over_equity"), pct(row.get("fin_dividend_yield"))] for row in top_by([row for row in enriched if row.get("fin_roe") is not None], "fin_roe", True, 20)]

    return {
        "as_of": datetime.now().astimezone().isoformat(timespec="seconds"),
        "source": fire.get("source"),
        "fireant_timestamp": fire.get("timestamp"),
        "quality_score": fire.get("quality_score"),
        "counts": {
            "industry_flows": len(industries),
            "ticker_trading_statistics": len(stats),
            "financial_ratios": len(fins),
            "enriched_symbols": len(enriched),
        },
        "mapping_policy": "ticker_trading_statistics/financial_ratios mapped by GetSymbols_order when server order length allows; otherwise row_index_only",
        "sector_top_by_value": sector_rows,
        "foreign_net_buy_sectors": foreign_rows,
        "foreign_net_sell_sectors": foreign_sell_rows,
        "momentum_top_1m": momentum_rows,
        "quality_factor_top_roe": valuation_rows,
    }


def markdown(summary: dict[str, Any]) -> str:
    md = "# FireAnt Supplement — lớp dữ liệu bổ sung cho báo cáo\n\n"
    md += f"As of: {summary['as_of']}\n\nSource: {summary['source']} @ {summary['fireant_timestamp']}\n\n"
    counts = summary["counts"]
    md += f"Counts: sector/industry {counts['industry_flows']}, trading stats {counts['ticker_trading_statistics']}, financial ratios {counts['financial_ratios']}, enriched symbols {counts['enriched_symbols']}.\n\n"
    md += "## Sector agents — bảng số cụ thể\n" + table(["Ngành", "%", "GTGD", "NN ròng", "Money +", "Money -", "P/E", "P/B", "Market cap"], summary["sector_top_by_value"]) + "\n\n"
    md += "## Top ngành NN mua ròng\n" + table(["Ngành", "NN ròng", "NN mua", "NN bán"], summary["foreign_net_buy_sectors"]) + "\n\n"
    md += "## Top ngành NN bán ròng\n" + table(["Ngành", "NN ròng", "NN mua", "NN bán"], summary["foreign_net_sell_sectors"]) + "\n\n"
    md += "## Ticker momentum — GetTradingStatistics mapped symbol\n" + table(["Ticker", "1W", "1M", "3M", "MFI14", "Beta", "AvgVol20D"], summary["momentum_top_1m"]) + "\n\n"
    md += "## Ticker quality/value — GetFinancialInfos mapped symbol\n" + table(["Ticker", "EPS", "ROE", "ROA", "Profit growth TTM", "D/E", "Dividend yield"], summary["quality_factor_top_roe"]) + "\n\n"
    md += "Ghi chú: không fake symbol. Symbol lấy theo `GetSymbols_order`; vẫn giữ `row_index` + `symbol_mapping_source` để audit.\n"
    return md


def main() -> int:
    fire = load(LIVE / "fireant_foreign_flow.vn.json")
    if not fire:
        raise SystemExit("missing data_live/fireant_foreign_flow.vn.json")
    summary = build_summary(fire)
    save_json(OUT / "fireant_supplement_summary.json", summary)
    (OUT / "fireant_supplement_summary.md").write_text(markdown(summary), encoding="utf-8")
    print("OK fireant supplement")
    print(OUT / "fireant_supplement_summary.json")
    print(OUT / "fireant_supplement_summary.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
