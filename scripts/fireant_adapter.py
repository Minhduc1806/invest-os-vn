#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
import re
import subprocess
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import requests

try:
    import msgpack  # type: ignore
except Exception:  # pragma: no cover
    msgpack = None

ROOT = Path(__file__).resolve().parents[1]
LIVE = ROOT / "data_live"
RAW = LIVE / "raw" / "fireant"
OUT = LIVE / "fireant_foreign_flow.vn.json"
FIREANT = "https://fireant.vn"
REST = "https://restv2.fireant.vn"
INDEX_SYMBOLS = {"VNINDEX", "VN30", "HNXINDEX", "UPINDEX"}


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def save_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def session() -> requests.Session:
    s = requests.Session()
    s.headers.update({
        "User-Agent": "Mozilla/5.0 invest-os-vn fireant-adapter/0.2",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "vi,en;q=0.8",
        "Referer": "https://fireant.vn/dashboard",
        "Origin": "https://fireant.vn",
    })
    return s


def fetch_text(s: requests.Session, url: str, timeout: int = 35) -> str:
    r = s.get(url, timeout=timeout)
    r.raise_for_status()
    return r.text


def discover_worker_url(s: requests.Session) -> str:
    html = fetch_text(s, f"{FIREANT}/dashboard")
    RAW.mkdir(parents=True, exist_ok=True)
    (RAW / "dashboard.html").write_text(html, encoding="utf-8")
    candidates = re.findall(r'(/assets/quote\.worker-[^"\']+\.js)', html)
    if not candidates:
        scripts = re.findall(r'<script[^>]+src=["\']([^"\']+\.js)["\']', html)
        for src in scripts:
            url = src if src.startswith("http") else FIREANT + src
            js = fetch_text(s, url)
            m = re.search(r'/assets/quote\.worker-[^"\']+\.js', js)
            if m:
                return FIREANT + m.group(0)
        raise RuntimeError("FIREANT_WORKER_NOT_FOUND")
    return FIREANT + candidates[0]


def extract_public_bearer(worker_js: str) -> str:
    patterns = [
        r'Authorization:`Bearer ([^`]+)`',
        r'Authorization\s*:\s*["\']Bearer\s+([^"\']+)["\']',
    ]
    for pat in patterns:
        m = re.search(pat, worker_js)
        if m:
            return m.group(1)
    raise RuntimeError("FIREANT_PUBLIC_BEARER_NOT_FOUND")


def fetch_icb_latest(s: requests.Session, bearer: str) -> list[dict[str, Any]]:
    h = dict(s.headers)
    h["Authorization"] = f"Bearer {bearer}"
    r = s.get(f"{REST}/icb/latest-index", headers=h, timeout=35)
    r.raise_for_status()
    RAW.mkdir(parents=True, exist_ok=True)
    (RAW / "icb_latest_index.json").write_text(r.text, encoding="utf-8")
    data = r.json()
    if not isinstance(data, list):
        raise RuntimeError("FIREANT_ICB_SCHEMA_NOT_LIST")
    return data


def safe_num(v: Any) -> float | int | None:
    if v is None:
        return None
    try:
        x = float(v)
        return int(x) if abs(x - int(x)) < 1e-9 else x
    except Exception:
        return None


