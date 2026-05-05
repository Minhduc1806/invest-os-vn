#!/usr/bin/env python
"""
Invest OS VN production pipeline runner. Live is default; mock requires explicit override.

Usage:
  python scripts/run_pipeline.py --config orchestrator.yaml --pipeline eod_market_brief --live
  python scripts/run_pipeline.py --config orchestrator.yaml --pipeline stock_signal_scan --live --universe investable
  python scripts/run_pipeline.py --config orchestrator.yaml --pipeline portfolio_daily_advice --live
  python scripts/run_pipeline.py --config orchestrator.yaml --pipeline company_deep_dive --ticker FPT --mock
"""
from __future__ import annotations

import argparse
import json
import math
import statistics
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import yaml

ROOT = Path(__file__).resolve().parents[1]


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def save_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def pct(x: float) -> str:
    return f"{x:.2f}%"


def money_vnd(x: float) -> str:
    if abs(x) >= 1_000_000_000:
        return f"{x/1_000_000_000:.2f} tỷ VND"
    if abs(x) >= 1_000_000:
        return f"{x/1_000_000:.2f} triệu VND"
    return f"{x:,.0f} VND"


def price_fmt(x: float) -> str:
    # vnstock may return adjusted prices in thousand VND; keep decimals when price < 1000.
    return f"{x:,.2f}" if abs(x) < 1000 else f"{x:,.0f}"


def round_price(x: float) -> float:
    return round(x, 2) if abs(x) < 1000 else round(x, -2)


def md_table(headers: List[str], rows: List[List[Any]]) -> str:
    out = ["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"]
    for r in rows:
        out.append("| " + " | ".join(str(x) for x in r) + " |")
    return "\n".join(out)


def render_template(template: str, values: Dict[str, Any]) -> str:
    text = template
    for k, v in values.items():
        text = text.replace("{{" + k + "}}", str(v))
    return text


def audit(log_path: Path, event: Dict[str, Any]) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    event = {"ts": now_iso(), **event}
    with log_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")


