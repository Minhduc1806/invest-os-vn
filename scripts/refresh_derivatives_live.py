#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import requests

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data_live"
RAW = OUT / "raw" / "derivatives"
SYMBOLS = ["VN30F1M", "VN30F2M", "VN30F1Q", "VN30F2Q"]
UA = {
    "User-Agent": "Mozilla/5.0 invest-os-vn derivatives-live/1.0",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "vi,en;q=0.8",
    "Referer": "https://fireant.vn/",
}


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def save_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def get_text(url: str, headers: dict[str, str] | None = None, timeout: int = 30) -> str:
    response = requests.get(url, headers=headers or UA, timeout=timeout)
    response.raise_for_status()
    return response.text


def get_json(url: str, headers: dict[str, str] | None = None, timeout: int = 30) -> Any:
    response = requests.get(url, headers=headers or UA, timeout=timeout)
    response.raise_for_status()
    return response.json()


def fireant_public_token() -> str:
    candidates = [
        "https://static.fireant.vn/web/v1/_next/static/chunks/pages/_app-0a438895d7cca37b.js",
        "https://fireant.vn/dashboard",
    ]
    patterns = [
        r'let\s+rX\s*=\s*"NONE"\s*,\s*r\$\s*=\s*"([^"]+)"',
        r'Authorization\s*:\s*`Bearer\s+([^`]+)`',
        r'Authorization\s*:\s*["\']Bearer\s+([^"\']+)["\']',
    ]
    for url in candidates:
        text = get_text(url)
        redacted = text
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                token = match.group(1)
                redacted = redacted.replace(token, "[REDACTED]")
                RAW.mkdir(parents=True, exist_ok=True)
                (RAW / "fireant_token_source.redacted.txt").write_text(redacted[:500_000], encoding="utf-8")
                return token
    raise RuntimeError("FIREANT_PUBLIC_TOKEN_NOT_FOUND")


def fetch_fireant_quotes(token: str, symbols: list[str], start: datetime, end: datetime) -> dict[str, list[dict[str, Any]]]:
    headers = {**UA, "Authorization": f"Bearer {token}"}
    out: dict[str, list[dict[str, Any]]] = {}
    for symbol in ["VN30", *symbols]:
        url = f"https://restv2.fireant.vn/symbols/{symbol}/historical-quotes?startDate={start:%Y-%m-%d}&endDate={end:%Y-%m-%d}&offset=0&limit=30"
        data = get_json(url, headers=headers)
        out[symbol] = data if isinstance(data, list) else []
    return out


def fetch_vndirect(symbols: list[str]) -> tuple[dict[str, dict[str, Any]], dict[str, list[dict[str, Any]]]]:
    mappings_raw = get_json("https://api-finfo.vndirect.com.vn/v4/derivative_mappings")
    mappings = mappings_raw.get("data", []) if isinstance(mappings_raw, dict) else []
    map_by = {row["deriCode"]: row for row in mappings if row.get("deriCode") in symbols and row.get("code")}
    prices: dict[str, list[dict[str, Any]]] = {}
    for symbol, mapping in map_by.items():
        code = mapping["code"]
        url = f"https://api-finfo.vndirect.com.vn/v4/derivative_prices?sort=date:desc&size=10&q=code:{code}"
        raw = get_json(url)
        prices[symbol] = raw.get("data", []) if isinstance(raw, dict) else []
    return map_by, prices