def normalize_industry(row: dict[str, Any]) -> dict[str, Any]:
    vals = row.get("indexValues") or {}
    code = str(row.get("industryCode") or vals.get("ICBCode") or "")
    buy_value = safe_num(vals.get("BuyForeignValue")) or 0
    sell_value = safe_num(vals.get("SellForeignValue")) or 0
    buy_qty = safe_num(vals.get("BuyForeignQuantity")) or 0
    sell_qty = safe_num(vals.get("SellForeignQuantity")) or 0
    return {
        "industry_code": code,
        "industry_name": vals.get("ICBName"),
        "level": len(code),
        "date": row.get("date"),
        "index_open": safe_num(vals.get("IndexOpen")),
        "index_high": safe_num(vals.get("IndexHigh")),
        "index_low": safe_num(vals.get("IndexLow")),
        "index_close": safe_num(vals.get("IndexClose")),
        "index_prev": safe_num(vals.get("IndexPrev")),
        "volume_shares": safe_num(vals.get("Volume")),
        "value_vnd": safe_num(vals.get("Value")),
        "foreign_buy_qty": buy_qty,
        "foreign_sell_qty": sell_qty,
        "foreign_net_qty": buy_qty - sell_qty,
        "foreign_buy_value_vnd": buy_value,
        "foreign_sell_value_vnd": sell_value,
        "foreign_net_value_vnd": buy_value - sell_value,
        "positive_money_flow_vnd": safe_num(vals.get("PositiveMoneyFlow")),
        "negative_money_flow_vnd": safe_num(vals.get("NegativeMoneyFlow")),
        "neutral_money_flow_vnd": safe_num(vals.get("NeutralMoneyFlow")),
        "pe": safe_num(vals.get("PE")),
        "pb": safe_num(vals.get("PB")),
        "ps": safe_num(vals.get("PS")),
        "market_cap_vnd": safe_num(vals.get("MarketCap")),
    }