def load_config(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def resolve_config_path(config_arg: str) -> Path:
    p = Path(config_arg)
    if p.exists():
        return p.resolve()
    p2 = ROOT / config_arg
    if p2.exists():
        return p2.resolve()
    raise FileNotFoundError(config_arg)


def live_ohlcv_path(universe: str) -> str:
    if universe == "hose_all":
        return "data_live/fdata_hose_all_bars.json"
    if universe == "investable":
        return "data_live/fdata_investable_bars.json"
    raise ValueError(f"Unknown universe: {universe}. Use hose_all or investable")

def live_input_path(name: str, universe: str) -> str:
    live_overrides = {
        "market_snapshot": "data_live/market_snapshot.vn.json",
        "ohlcv": live_ohlcv_path(universe),
        "fundamentals": "data_live/fundamentals_sample.vn.json",
        "portfolio": "data_live/portfolio_real.json",
        "news": "mock_data/news_sample.vn.json",
        "macro_rates": "mock_data/macro_rates_sample.vn.json",
    }
    return live_overrides[name]

def refresh_live_ohlcv_if_needed(config: Dict[str, Any], pipeline_name: str, universe: str) -> None:
    """Regenerate derived live OHLCV before quality gate when cache age exceeds policy."""
    path = ROOT / live_ohlcv_path(universe)
    if not path.exists():
        return
    data = load_json(path)
    as_of = _parse_as_of(data.get("as_of"))
    if not as_of:
        return
    stale = config.get("quality_gate", {}).get("block_if_stale_minutes", {})
    key = "intraday_market" if not pipeline_name.startswith("eod") else "eod_market"
    max_min = stale.get(key)
    if not max_min:
        return
    age_min = (datetime.now().astimezone() - as_of).total_seconds() / 60
    if age_min <= max_min:
        return
    script = "fdata_hose_universe.py" if universe == "hose_all" else "fdata_universe_filter.py"
    cmd = [sys.executable, str(ROOT / "scripts" / script)]
    if universe == "hose_all":
        cmd += ["--timeframe", "EOD"]
    subprocess.run(cmd, cwd=ROOT, check=True)

def refresh_live_market_snapshot_if_needed(config: Dict[str, Any], pipeline_name: str) -> None:
    """Regenerate live market snapshot before quality gate when cache age exceeds policy."""
    path = ROOT / "data_live" / "market_snapshot.vn.json"
    if not path.exists():
        return
    data = load_json(path)
    as_of = _parse_as_of(data.get("as_of"))
    if not as_of:
        return
    stale = config.get("quality_gate", {}).get("block_if_stale_minutes", {})
    key = "intraday_market" if not pipeline_name.startswith("eod") else "eod_market"
    max_min = stale.get(key)
    if not max_min:
        return
    age_min = (datetime.now().astimezone() - as_of).total_seconds() / 60
    if age_min <= max_min:
        return
    subprocess.run([sys.executable, str(ROOT / "scripts" / "data_adapters.py"), "--market"], cwd=ROOT, check=True)

def load_inputs(config: Dict[str, Any], pipeline: Dict[str, Any], live: bool = True, universe: str = "hose_all", pipeline_name: str = "") -> Dict[str, Any]:
    if live and "market_snapshot" in pipeline.get("inputs", []):
        refresh_live_market_snapshot_if_needed(config, pipeline_name)
    if live and "ohlcv" in pipeline.get("inputs", []):
        refresh_live_ohlcv_if_needed(config, pipeline_name, universe)
    inputs = {}
    mapping = config.get("inputs", {})
    for name in pipeline.get("inputs", []):
        rel = live_input_path(name, universe) if live else None
        path = ROOT / rel if rel else ROOT / mapping[name]
        if live and rel and not path.exists():
            hint = "python scripts/fdata_hose_universe.py --timeframe EOD" if universe == "hose_all" else "python scripts/fdata_universe_filter.py"
            raise FileNotFoundError(f"Live data missing: {path}. Run: {hint}")
        inputs[name] = load_json(path)
    return inputs


def _parse_as_of(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        text = str(value).replace("Z", "+00:00")
        dt = datetime.fromisoformat(text)
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except Exception:
        return None

def quality_gate(config: Dict[str, Any], inputs: Dict[str, Any], pipeline_name: str = "") -> List[str]:
    warnings: List[str] = []
    qcfg = config.get("quality_gate", {})
    stale = qcfg.get("block_if_stale_minutes", {})
    now = datetime.now().astimezone()
    for name, data in inputs.items():
        if not isinstance(data, dict):
            warnings.append(f"{name}: invalid payload type {type(data).__name__}")
            continue
        if qcfg.get("require_as_of", True) and "as_of" not in data:
            warnings.append(f"{name}: missing as_of")
        if qcfg.get("require_sources", True) and "source" not in data:
            warnings.append(f"{name}: missing source")
        score = data.get("quality_score", 1)
        if score is not None and score < 0.8:
            warnings.append(f"{name}: low quality_score {score}")
        as_of = _parse_as_of(data.get("as_of"))
        if as_of:
            key = "intraday_market" if name in {"market_snapshot", "ohlcv"} and not pipeline_name.startswith("eod") else "eod_market" if name in {"market_snapshot", "ohlcv"} else name
            max_min = stale.get(key)
            if max_min and (now - as_of).total_seconds() / 60 > max_min:
                warnings.append(f"{name}: stale as_of {data.get('as_of')} > {max_min}m")
        if name == "ohlcv" and not data.get("bars"):
            warnings.append("ohlcv: empty bars")
        if name == "market_snapshot":
            if not data.get("indices"):
                warnings.append("market_snapshot: empty indices")
            br = data.get("breadth", {})
            if br.get("advancers") is None or br.get("decliners") is None:
                warnings.append("market_snapshot: breadth incomplete")
    return warnings

def assert_quality_or_raise(config: Dict[str, Any], warnings: List[str], allow_warnings: bool) -> None:
    if warnings and not allow_warnings:
        raise RuntimeError("QUALITY_GATE_BLOCKED: " + " | ".join(warnings))

def derive_market_regime(market: Dict[str, Any], macro: Dict[str, Any] | None = None) -> Dict[str, Any]:
    vn = next(x for x in market["indices"] if x["symbol"] == "VNINDEX")
    breadth = market["breadth"]
    adv_dec = breadth["advancers"] / max(1, breadth["decliners"])
    sector_pos = sum(1 for s in market["sectors"] if s["change_pct"] > 0) / len(market["sectors"])
    liquidity = vn["value_bil_vnd"]
    score = 0.0
    score += 0.35 if vn["change_pct"] > 0.5 else 0.1 if vn["change_pct"] > 0 else -0.2
    score += 0.25 if adv_dec > 1.2 else -0.15
    score += 0.20 if sector_pos >= 0.6 else -0.1
    score += 0.10 if liquidity >= 15000 else -0.05
    if macro and macro.get("liquidity_assessment") == "neutral":
        score += 0.05
    regime = "risk_on" if score >= 0.55 else "neutral" if score >= 0.15 else "risk_off"
    risk_appetite = max(0, min(100, round(50 + score * 50, 1)))
    top_sectors = sorted(market["sectors"], key=lambda s: (s["relative_strength_20d"], s["change_pct"], s["value_bil_vnd"]), reverse=True)
    return {
        "as_of": market["as_of"],
        "regime": regime,
        "risk_appetite": risk_appetite,
        "evidence": [
            f"VNINDEX {pct(vn['change_pct'])}, value {vn['value_bil_vnd']} tỷ VND",
            f"Breadth adv/dec {adv_dec:.2f} ({breadth['advancers']}/{breadth['decliners']})",
            f"Sector positive ratio {sector_pos:.0%}",
            f"Foreign net flow {market['foreign_flow']['net_value_bil_vnd']} tỷ VND",
        ],
        "top_sectors_by_data": top_sectors[:3],
        "source": market["source"],
        "confidence": 0.74,
    }


def run_eod_market_brief(inputs: Dict[str, Any]) -> Dict[str, Any]:
    market, news, macro = inputs["market_snapshot"], inputs["news"], inputs["macro_rates"]
    regime = derive_market_regime(market, macro)
    news_items = news["items"][:5]
    thesis = (
        f"Thị trường nghiêng {regime['regime']} với risk appetite {regime['risk_appetite']}/100. "
        f"Bằng chứng chính: {regime['evidence'][0]}; {regime['evidence'][1]}."
    )
    sector_rows = [[s["name"], pct(s["change_pct"]), s["value_bil_vnd"], s["relative_strength_20d"]] for s in regime["top_sectors_by_data"]]
    return {
        "run_id": f"eod_market_brief_{now_iso()}",
        "as_of": market["as_of"],
        "pipeline": "eod_market_brief",
        "market_regime": regime,
        "market_thesis": thesis,
        "sector_table": sector_rows,
        "news_brief": [{"title": n["title"], "tickers": n["tickers"], "url": n["url"], "summary": n["summary"]} for n in news_items],
        "next_session_conditions": [
            "Ưu tiên giải ngân nếu VNINDEX giữ trên tham chiếu và breadth tiếp tục > 1.2.",
            "Giảm tốc nếu thanh khoản tăng nhưng breadth xấu đi hoặc basis phái sinh âm rộng.",
            "Không gọi nhóm dẫn dắt nếu sector ranking không duy trì qua ít nhất 2 phiên.",
        ],
        "sources": [market["source"], news["source"], macro["source"]],
        "confidence": 0.74,
        "disclaimer": "Thông tin hỗ trợ quyết định, không phải khuyến nghị đầu tư cá nhân hóa bắt buộc mua/bán.",
    }


def classify_signal(bar: Dict[str, Any], regime: Dict[str, Any]) -> Dict[str, Any]:
    trend = bar["close"] > bar["ma20"] > bar["ma50"]
    volume = bar["vol_ratio_20d"] >= 1.15
    rs = bar["rs_20d"] >= 0.5
    rsi_ok = 45 <= bar["rsi14"] <= 70
    score = sum([trend, volume, rs, rsi_ok]) / 4
    if regime["regime"] == "risk_off":
        score -= 0.2
    status = "actionable" if score >= 0.85 else "watch" if score >= 0.60 else "idea" if score >= 0.40 else "avoid"
    entry_low = round_price(bar["close"] * 0.98)
    entry_high = round_price(bar["close"] * 1.01)
    stop = round_price(bar["close"] * (1 - max(bar["atr14_pct"] * 1.5 / 100, 0.04)))
    return {
        "ticker": bar["ticker"],
        "status": status,
        "score": round(score, 2),
        "entry_zone": f"{price_fmt(entry_low)}-{price_fmt(entry_high)}",
        "invalidation": f"Đóng cửa dưới {price_fmt(stop)} hoặc volume breakout thất bại.",
        "risk": f"ATR14 {bar['atr14_pct']}%, RSI14 {bar['rsi14']}, vol_ratio_20d {bar['vol_ratio_20d']}",
        "confidence": round(0.5 + score * 0.35, 2),
        "evidence": [
            f"Close {bar['close']:,} vs MA20 {bar['ma20']:,} vs MA50 {bar['ma50']:,}",
            f"RS20D {bar['rs_20d']}, volume ratio {bar['vol_ratio_20d']}",
        ],
    }


def run_stock_signal_scan(inputs: Dict[str, Any]) -> Dict[str, Any]:
    market, ohlcv = inputs["market_snapshot"], inputs["ohlcv"]
    regime = derive_market_regime(market)
    source_bars = ohlcv.get("bars", [])
    signals = [classify_signal(b, regime) for b in source_bars]
    signals.sort(key=lambda x: (x["status"] != "actionable", -x["score"]))
    universe_name = "investable" if ohlcv.get("source") == "fdata_universe_filter" else "hose_all" if ohlcv.get("source") == "fdata_hose_all_listed" else "unknown"
    return {
        "run_id": f"stock_signal_scan_{now_iso()}",
        "as_of": ohlcv["as_of"],
        "pipeline": "stock_signal_scan",
        "universe_mode": universe_name,
        "market_regime": regime,
        "signals": signals,
        "summary": {
            "actionable": [s["ticker"] for s in signals if s["status"] == "actionable"],
            "watch": [s["ticker"] for s in signals if s["status"] == "watch"],
            "avoid": [s["ticker"] for s in signals if s["status"] == "avoid"],
        },
        "universe_size": len(source_bars),
        "universe_filter": ohlcv.get("params", {}),
        "excluded_count": ohlcv.get("excluded_count"),
        "sources": [market["source"], ohlcv["source"]],
        "confidence": 0.72,
        "disclaimer": "Tín hiệu là kịch bản có điều kiện, không phải lệnh mua/bán.",
    }


def run_portfolio_daily_advice(inputs: Dict[str, Any]) -> Dict[str, Any]:
    portfolio, market, news, ohlcv = inputs["portfolio"], inputs["market_snapshot"], inputs["news"], inputs["ohlcv"]
    bars = {b["ticker"]: b for b in ohlcv["bars"]}
    positions = []
    equity_value = 0
    total_cost = 0
    for p in portfolio["positions"]:
        value = p["quantity"] * p["last_price"]
        cost = p["quantity"] * p["avg_cost"]
        equity_value += value
        total_cost += cost
        positions.append({
            "ticker": p["ticker"],
            "sector": p["sector"],
            "value_vnd": value,
            "pnl_vnd": value - cost,
            "pnl_pct": round((value / cost - 1) * 100, 2),
            "technical_status": classify_signal(bars[p["ticker"]], derive_market_regime(market))["status"] if p["ticker"] in bars else "unknown",
        })
    nav = equity_value + portfolio["cash_vnd"] - portfolio.get("margin_debt_vnd", 0)
    for p in positions:
        p["weight_pct"] = round(p["value_vnd"] / nav * 100, 2)
    sector_weights: Dict[str, float] = {}
    for p in positions:
        sector_weights[p["sector"]] = sector_weights.get(p["sector"], 0) + p["weight_pct"]
    risks = []
    if positions:
        max_pos = max(positions, key=lambda p: p["weight_pct"])
        if max_pos["weight_pct"] > portfolio["constraints"]["max_position_pct"] * 100:
            risks.append(f"{max_pos['ticker']} vượt max position {portfolio['constraints']['max_position_pct']:.0%} NAV.")
    cash_pct = portfolio["cash_vnd"] / nav * 100 if nav else 0
    if positions and cash_pct < portfolio["constraints"]["min_cash_pct"] * 100:
        risks.append("Tiền mặt dưới ngưỡng tối thiểu.")
    if not positions:
        risks.append("Danh mục chưa có vị thế; trạng thái cash-only/no holdings.")
    ticker_news = {t: [] for t in [p["ticker"] for p in positions]}
    for item in news["items"]:
        for t in item["tickers"]:
            if t in ticker_news:
                ticker_news[t].append(item["title"])
    actions = []
    for p in positions:
        if p["technical_status"] == "actionable" and p["weight_pct"] < 25:
            actions.append(f"{p['ticker']}: giữ/quan sát tăng tỷ trọng chỉ khi thị trường xác nhận; không đuổi giá.")
        elif p["technical_status"] in ["idea", "avoid"]:
            actions.append(f"{p['ticker']}: rà soát điểm giảm rủi ro vì tín hiệu kỹ thuật chưa đủ mạnh.")
        else:
            actions.append(f"{p['ticker']}: tiếp tục theo dõi, chưa cần hành động lớn.")
    if not positions:
        actions.append("Không có cổ phiếu để khuyến nghị mua/bán; giữ tiền mặt đến khi nhập positions thật hoặc có kế hoạch giải ngân.")
    return {
        "run_id": f"portfolio_daily_advice_{now_iso()}",
        "as_of": portfolio["as_of"],
        "pipeline": "portfolio_daily_advice",
        "nav_vnd": nav,
        "equity_value_vnd": equity_value,
        "cash_vnd": portfolio["cash_vnd"],
        "cash_pct": round(cash_pct, 2),
        "total_pnl_vnd": equity_value - total_cost,
        "total_pnl_pct": round((equity_value / total_cost - 1) * 100, 2) if total_cost else 0,
        "positions": positions,
        "sector_weights": sector_weights,
        "ticker_news": ticker_news,
        "risks": risks or ["Chưa phát hiện rủi ro vượt ngưỡng cấu hình."],
        "actions": actions,
        "sources": [portfolio["source"], market["source"], news["source"], ohlcv["source"]],
        "confidence": 0.76,
        "disclaimer": "Kế hoạch danh mục cần đối chiếu khẩu vị rủi ro thật và lệnh thực tế.",
    }


def run_company_deep_dive(inputs: Dict[str, Any], ticker: str) -> Dict[str, Any]:
    fundamentals, news, ohlcv = inputs["fundamentals"], inputs["news"], inputs["ohlcv"]
    co = next((c for c in fundamentals["companies"] if c["ticker"] == ticker), None)
    if not co:
        raise ValueError(f"Ticker not found in fundamentals mock: {ticker}")
    bar = next((b for b in ohlcv["bars"] if b["ticker"] == ticker), None)
    related_news = [n for n in news["items"] if ticker in n["tickers"]]
    val = co["valuation"]
    fin = co["financials"]
    valuation_view = "cao hơn cần biên an toàn" if val["pe_ttm"] > 22 else "trung tính" if val["pe_ttm"] > 14 else "không đắt theo P/E mock"
    return {
        "run_id": f"company_deep_dive_{ticker}_{now_iso()}",
        "as_of": fundamentals["as_of"],
        "pipeline": "company_deep_dive",
        "ticker": ticker,
        "business": co["business"],
        "sector": co["sector"],
        "financial_quality": f"ROE {fin['roe']:.1%}, tăng trưởng LNST {fin['net_profit_growth_yoy']:.1%}, D/E {fin['debt_to_equity']:.2f}.",
        "valuation": f"P/E {val['pe_ttm']}, P/B {val['pb']}, EV/EBITDA {val['ev_ebitda']}. Nhận định: {valuation_view}.",
        "peer_percentile": co["peer_percentile"],
        "technical_snapshot": bar,
        "news": related_news,
        "risks": co["risks"],
        "watch_conditions": [
            "Kết quả kinh doanh quý tới xác nhận tăng trưởng.",
            "Giá không thủng vùng hỗ trợ kỹ thuật chính.",
            "Định giá không mở rộng quá nhanh so với tăng trưởng lợi nhuận.",
        ],
        "sources": [fundamentals["source"], news["source"], ohlcv["source"]],
        "confidence": 0.73,
        "disclaimer": "Company deep dive là hồ sơ tham chiếu, không phải lệnh mua/bán.",
    }


def markdown_eod(result: Dict[str, Any], template: str) -> str:
    sector_table = md_table(["Ngành", "% phiên", "GTGD tỷ", "RS20D"], result["sector_table"])
    watchlist = "\n".join(f"- {n['title']} ({', '.join(n['tickers']) or 'vĩ mô'}): {n['summary']}" for n in result["news_brief"])
    conditions = "\n".join(f"- {x}" for x in result["next_session_conditions"])
    return render_template(template, {
        "date": result["as_of"][:10],
        "market_thesis": result["market_thesis"],
        "regime": result["market_regime"]["regime"],
        "risk_appetite": result["market_regime"]["risk_appetite"],
        "sector_table": sector_table,
        "watchlist": watchlist,
        "next_session_conditions": conditions,
    }) + f"\n\nNguồn: {', '.join(result['sources'])}\n\n{result['disclaimer']}\n"


def markdown_signals(result: Dict[str, Any], template: str) -> str:
    rows = [[s["ticker"], s["status"], s["score"], s["entry_zone"], s["invalidation"], s["confidence"]] for s in result["signals"]]
    table = md_table(["Ticker", "Status", "Score", "Entry zone", "Invalidation", "Confidence"], rows)
    groups = {k: "\n".join(f"- {s['ticker']}: {s['risk']}" for s in result["signals"] if s["status"] == k) or "- Không có" for k in ["actionable", "watch", "avoid"]}
    return render_template(template, {"signal_table": table, "actionable": groups["actionable"], "watch": groups["watch"], "avoid": groups["avoid"]}) + f"\n\nNguồn: {', '.join(result['sources'])}\n\n{result['disclaimer']}\n"


def markdown_portfolio(result: Dict[str, Any], template: str) -> str:
    nav_summary = f"NAV {money_vnd(result['nav_vnd'])}; cổ phiếu {money_vnd(result['equity_value_vnd'])}; cash {result['cash_pct']}%; P&L {money_vnd(result['total_pnl_vnd'])} ({result['total_pnl_pct']}%)."
    pos_rows = [[p["ticker"], p["weight_pct"], money_vnd(p["value_vnd"]), p["pnl_pct"], p["technical_status"]] for p in result["positions"]]
    position_alerts = md_table(["Ticker", "Weight %", "Value", "P&L %", "Tech"], pos_rows) + "\n\n" + "\n".join(f"- {r}" for r in result["risks"])
    action_plan = "\n".join(f"- {a}" for a in result["actions"])
    return render_template(template, {"date": result["as_of"][:10], "nav_summary": nav_summary, "position_alerts": position_alerts, "action_plan": action_plan}) + f"\n\nNguồn: {', '.join(result['sources'])}\n\n{result['disclaimer']}\n"


def markdown_company(result: Dict[str, Any], template: str) -> str:
    financials = result["financial_quality"]
    risks = "\n".join(f"- {r}" for r in result["risks"])
    return render_template(template, {"ticker": result["ticker"], "business": result["business"], "financials": financials, "valuation": result["valuation"], "risks": risks}) + f"\n\nNguồn: {', '.join(result['sources'])}\n\n{result['disclaimer']}\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="orchestrator.yaml")
    ap.add_argument("--pipeline", required=True)
    ap.add_argument("--ticker", default="FPT")
    ap.add_argument("--mock", action="store_true", help="Use mock_data configured in orchestrator.yaml. Requires --allow-quality-warnings.")
    ap.add_argument("--live", action="store_true", help="Use data_live generated by FData/data adapters. Default mode.")
    ap.add_argument("--universe", choices=["hose_all", "investable"], default="hose_all", help="Signal universe for live OHLCV: hose_all = full HOSE; investable = liquidity-filtered")
    ap.add_argument("--allow-quality-warnings", action="store_true", help="Do not block run when quality gate warns")
    args = ap.parse_args()

    if args.mock and not args.allow_quality_warnings:
        raise RuntimeError("MOCK_BLOCKED: production path defaults to live; mock requires --mock --allow-quality-warnings")
    live_mode = not args.mock

    cfg_path = resolve_config_path(args.config)
    config = load_config(cfg_path)
    if args.pipeline not in config["pipelines"]:
        raise KeyError(f"Unknown pipeline: {args.pipeline}")
    pipeline = config["pipelines"][args.pipeline]
    log_path = ROOT / config["runtime"].get("audit_log", "logs/audit.jsonl")

    audit(log_path, {"event": "pipeline_start", "pipeline": args.pipeline, "mock": args.mock, "live": live_mode, "universe": args.universe})
    inputs = load_inputs(config, pipeline, live=live_mode, universe=args.universe, pipeline_name=args.pipeline)
    warnings = quality_gate(config, inputs, args.pipeline)
    assert_quality_or_raise(config, warnings, args.allow_quality_warnings or args.mock)
    for w in warnings:
        audit(log_path, {"event": "quality_warning", "pipeline": args.pipeline, "warning": w})

    if args.pipeline == "eod_market_brief":
        result = run_eod_market_brief(inputs)
        md = markdown_eod(result, (ROOT / pipeline["outputs"]["template"]).read_text(encoding="utf-8"))
    elif args.pipeline == "stock_signal_scan":
        result = run_stock_signal_scan(inputs)
        md = markdown_signals(result, (ROOT / pipeline["outputs"]["template"]).read_text(encoding="utf-8"))
    elif args.pipeline == "portfolio_daily_advice":
        result = run_portfolio_daily_advice(inputs)
        md = markdown_portfolio(result, (ROOT / pipeline["outputs"]["template"]).read_text(encoding="utf-8"))
    elif args.pipeline == "company_deep_dive":
        result = run_company_deep_dive(inputs, args.ticker.upper())
        md = markdown_company(result, (ROOT / pipeline["outputs"]["template"]).read_text(encoding="utf-8"))
    else:
        raise NotImplementedError(args.pipeline)

    result["quality_warnings"] = warnings
    result["production_phase_3"] = {"orchestrator_calls_agents": True, "lead_agent": pipeline.get("lead_agent"), "agents": pipeline.get("agent_ids", []), "tool_outputs": pipeline.get("tools", []), "quality_report": warnings, "final_writer": pipeline.get("final_writer")}
    out_json = ROOT / pipeline["outputs"]["json"]
    out_md = ROOT / pipeline["outputs"]["markdown"]
    if args.pipeline == "stock_signal_scan" and live_mode:
        suffix = args.universe
        out_json = out_json.with_name(f"{out_json.stem}_{suffix}{out_json.suffix}")
        out_md = out_md.with_name(f"{out_md.stem}_{suffix}{out_md.suffix}")
    save_json(out_json, result)
    save_text(out_md, md)
    audit(log_path, {"event": "pipeline_done", "pipeline": args.pipeline, "json": str(out_json), "markdown": str(out_md), "warnings": warnings})
    print(f"OK {args.pipeline}")
    print(f"JSON: {out_json}")
    print(f"MD:   {out_md}")
    if warnings:
        print("WARNINGS:")
        for w in warnings:
            print(f"- {w}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
