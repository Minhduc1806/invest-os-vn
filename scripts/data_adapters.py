#!/usr/bin/env python
"""
Real data adapters for Invest OS VN.

Primary provider: vnstock Python package when available.
Fallback: existing mock_data files with provider_down warning.

Usage:
  python scripts/data_adapters.py --all
  python scripts/data_adapters.py --market --tickers FPT,MWG,VCB,SSI
"""
from __future__ import annotations

import argparse
import json
import math
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
MOCK = ROOT / "mock_data"
LIVE = ROOT / "data_live"


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def save(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def load_mock(name: str) -> Dict[str, Any]:
    data = json.loads((MOCK / name).read_text(encoding="utf-8"))
    data["adapter_warning"] = "provider_down_or_schema_changed; fallback_to_mock"
    data["adapter_as_of"] = now_iso()
    return data


def to_records(df: Any) -> List[Dict[str, Any]]:
    if df is None:
        return []
    try:
        return df.to_dict("records")
    except Exception:
        return []


def num(x: Any, default: float = 0.0) -> float:
    try:
        if x is None:
            return default
        if isinstance(x, str):
            x = x.replace(",", "")
        v = float(x)
        if math.isnan(v):
            return default
        return v
    except Exception:
        return default


def pick(row: Dict[str, Any], names: List[str], default: Any = None) -> Any:
    low = {str(k).lower(): v for k, v in row.items()}
    for n in names:
        if n in row:
            return row[n]
        if n.lower() in low:
            return low[n.lower()]
    return default


def pct_change(a: float, b: float) -> float:
    return round((a / b - 1) * 100, 2) if b else 0.0


def ma(vals: List[float], n: int) -> float:
    if not vals:
        return 0.0
    chunk = vals[-n:] if len(vals) >= n else vals
    return round(sum(chunk) / len(chunk), 2)


def rsi(vals: List[float], n: int = 14) -> float:
    if len(vals) < n + 1:
        return 50.0
    gains, losses = [], []
    for i in range(-n, 0):
        ch = vals[i] - vals[i - 1]
        gains.append(max(ch, 0))
        losses.append(abs(min(ch, 0)))
    avg_gain = sum(gains) / n
    avg_loss = sum(losses) / n
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return round(100 - (100 / (1 + rs)), 2)


def atr_pct(rows: List[Dict[str, Any]], n: int = 14) -> float:
    if len(rows) < 2:
        return 0.0
    trs = []
    for i in range(max(1, len(rows) - n), len(rows)):
        high = num(pick(rows[i], ["high", "High"]), 0)
        low = num(pick(rows[i], ["low", "Low"]), 0)
        prev_close = num(pick(rows[i - 1], ["close", "Close"]), 0)
        trs.append(max(high - low, abs(high - prev_close), abs(low - prev_close)))
    close = num(pick(rows[-1], ["close", "Close"]), 0)
    return round((sum(trs) / len(trs)) / close * 100, 2) if close else 0.0


def get_vnstock():
    try:
        import vnstock  # type: ignore
        return vnstock
    except Exception:
        return None


RATE_LIMIT_STOP = False
LAST_PROVIDER_CALL = 0.0

def provider_throttle(min_interval_sec: float = 3.2) -> None:
    global LAST_PROVIDER_CALL
    now = time.monotonic()
    wait = min_interval_sec - (now - LAST_PROVIDER_CALL)
    if wait > 0:
        time.sleep(wait)
    LAST_PROVIDER_CALL = time.monotonic()

def is_rate_limit_error(exc: Exception) -> bool:
    text = str(exc).lower()
    return "rate limit" in text or "giới hạn api" in text or "limit exceeded" in text or "20 requests" in text

def fetch_history_vnstock(ticker: str, days: int = 260) -> List[Dict[str, Any]]:
    global RATE_LIMIT_STOP
    if RATE_LIMIT_STOP:
        return []
    vnstock = get_vnstock()
    if vnstock is None:
        return []
    end = datetime.now()
    start = end - timedelta(days=days * 2)
    start_s = start.strftime("%Y-%m-%d")
    end_s = end.strftime("%Y-%m-%d")
    errors = []
    # vnstock 3.x Quote API
    try:
        provider_throttle()
        q = vnstock.Quote(symbol=ticker, source="VCI")
        df = q.history(start=start_s, end=end_s, interval="1D")
        recs = to_records(df)
        if recs:
            return recs[-days:]
    except Exception as e:
        errors.append(str(e))
        if is_rate_limit_error(e):
            RATE_LIMIT_STOP = True
            return []
    # legacy style fallback
    try:
        provider_throttle()
        stock = vnstock.Vnstock().stock(symbol=ticker, source="VCI")
        df = stock.quote.history(start=start_s, end=end_s, interval="1D")
        recs = to_records(df)
        if recs:
            return recs[-days:]
    except Exception as e:
        errors.append(str(e))
        if is_rate_limit_error(e):
            RATE_LIMIT_STOP = True
    return []


def build_ohlcv_live(tickers: List[str]) -> Dict[str, Any]:
    bars = []
    warnings = []
    index_close_20 = None
    # crude RS reference from VNINDEX if available
    idx_rows = fetch_history_vnstock("VNINDEX", 80)
    if idx_rows:
        idx_closes = [num(pick(r, ["close"])) for r in idx_rows if num(pick(r, ["close"]), 0) > 0]
        if len(idx_closes) >= 21:
            index_close_20 = pct_change(idx_closes[-1], idx_closes[-21])
    for t in tickers:
        rows = fetch_history_vnstock(t, 260)
        if not rows:
            warnings.append(f"{t}: provider_rate_limit_stop" if RATE_LIMIT_STOP else f"{t}: no_history")
            if RATE_LIMIT_STOP:
                break
            continue
        closes = [num(pick(r, ["close"])) for r in rows if num(pick(r, ["close"]), 0) > 0]
        vols = [num(pick(r, ["volume", "Volume", "vol"])) for r in rows]
        if len(closes) < 2:
            warnings.append(f"{t}: insufficient_history")
            continue
        last = rows[-1]
        close = closes[-1]
        prev = closes[-2]
        vol20 = sum(vols[-20:]) / min(20, len(vols)) if vols else 0
        ret20 = pct_change(closes[-1], closes[-21]) if len(closes) >= 21 else 0
        rs20 = round((ret20 - (index_close_20 or 0)) / 10, 2)
        bars.append({
            "ticker": t,
            "exchange": "VN",
            "date": str(pick(last, ["time", "date", "tradingDate"], ""))[:10],
            "close": close,
            "change_pct": pct_change(close, prev),
            "volume": int(num(pick(last, ["volume", "Volume", "vol"]), 0)),
            "vol_ratio_20d": round(num(pick(last, ["volume", "Volume", "vol"]), 0) / vol20, 2) if vol20 else 0,
            "ma20": ma(closes, 20),
            "ma50": ma(closes, 50),
            "ma200": ma(closes, 200),
            "rsi14": rsi(closes, 14),
            "atr14_pct": atr_pct(rows, 14),
            "rs_20d": rs20,
        })
    if not bars:
        data = load_mock("ohlcv_sample.vn.json")
        data["adapter_warning_detail"] = warnings
        return data
    return {"as_of": now_iso(), "source": "vnstock_history", "bars": bars, "quality_score": 0.86 if warnings else 0.94, "warnings": warnings}


def build_market_live(tickers: List[str]) -> Dict[str, Any]:
    # Index + breadth from fetched universe/tickers. True market-wide breadth needs paid/provider full market data.
    idx_symbols = ["VNINDEX", "VN30", "HNXINDEX"]
    indices = []
    warnings = []
    for sym in idx_symbols:
        rows = fetch_history_vnstock(sym, 60)
        if not rows:
            warnings.append(f"{sym}: provider_rate_limit_stop" if RATE_LIMIT_STOP else f"{sym}: no_index_history")
            if RATE_LIMIT_STOP:
                break
            continue
        closes = [num(pick(r, ["close"])) for r in rows if num(pick(r, ["close"]), 0) > 0]
        vols = [num(pick(r, ["volume", "vol"])) for r in rows]
        if len(closes) < 2:
            continue
        indices.append({
            "symbol": sym,
            "close": closes[-1],
            "change_pct": pct_change(closes[-1], closes[-2]),
            "volume_mn": round((vols[-1] if vols else 0) / 1_000_000, 2),
            "value_bil_vnd": 0,
            "above_ma20_pct": 100.0 if closes[-1] > ma(closes, 20) else 0.0,
        })
    ohlcv = build_ohlcv_live(tickers)
    bars = ohlcv.get("bars", [])
    adv = sum(1 for b in bars if b.get("change_pct", 0) > 0)
    dec = sum(1 for b in bars if b.get("change_pct", 0) < 0)
    unchanged = max(0, len(bars) - adv - dec)
    # sector mapping placeholder: dev can replace with real industry classification provider
    sector_map = {"FPT": "Công nghệ", "CMG": "Công nghệ", "VCB": "Ngân hàng", "TCB": "Ngân hàng", "MBB": "Ngân hàng", "SSI": "Chứng khoán", "VND": "Chứng khoán", "MWG": "Bán lẻ", "VIC": "Bất động sản", "VHM": "Bất động sản"}
    sector_bucket: Dict[str, List[Dict[str, Any]]] = {}
    for b in bars:
        sec = sector_map.get(b["ticker"], "Khác")
        sector_bucket.setdefault(sec, []).append(b)
    sectors = []
    for sec, xs in sector_bucket.items():
        sectors.append({
            "name": sec,
            "change_pct": round(sum(x["change_pct"] for x in xs) / len(xs), 2),
            "value_bil_vnd": 0,
            "relative_strength_20d": round(sum(x["rs_20d"] for x in xs) / len(xs), 2),
        })
    if not indices:
        data = load_mock("market_snapshot.vn.json")
        data["adapter_warning_detail"] = warnings
        return data
    return {
        "as_of": now_iso(),
        "source": "vnstock_history_adapter_partial_market",
        "market": "VN",
        "indices": indices,
        "breadth": {"advancers": adv, "decliners": dec, "unchanged": unchanged, "new_high_20d": None, "new_low_20d": None},
        "sectors": sectors or load_mock("market_snapshot.vn.json")["sectors"],
        "foreign_flow": {"net_value_bil_vnd": 0, "top_buy": [], "top_sell": [], "note": "not_available_in_free_adapter"},
        "derivatives": {"vn30f1m_basis": 0, "open_interest": 0, "note": "not_available_in_free_adapter"},
        "quality_score": 0.78 if warnings else 0.84,
        "warnings": warnings + ["partial_market_universe_breadth", "foreign_flow_not_available", "derivatives_placeholder"],
    }


def build_fundamentals_live(tickers: List[str]) -> Dict[str, Any]:
    vnstock = get_vnstock()
    companies = []
    warnings = []
    if vnstock is None:
        return load_mock("fundamentals_sample.vn.json")
    for t in tickers:
        item = {"ticker": t, "exchange": "VN", "sector": "unknown", "business": "", "financials": {}, "valuation": {}, "peer_percentile": {}, "risks": []}
        try:
            c = vnstock.Company(symbol=t)
            # Methods vary by vnstock version. Try common ones.
            for method in ["overview", "profile"]:
                if hasattr(c, method):
                    recs = to_records(getattr(c, method)())
                    if recs:
                        row = recs[0]
                        item["business"] = str(pick(row, ["shortName", "companyProfile", "businessType", "organName"], ""))
                        item["sector"] = str(pick(row, ["industry", "sector", "icbName3", "comGroupCode"], "unknown"))
                        break
        except Exception as e:
            warnings.append(f"{t}: company_profile_error: {e}")
        try:
            f = vnstock.Finance(symbol=t, source="VCI")
            # Keep raw compact due version variance
            if hasattr(f, "ratio"):
                recs = to_records(f.ratio(period="year", lang="vi", dropna=True))
                if recs:
                    row = recs[0]
                    item["financials"] = {k: row[k] for k in list(row.keys())[:20]}
        except Exception as e:
            warnings.append(f"{t}: finance_ratio_error: {e}")
        companies.append(item)
    if not companies:
        data = load_mock("fundamentals_sample.vn.json")
        data["adapter_warning_detail"] = warnings
        return data
    return {"as_of": now_iso(), "source": "vnstock_company_finance_partial", "companies": companies, "quality_score": 0.72, "warnings": warnings + ["fundamental_schema_partial"]}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tickers", default="FPT,MWG,VCB,SSI")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--market", action="store_true")
    ap.add_argument("--ohlcv", action="store_true")
    ap.add_argument("--fundamentals", action="store_true")
    args = ap.parse_args()
    tickers = [x.strip().upper() for x in args.tickers.split(",") if x.strip()]
    if args.all or args.market:
        p = LIVE / "market_snapshot.vn.json"
        save(p, build_market_live(tickers))
        print("wrote", p)
    if args.all or args.ohlcv:
        p = LIVE / "ohlcv_sample.vn.json"
        save(p, build_ohlcv_live(tickers))
        print("wrote", p)
    if args.all or args.fundamentals:
        p = LIVE / "fundamentals_sample.vn.json"
        save(p, build_fundamentals_live(tickers))
        print("wrote", p)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