def run_playwright_capture(wait_ms: int = 22000) -> list[dict[str, Any]]:
    RAW.mkdir(parents=True, exist_ok=True)
    frames_path = RAW / "websocket_frames.json"
    script = f"""
const {{ chromium }} = require('playwright');
const fs = require('fs');
(async()=>{{
 const browser=await chromium.launch({{headless:true}});
 const page=await browser.newPage({{viewport:{{width:1440,height:1200}}}});
 let messages=[];
 page.on('websocket', ws=>{{
   messages.push({{type:'ws_open',url:ws.url().replace(/access_token=[^&]+/,'access_token=[REDACTED]'),ts:Date.now()}});
   ws.on('framesent', f=>messages.push({{type:'sent',payload:f.payload,ts:Date.now()}}));
   ws.on('framereceived', f=>messages.push({{type:'recv',payload:f.payload,ts:Date.now()}}));
 }});
 await page.goto('https://fireant.vn/dashboard',{{waitUntil:'domcontentloaded',timeout:60000}});
 await page.waitForTimeout({wait_ms});
 fs.writeFileSync({json.dumps(str(frames_path))}, JSON.stringify(messages), 'utf8');
 await browser.close();
}})().catch(e=>{{console.error(e); process.exit(1);}});
"""
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8", dir=str(ROOT / "scripts")) as f:
        f.write(script)
        tmp = Path(f.name)
    try:
        subprocess.run(["node", str(tmp)], cwd=ROOT, check=True, timeout=max(80, wait_ms // 1000 + 40))
    finally:
        try:
            tmp.unlink()
        except Exception:
            pass
    return json.loads(frames_path.read_text(encoding="utf-8"))


def _unpack_msgpack_blob(bb: bytes) -> Any | None:
    if bb and bb[-1] == 0x1E:
        bb = bb[:-1]
    try:
        return msgpack.unpackb(bb, raw=False, strict_map_key=False, timestamp=3)
    except Exception:
        return None


def decode_msgpack_payloads(payload: Any) -> list[Any]:
    if msgpack is None or not isinstance(payload, dict) or payload.get("type") != "Buffer":
        return []
    b = bytes(payload.get("data") or [])
    out: list[Any] = []

    # SignalR binary protocol: one frame can contain multiple length-prefixed MessagePack messages.
    pos = 0
    while pos < len(b):
        shift = 0
        size = 0
        start = pos
        while pos < len(b):
            byte = b[pos]
            pos += 1
            size |= (byte & 0x7F) << shift
            if (byte & 0x80) == 0:
                break
            shift += 7
        if size <= 0 or pos + size > len(b):
            pos = start
            break
        val = _unpack_msgpack_blob(b[pos:pos + size])
        if val is not None:
            out.append(val)
        pos += size

    if out:
        return out

    # Fallback for captured handshake or non-standard fragments.
    for off in range(0, 6):
        val = _unpack_msgpack_blob(b[off:])
        if val is not None:
            return [val]
    return []


def decode_frames(frames: list[dict[str, Any]]) -> tuple[list[Any], dict[str, str]]:
    decoded: list[Any] = []
    invocation_map: dict[str, str] = {}
    for frame in frames:
        vals = decode_msgpack_payloads(frame.get("payload"))
        for val in vals:
            decoded.append(val)
            if frame.get("type") == "sent" and isinstance(val, list) and len(val) >= 4 and val[0] == 1:
                invocation_map[str(val[2])] = str(val[3])
    save_json(RAW / "websocket_decoded.json", decoded)
    return decoded, invocation_map


def normalize_symbol(e: list[Any]) -> dict[str, Any]:
    icb = e[18] if len(e) > 18 else None
    return {
        "symbol": e[0], "type": e[1], "name": e[2], "exchange": e[3], "is_listing": e[4],
        "sector_code": str(icb)[:2] if icb else None,
        "industry_code": str(icb)[:6] if icb else None,
        "sector": e[7] if len(e) > 7 else None, "industry": e[8] if len(e) > 8 else None,
        "unit": e[9] if len(e) > 9 else None, "session": e[11] if len(e) > 11 else None,
        "timezone": e[12] if len(e) > 12 else None, "fraction_digits": e[15] if len(e) > 15 else None,
        "shares_outstanding": e[16] if len(e) > 16 else None, "total_shares": e[17] if len(e) > 17 else None,
        "icb_code": icb,
    }


def normalize_price(e: list[Any]) -> dict[str, Any]:
    return {"symbol": e[0], "date": e[1], "last": e[2], "volume": e[3], "total_volume": e[4], "total_value": e[5], "current": e[6], "active_buy_volume": e[7], "deal_volume": e[8] if len(e) > 8 else e[7], "volume24h": e[9] if len(e) > 9 else None}


def normalize_ref(e: list[Any]) -> dict[str, Any]:
    return {"symbol": e[0], "date": e[1], "prev": e[2], "ceiling": e[3], "floor": e[4], "open": e[5], "high": e[6], "low": e[7], "fraction_digits": e[8] if len(e) > 8 else None, "session_date": e[9] if len(e) > 9 else None}


def normalize_exchange(e: list[Any]) -> dict[str, Any]:
    return {"symbol": e[0], "date": e[1], "advances": e[2], "declines": e[3], "unchanged": e[4], "advances_value": e[5], "declines_value": e[6], "unchanged_value": e[7]}


def normalize_foreigner(e: list[Any]) -> dict[str, Any]:
    buy_q, sell_q, buy_v, sell_v = e[3], e[4], e[5], e[6]
    return {"symbol": e[0], "date": e[1], "current_foreign_room": e[2], "buy_foreign_quantity": buy_q, "sell_foreign_quantity": sell_q, "foreign_net_quantity": buy_q - sell_q, "buy_foreign_value": buy_v, "sell_foreign_value": sell_v, "foreign_net_value": buy_v - sell_v}


def normalize_orderbook(e: list[Any]) -> dict[str, Any]:
    return {"symbol": e[0], "date": e[1], "total_bid_quantity": e[2], "total_ask_quantity": e[3], "bids": e[4], "asks": e[5]}


TRADING_STAT_FIELDS = {
    12: "price_change_1w", 13: "price_change_1m", 14: "price_change_3m", 15: "price_change_6m", 16: "price_change_1y",
    33: "avg_volume_4d", 34: "avg_volume_5d", 36: "avg_volume_10d", 40: "avg_volume_20d", 42: "avg_volume_45d", 43: "avg_volume_3m", 44: "avg_volume_6m", 45: "avg_volume_1y",
    46: "avg_value_4d", 47: "avg_value_9d", 48: "avg_value_14d", 49: "avg_value_19d", 50: "avg_value_44d",
    51: "ema_5d", 55: "ema_10d", 65: "ema_20d", 69: "ema_45d", 81: "beta", 82: "mfi_14d",
    88: "buy_foreign_qty_4d", 89: "buy_foreign_qty_9d", 90: "buy_foreign_qty_14d", 91: "buy_foreign_qty_19d", 92: "buy_foreign_qty_44d",
    93: "buy_foreign_val_4d", 94: "buy_foreign_val_9d", 95: "buy_foreign_val_14d", 96: "buy_foreign_val_19d", 97: "buy_foreign_val_44d",
    98: "sell_foreign_qty_4d", 99: "sell_foreign_qty_9d", 100: "sell_foreign_qty_14d", 101: "sell_foreign_qty_19d", 102: "sell_foreign_qty_44d",
    103: "sell_foreign_val_4d", 104: "sell_foreign_val_9d", 105: "sell_foreign_val_14d", 106: "sell_foreign_val_19d", 107: "sell_foreign_val_44d",
    151: "foreigner_net_buy_consecutive_days", 152: "foreigner_net_buy_consecutive_volume", 153: "foreigner_net_buy_consecutive_value", 161: "foreign_ownership",
}
FINANCIAL_FIELDS = {9: "eps", 27: "roa", 29: "roe", 30: "roic", 12: "gross_margin", 16: "operating_margin", 18: "pre_tax_margin", 1: "after_tax_margin", 31: "sales", 19: "profit", 35: "sales_growth_ttm", 23: "profit_growth_ttm", 39: "debt_over_assets", 40: "debt_over_equity", 7: "dividend_yield", 2: "book_value_per_share", 6: "current_ratio", 24: "quick_ratio"}


def normalize_sparse_row(
    e: list[Any],
    fields: dict[int, str],
    row_index: int | None = None,
    symbol: str | None = None,
    mapping_source: str | None = None,
) -> dict[str, Any]:
    out: dict[str, Any] = {}
    if symbol:
        out["symbol"] = symbol
        out["symbol_mapping_source"] = mapping_source or "unknown"
    if row_index is not None:
        out["row_index"] = row_index
    for idx, name in fields.items():
        if len(e) > idx:
            out[name] = e[idx]
    return out

def map_rows_to_symbols(rows: list[Any], symbols: list[dict[str, Any]]) -> tuple[list[tuple[list[Any], str | None]], str]:
    ordered_symbols = [str(s.get("symbol") or "").strip() for s in symbols if s.get("symbol")]
    list_rows = [r for r in rows if isinstance(r, list) and r]
    if ordered_symbols and len(list_rows) <= len(ordered_symbols):
        return [(row, ordered_symbols[i]) for i, row in enumerate(list_rows)], "GetSymbols_order"
    return [(row, None) for row in list_rows], "row_index_only"


def normalize_bar(e: list[Any]) -> dict[str, Any]:
    return {"date": e[0], "open": e[1], "high": e[2], "low": e[3], "close": e[4], "volume": e[5], "total_volume": e[6] if len(e) > 6 else None, "value": e[7] if len(e) > 7 else None, "total_value": e[8] if len(e) > 8 else None}


def extract_signalr_data(decoded: list[Any], invocation_map: dict[str, str]) -> dict[str, Any]:
    prices: dict[str, dict[str, Any]] = {}
    refs: dict[str, dict[str, Any]] = {}
    exchange: dict[str, dict[str, Any]] = {}
    foreigner: dict[str, dict[str, Any]] = {}
    order_books: dict[str, dict[str, Any]] = {}
    symbols: list[dict[str, Any]] = []
    trading_stats: list[dict[str, Any]] = []
    financials: list[dict[str, Any]] = []
    intraday_bars: dict[str, list[dict[str, Any]]] = {}
    daily_bars: dict[str, list[dict[str, Any]]] = {}

    for val in decoded:
        if not (isinstance(val, list) and len(val) >= 4):
            continue
        if val[0] == 1 and val[3] == "UpdateLastPrices":
            for e in (val[4][0] if len(val) > 4 and val[4] else []):
                p = normalize_price(e); prices[p["symbol"]] = p
        elif val[0] == 1 and val[3] == "UpdateRefPrices":
            for e in (val[4][0] if len(val) > 4 and val[4] else []):
                r = normalize_ref(e); refs[r["symbol"]] = r
        elif val[0] == 1 and val[3] == "UpdateExchangeStats":
            for e in (val[4][0] if len(val) > 4 and val[4] else []):
                x = normalize_exchange(e); exchange[x["symbol"]] = x
        elif val[0] == 1 and val[3] == "UpdateForeignerStats":
            for e in (val[4][0] if len(val) > 4 and val[4] else []):
                f = normalize_foreigner(e); foreigner[f["symbol"]] = f
        elif val[0] == 1 and val[3] == "UpdateOrderBooks":
            for e in (val[4][0] if len(val) > 4 and val[4] else []):
                ob = normalize_orderbook(e); order_books[ob["symbol"]] = ob
        elif val[0] == 3 and len(val) >= 5:
            method = invocation_map.get(str(val[2]), "")
            result = val[4]
            if method == "GetSymbols" and isinstance(result, list):
                symbols = [normalize_symbol(e) for e in result if isinstance(e, list) and e]
            elif method == "GetTradingStatistics" and isinstance(result, list) and len(result) > 1 and isinstance(result[1], list):
                mapped_rows, mapping_source = map_rows_to_symbols(result[1], symbols)
                trading_stats = [normalize_sparse_row(e, TRADING_STAT_FIELDS, i, symbol, mapping_source) for i, (e, symbol) in enumerate(mapped_rows)]
            elif method == "GetFinancialInfos" and isinstance(result, list):
                mapped_rows, mapping_source = map_rows_to_symbols(result, symbols)
                financials = [normalize_sparse_row(e, FINANCIAL_FIELDS, i, symbol, mapping_source) for i, (e, symbol) in enumerate(mapped_rows)]
            elif method == "GetIntradayBars" and isinstance(result, list) and len(result) > 0:
                # Symbol recovered from sent invocation is not retained here; keep bucket by invocation id.
                intraday_bars[str(val[2])] = [normalize_bar(e) for e in (result[0] or []) if isinstance(e, list)]
            elif method == "GetBars" and isinstance(result, list) and len(result) > 0:
                daily_bars[str(val[2])] = [normalize_bar(e) for e in (result[0] or []) if isinstance(e, list)]

    market_indices = []
    for sym in INDEX_SYMBOLS:
        merged = {"symbol": sym}
        merged.update(refs.get(sym, {}))
        merged.update(prices.get(sym, {}))
        if len(merged) > 1:
            market_indices.append(merged)

    return {
        "market_indices": market_indices,
        "exchange_breadth": list(exchange.values()),
        "ticker_metadata": symbols,
        "ticker_realtime_prices": list(prices.values()),
        "order_books": list(order_books.values()),
        "ticker_flows": list(foreigner.values()),
        "ticker_trading_statistics": trading_stats,
        "financial_ratios": financials,
        "intraday_bars": intraday_bars,
        "daily_bars": daily_bars,
    }


def build_payload(phases: str = "all", wait_ms: int = 22000) -> dict[str, Any]:
    warnings: list[str] = []
    missing_fields: list[str] = []
    s = session()
    worker_url = discover_worker_url(s)
    worker_js = fetch_text(s, worker_url)
    RAW.mkdir(parents=True, exist_ok=True)
    redacted = re.sub(r'(Authorization:`Bearer )([^`]+)(`)', r'\1[REDACTED]\3', worker_js)
    (RAW / "quote_worker.redacted.js").write_text(redacted, encoding="utf-8")
    bearer = extract_public_bearer(worker_js)

    rows = fetch_icb_latest(s, bearer)
    industry_flows = [normalize_industry(r) for r in rows]
    industry_flows = [r for r in industry_flows if r.get("industry_code")]
    if not industry_flows:
        missing_fields.append("industry_flows")

    sig = {
        "market_indices": [], "exchange_breadth": [], "ticker_metadata": [], "ticker_realtime_prices": [],
        "order_books": [], "ticker_flows": [], "ticker_trading_statistics": [], "financial_ratios": [],
        "intraday_bars": {}, "daily_bars": {},
    }
    if phases == "all":
        if msgpack is None:
            warnings.append("msgpack_missing;signalr_phases_skipped")
        else:
            try:
                frames = run_playwright_capture(wait_ms=wait_ms)
                decoded, invocation_map = decode_frames(frames)
                sig = extract_signalr_data(decoded, invocation_map)
            except Exception as e:
                warnings.append(f"signalr_capture_failed:{type(e).__name__}:{e}")

    for k in ["market_indices", "exchange_breadth", "ticker_metadata", "ticker_realtime_prices", "ticker_trading_statistics", "financial_ratios"]:
        if not sig.get(k):
            missing_fields.append(k)
    # These are event-driven; absence during short capture is partial, not failure.
    for k in ["order_books", "ticker_flows"]:
        if not sig.get(k):
            warnings.append(f"{k}:no_frame_seen_in_short_capture")

    ready_groups = 1 + sum(1 for k in ["market_indices", "exchange_breadth", "ticker_metadata", "ticker_realtime_prices", "ticker_trading_statistics", "financial_ratios"] if sig.get(k))
    quality_score = round(min(0.95, 0.45 + ready_groups * 0.08 + (0.12 if industry_flows else 0)), 2)
    return {
        "source": "fireant_public_dashboard",
        "source_url": "https://fireant.vn/dashboard",
        "source_policy": "cophieu68_primary_fireant_supplement_for_realtime_breadth_sector_intelligence",
        "timestamp": now_iso(),
        "status": "real_parsed" if industry_flows else "empty",
        "phase": "phase1_to_phase5_rest_icb_plus_signalr_capture",
        "quality_score": quality_score,
        "auth_note": "public dashboard app bearer/access token extracted at runtime; token not stored",
        "records": len(industry_flows),
        "capabilities": {
            "phase1_sector_industry": bool(industry_flows),
            "phase2_market_realtime_breadth": bool(sig.get("market_indices") or sig.get("exchange_breadth")),
            "phase3_ticker_metadata_price_orderbook_foreign": bool(sig.get("ticker_metadata") or sig.get("ticker_realtime_prices") or sig.get("order_books") or sig.get("ticker_flows")),
            "phase4_trading_statistics_intraday": bool(sig.get("ticker_trading_statistics") or sig.get("intraday_bars") or sig.get("daily_bars")),
            "phase5_financial_ratios": bool(sig.get("financial_ratios")),
        },
        "industry_flows": industry_flows,
        **sig,
        "missing_fields": sorted(set(missing_fields)),
        "warnings": warnings,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="FireAnt public dashboard adapter for InvestOS VN")
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--phases", choices=["phase1", "all"], default="all")
    ap.add_argument("--wait-ms", type=int, default=22000)
    args = ap.parse_args()
    try:
        payload = build_payload(phases=args.phases, wait_ms=args.wait_ms)
    except Exception as e:
        payload = {
            "source": "fireant_public_dashboard",
            "source_url": "https://fireant.vn/dashboard",
            "source_policy": "cophieu68_primary_fireant_supplement_for_realtime_breadth_sector_intelligence",
            "timestamp": now_iso(),
            "status": "provider_down_or_schema_changed",
            "phase": "phase1_to_phase5_rest_icb_plus_signalr_capture",
            "quality_score": 0.0,
            "industry_flows": [],
            "missing_fields": ["industry_flows"],
            "warnings": [f"fireant_adapter_failed:{type(e).__name__}:{e}"],
        }
    save_json(Path(args.out), payload)
    print(json.dumps({
        "out": str(Path(args.out)),
        "status": payload.get("status"),
        "records": payload.get("records", 0),
        "quality_score": payload.get("quality_score"),
        "capabilities": payload.get("capabilities", {}),
        "warnings": payload.get("warnings", []),
    }, ensure_ascii=False))
    return 0 if payload.get("status") == "real_parsed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