def build_rows(fireant_quotes: dict[str, list[dict[str, Any]]], mappings: dict[str, dict[str, Any]], vnd_prices: dict[str, list[dict[str, Any]]], symbols: list[str]) -> list[dict[str, Any]]:
    vn30_by = {row["date"][:10]: row for row in fireant_quotes.get("VN30", []) if row.get("date")}
    rows: list[dict[str, Any]] = []
    for symbol in symbols:
        vnd_by = {row["date"][:10]: row for row in vnd_prices.get(symbol, []) if row.get("date")}
        for future in fireant_quotes.get(symbol, [])[:7]:
            date = future.get("date", "")[:10]
            vn30 = vn30_by.get(date, {})
            vnd = vnd_by.get(date, {})
            close = future.get("priceClose")
            vn30_close = vn30.get("priceClose")
            basis = close - vn30_close if close is not None and vn30_close is not None else None
            rows.append({
                "date": date,
                "symbol": symbol,
                "vndirect_code": mappings.get(symbol, {}).get("code"),
                "future_close": close,
                "vn30_close": vn30_close,
                "basis": basis,
                "basis_pct": basis / vn30_close * 100 if basis is not None and vn30_close else None,
                "fireant_volume": future.get("totalVolume"),
                "fireant_value": future.get("totalValue"),
                "foreign_net_qty": (future.get("buyForeignQuantity") or 0) - (future.get("sellForeignQuantity") or 0),
                "foreign_net_value": (future.get("buyForeignValue") or 0) - (future.get("sellForeignValue") or 0),
                "prop_net_value": future.get("propTradingNetValue"),
                "open_interest": vnd.get("openInterest"),
                "vndirect_volume": vnd.get("nmVolume"),
                "vndirect_value": vnd.get("nmValue"),
            })
    rows = sorted(rows, key=lambda row: (row["date"], row["symbol"]), reverse=True)
    for symbol in symbols:
        prev = None
        for row in sorted([r for r in rows if r["symbol"] == symbol], key=lambda r: r["date"]):
            oi = row.get("open_interest")
            row["oi_change"] = None if oi is None or prev is None else oi - prev
            if oi not in (None, 0):
                prev = oi
    return rows


def quality(rows: list[dict[str, Any]], mappings: dict[str, dict[str, Any]]) -> tuple[float, list[str]]:
    warnings: list[str] = []
    if not rows:
        warnings.append("empty_derivatives_rows")
    if len(mappings) < len(SYMBOLS):
        warnings.append("partial_vndirect_mapping")
    latest = [r for r in rows if r.get("date") == max([x.get("date") for x in rows], default=None)]
    required = ["future_close", "vn30_close", "basis", "fireant_volume", "open_interest"]
    missing = sorted({field for row in latest for field in required if row.get(field) is None})
    for field in missing:
        warnings.append(f"latest_missing_field:{field}")
    score = 0.45
    score += 0.25 if rows else 0
    score += 0.15 if len(mappings) >= 2 else 0
    score += 0.15 if not missing else max(0, 0.15 - 0.03 * len(missing))
    return round(min(score, 0.95), 2), warnings


def build_payload(symbols: list[str] | None = None, days: int = 14) -> dict[str, Any]:
    symbols = symbols or SYMBOLS
    end = datetime.now()
    start = end - timedelta(days=days)
    token = fireant_public_token()
    fireant_quotes = fetch_fireant_quotes(token, symbols, start, end)
    mappings, vnd_prices = fetch_vndirect(symbols)
    RAW.mkdir(parents=True, exist_ok=True)
    save_json(RAW / "fireant_quotes.redacted.json", fireant_quotes)
    save_json(RAW / "vndirect_derivatives.json", {"mappings": mappings, "prices": vnd_prices})
    rows = build_rows(fireant_quotes, mappings, vnd_prices, symbols)
    quality_score, warnings = quality(rows, mappings)
    return {
        "as_of": now_iso(),
        "status": "real_parsed" if rows else "empty",
        "source": ["FireAnt public dashboard historical-quotes", "VNDIRECT public derivative_mappings/derivative_prices"],
        "source_policy": "production_safe_public_no_secret; FireAnt token extracted at runtime and redacted from raw artifacts",
        "symbols": symbols,
        "mappings": mappings,
        "rows": rows,
        "quality_score": quality_score,
        "warnings": warnings,
        "field_policy": {
            "basis": "future_close - vn30_close",
            "basis_pct": "basis / vn30_close * 100",
            "oi_change": "daily open_interest difference per symbol from VNDIRECT",
            "long_short": "no explicit public long/short endpoint used; keep foreign/proprietary net fields separate",
        },
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Production-safe VN30 derivatives ingest")
    ap.add_argument("--out", default=str(OUT / "derivatives_live.vn.json"))
    ap.add_argument("--days", type=int, default=14)
    args = ap.parse_args()
    payload = build_payload(days=args.days)
    out = Path(args.out)
    save_json(out, payload)
    print(f"DERIVATIVES_LIVE_READY status={payload['status']} quality_score={payload['quality_score']} rows={len(payload['rows'])} warnings={len(payload['warnings'])}")
    print(f"JSON: {out}")
    return 0 if payload["status"] == "real_parsed" and payload["quality_score"] >= 0.7 else 1


if __name__ == "__main__":
    raise SystemExit(main())
