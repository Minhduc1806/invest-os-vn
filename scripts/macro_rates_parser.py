#!/usr/bin/env python
"""Stable macro/rates parser scaffold for Phase 4 real-only data.

No fake fallback: required missing fields make command fail.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime
from html import unescape
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
LIVE = ROOT / "data_live"
OUT = LIVE / "macro_rates_live.vn.json"
RAW = LIVE / "raw"

SOURCES = [
    {"name": "Trading Economics", "url": "https://tradingeconomics.com/vietnam/stock-market", "kind": "macro_indicators"},
    {"name": "Trading Economics interest rate", "url": "https://tradingeconomics.com/vietnam/interest-rate", "kind": "te_interest_rate"},
    {"name": "World Bank CPI", "url": "https://api.worldbank.org/v2/country/VN/indicator/FP.CPI.TOTL.ZG?format=json&per_page=5", "kind": "worldbank_inflation"},
    {"name": "World Bank unemployment", "url": "https://api.worldbank.org/v2/country/VN/indicator/SL.UEM.TOTL.ZS?format=json&per_page=5", "kind": "worldbank_unemployment"},
    {"name": "SBV interest rates", "url": "https://www.sbv.gov.vn/webcenter/portal/vi/menu/trangchu/lstk", "kind": "sbv_policy_rates"},
    {"name": "SBV exchange rates", "url": "https://www.sbv.gov.vn/webcenter/portal/vi/menu/rm/tygia", "kind": "sbv_fx_rates"},
    {"name": "CafeF", "url": "https://cafef.vn/du-lieu/lai-suat-ngan-hang.chn", "kind": "rates_fx"},
    {"name": "WebGia deposit rates", "url": "https://webgia.com/lai-suat/", "kind": "deposit_rates"},
    {"name": "WebGia USD FX", "url": "https://webgia.com/ty-gia/usd/", "kind": "webgia_usd_fx"},
    {"name": "Vietcombank exchange rates", "url": "https://portal.vietcombank.com.vn/UserControls/TVPortal.TyGia/pXML.aspx", "kind": "vcb_fx_rates"},
]

def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")

def fetch(url: str) -> tuple[str, str]:
    req = Request(url, headers={"User-Agent": "Mozilla/5.0 InvestOSVN/phase4-real-parser", "Accept": "text/html,application/json;q=0.9,*/*;q=0.8"})
    with urlopen(req, timeout=30) as resp:
        raw = resp.read()
    sha = hashlib.sha256(raw).hexdigest()
    return raw.decode("utf-8", errors="replace"), sha

NB_CHARS = set("0123456789,.")
def decode_webgia_nb(value: str) -> float | None:
    if not value:
        return None
    # WebGia nb is noisy. Accept only explicit decimal tokens x,y / x.y / x2cy.
    # Reject standalone integers like 30 because those are often noise from encoded spans.
    candidates = re.findall(r"([0-9]{1,2}(?:2c|,|\.)[0-9]{1,2})", value)
    nums: list[float] = []
    for c in candidates:
        c = c.replace("2c", ",")
        v = vn_num(c)
        if v is not None and 0 <= v <= 15:
            nums.append(v)
    return nums[-1] if nums else None

def html_text(cell: str) -> str:
    return unescape(re.sub(r"<[^>]+>", " ", cell)).strip()

def vn_num(text: str) -> float | None:
    s = text.strip().replace("%", "")
    s = re.sub(r"[^0-9,.-]", "", s)
    if not s:
        return None
    if "," in s and "." in s:
        if s.rfind(",") < s.rfind("."):
            s = s.replace(",", "")
        else:
            s = s.replace(".", "").replace(",", ".")
    elif "," in s:
        parts = s.split(",")
        s = "".join(parts) if len(parts[-1]) == 3 and len(parts) > 1 else s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None

def pct_range(v: float | None) -> bool:
    return v is not None and 0 <= v <= 30

def fx_range(v: float | None) -> bool:
    return v is not None and 10000 <= v <= 50000

def strip_html(html: str) -> str:
    text = re.sub(r"<script.*?</script>", " ", html, flags=re.S | re.I)
    text = re.sub(r"<style.*?</style>", " ", text, flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text)

def parse_webgia_deposit_rates(html: str) -> dict[str, Any]:
    tenors = ["0m", "1m", "3m", "6m", "9m", "12m", "13m", "18m", "24m", "36m"]
    by_bank: dict[str, dict[str, float]] = {}
    table = re.search(r'<section id="lai_suat_tiet_kiem_tai_quay".*?<tbody>(.*?)</tbody>', html, re.S | re.I)
    if not table:
        table = re.search(r'<tbody>(.*?)</tbody>', html, re.S | re.I)
    if not table:
        return by_bank
    for row in re.findall(r"<tr>(.*?)</tr>", table.group(1), re.S | re.I):
        cells = re.findall(r"(<td[^>]*>.*?</td>)", row, re.S | re.I)
        if len(cells) < 11:
            continue
        bank = html_text(cells[0]).split()[-1] if html_text(cells[0]) else ""
        if not bank:
            continue
        rates: dict[str, float] = {}
        for tenor, cell in zip(tenors, cells[1:11]):
            m = re.search(r'nb="([^"]+)"', cell)
            v = decode_webgia_nb(m.group(1)) if m else vn_num(html_text(cell))
            if pct_range(v):
                rates[tenor] = v
        if rates:
            by_bank[bank] = rates
    return by_bank

def parse_webgia_usd_fx(html: str) -> float | None:
    # Prefer rows around USD/VND, ignore unlabeled numbers.
    text = strip_html(html)
    for pat in [r"USD\s+[^0-9]{0,80}([0-9]{2,3}(?:[.,][0-9]{3})+(?:[.,][0-9]+)?)", r"Đô la Mỹ\s+[^0-9]{0,80}([0-9]{2,3}(?:[.,][0-9]{3})+(?:[.,][0-9]+)?)"]:
        for m in re.finditer(pat, text, re.I):
            v = vn_num(m.group(1))
            if v is not None and 10000 <= v <= 50000:
                return v
    return None

def parse_vcb_usd_fx(xml: str) -> float | None:
    # Vietcombank XML has CurrencyCode="USD" with Transfer/Sell. Prefer Transfer, then Sell.
    row = re.search(r'<Exrate[^>]*CurrencyCode="USD"[^>]*/?>', xml, re.I)
    if not row:
        row = re.search(r'<Exrate[^>]*CurrencyName="[^"]*USD[^"]*"[^>]*/?>', xml, re.I)
    if not row:
        return None
    attrs = row.group(0)
    for key in ["Transfer", "Sell", "Buy"]:
        m = re.search(key + r'="([0-9.,]+)"', attrs, re.I)
        v = vn_num(m.group(1)) if m else None
        if v is not None and 10000 <= v <= 50000:
            return v
    return None

def parse_sbv_fx_rate(text: str) -> float | None:
    for pat in [r"USD\s*[/]??\s*VND[^0-9]{0,120}([0-9]{2,3}(?:[.,][0-9]{3})+(?:[.,][0-9]+)?)", r"Đô la Mỹ[^0-9]{0,120}([0-9]{2,3}(?:[.,][0-9]{3})+(?:[.,][0-9]+)?)"]:
        m = re.search(pat, text, re.I)
        v = vn_num(m.group(1)) if m else None
        if v is not None and 10000 <= v <= 50000:
            return v
    return None

def parse_sbv_policy_rate(text: str) -> dict[str, Any] | None:
    # SBV Liferay menu page often loads homepage chrome; parse actual table/article if present.
    clean = strip_html(text) if "<" in text else text
    patterns = [
        r"lãi suất tái cấp vốn[^0-9]{0,120}([0-9]+(?:[,.][0-9]+)?)\s*%",
        r"tái cấp vốn[^0-9]{0,120}([0-9]+(?:[,.][0-9]+)?)\s*%",
        r"refinancing rate[^0-9]{0,120}([0-9]+(?:[,.][0-9]+)?)\s*%",
        r"lãi suất điều hành[^0-9]{0,120}([0-9]+(?:[,.][0-9]+)?)\s*%",
    ]
    for pat in patterns:
        m = re.search(pat, clean, re.I)
        v = vn_num(m.group(1)) if m else None
        if pct_range(v):
            return {"name": "Vietnam policy rate", "value": v, "unit": "percent", "reference_period": "latest", "source": "SBV", "timestamp": now_iso()}
    return None

def parse_te_interest_rate(text: str) -> dict[str, Any] | None:
    clean = strip_html(text) if "<" in text else text
    patterns = [
        r"benchmark interest rate in Vietnam was last recorded at\s+([0-9]+(?:[,.][0-9]+)?)\s+percent",
        r"Interest Rate\s+([0-9]+(?:[,.][0-9]+)?)\s+([0-9]+(?:[,.][0-9]+)?)\s+percent\s+([A-Za-z]{3}\s+\d{4})",
    ]
    for pat in patterns:
        m = re.search(pat, clean, re.I)
        v = vn_num(m.group(1)) if m else None
        if pct_range(v):
            ref = m.group(3) if m and m.lastindex and m.lastindex >= 3 else "latest"
            return {"name": "Vietnam Interest Rate", "value": v, "unit": "percent", "reference_period": ref, "source": "Trading Economics / State Bank of Vietnam", "timestamp": now_iso()}
    return None

def parse_worldbank_json(text: str, name: str, source: str) -> dict[str, Any] | None:
    try:
        payload = json.loads(text)
        rows = payload[1] if isinstance(payload, list) and len(payload) > 1 else []
        for row in rows:
            v = row.get("value")
            if pct_range(v):
                return {"name": name, "value": float(v), "unit": "percent", "reference_period": str(row.get("date")), "source": source, "timestamp": now_iso()}
    except Exception:
        return None
    return None

def parse_tradingeconomics(text: str) -> list[dict[str, Any]]:
    specs = [
        ("Vietnam Inflation Rate", "percent"),
        ("Vietnam Interest Rate", "percent"),
        ("Vietnam Unemployment Rate", "percent"),
    ]
    series: list[dict[str, Any]] = []
    for name, unit in specs:
        m = re.search(re.escape(name) + r"\s+([0-9]+(?:\.[0-9]+)?)\s+([0-9]+(?:\.[0-9]+)?)\s+" + re.escape(unit) + r"\s+([A-Za-z]{3}\s+\d{4})", text)
        if m:
            value = vn_num(m.group(1))
            if pct_range(value):
                series.append({"name": name, "value": value, "unit": unit, "reference_period": m.group(3), "source": "Trading Economics", "timestamp": now_iso()})
    return series

def parse_source(src: dict[str, str]) -> tuple[dict[str, Any], list[str]]:
    warnings: list[str] = []
    if src.get("kind") == "te_interest_rate_text_file":
        html = Path(src["url"]).read_text(encoding="utf-8")
        sha = hashlib.sha256(html.encode("utf-8")).hexdigest()
        meta = {"name": src["name"], "url": src["url"], "fetched_at": now_iso(), "sha256": sha, "source_mode": "text_file"}
        (RAW / f"macro_{src['kind']}.html").write_text(html, encoding="utf-8")
        return {"meta": meta, "text": html}, warnings
    try:
        html, sha = fetch(src["url"])
    except Exception as exc:
        return {"name": src["name"], "url": src["url"], "fetched_at": now_iso(), "sha256": None, "error_code": "provider_down", "error": str(exc)}, [f"{src['name']}:provider_down:{exc}"]
    RAW.mkdir(parents=True, exist_ok=True)
    (RAW / f"macro_{src['kind']}.html").write_text(html, encoding="utf-8")
    meta = {"name": src["name"], "url": src["url"], "fetched_at": now_iso(), "sha256": sha}
    return {"meta": meta, "text": strip_html(html)}, warnings

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--allow-partial", action="store_true")
    ap.add_argument("--te-interest-text-file", help="Secondary extracted text for Trading Economics interest-rate page when direct HTTP is 403")
    ap.add_argument("--merge-live", action="store_true", help="Write production data_live/macro_rates_live.vn.json")
    args = ap.parse_args()
    sources_meta: list[dict[str, Any]] = []
    if args.te_interest_text_file:
        SOURCES.insert(1, {"name": "Trading Economics interest rate text", "url": str(Path(args.te_interest_text_file)), "kind": "te_interest_rate_text_file"})
    warnings: list[str] = []
    series: list[dict[str, Any]] = []
    deposit_rates: dict[str, Any] = {}
    usd_vnd: float | None = None
    policy_alt: dict[str, Any] | None = None
    for src in SOURCES:
        parsed, warn = parse_source(src)
        warnings.extend(warn)
        if "meta" in parsed:
            sources_meta.append(parsed["meta"])
            text = parsed["text"]
            raw = (RAW / f"macro_{src['kind']}.html").read_text(encoding="utf-8")
            if src["kind"] == "macro_indicators":
                series.extend(parse_tradingeconomics(text))
            elif src["kind"] in {"te_interest_rate", "te_interest_rate_text_file"}:
                item = parse_te_interest_rate(text)
                if item and not any(x["name"] == item["name"] for x in series):
                    series.append(item)
            elif src["kind"] == "worldbank_inflation":
                item = parse_worldbank_json(raw, "Vietnam Inflation Rate", "World Bank")
                if item and not any(x["name"] == item["name"] for x in series):
                    series.append(item)
            elif src["kind"] == "worldbank_unemployment":
                item = parse_worldbank_json(raw, "Vietnam Unemployment Rate", "World Bank")
                if item and not any(x["name"] == item["name"] for x in series):
                    series.append(item)
            elif src["kind"] == "sbv_policy_rates":
                policy_alt = parse_sbv_policy_rate(text)
            elif src["kind"] == "sbv_fx_rates":
                usd_vnd = usd_vnd or parse_sbv_fx_rate(text)
            elif src["kind"] == "deposit_rates":
                deposit_rates = parse_webgia_deposit_rates(raw)
            elif src["kind"] == "webgia_usd_fx":
                usd_vnd = usd_vnd or parse_webgia_usd_fx(raw)
            elif src["kind"] == "vcb_fx_rates":
                usd_vnd = usd_vnd or parse_vcb_usd_fx(raw)
        else:
            sources_meta.append(parsed)
    policy = next((x for x in series if x["name"] in {"Vietnam Interest Rate", "Vietnam policy rate"}), None) or policy_alt
    if policy and not any(x["name"] == policy["name"] for x in series):
        series.append(policy)
    inflation = next((x for x in series if x["name"] == "Vietnam Inflation Rate"), None)
    missing = []
    if not policy:
        missing.append("policy_rate")
    if not inflation:
        missing.append("inflation")
    if not deposit_rates:
        missing.append("deposit_rates_by_bank_tenor")
    if usd_vnd is None:
        missing.append("usd_vnd")
    out = {
        "as_of": now_iso(),
        "source": sources_meta,
        "rates": {
            "policy_rate_pct": {"value": policy.get("value") if policy else None, "unit": "percent", "source": policy.get("source") if policy else "Trading Economics/SBV", "timestamp": now_iso()},
            "deposit_rates": {"unit": "%/year", "by_bank": deposit_rates, "source": "WebGia", "timestamp": now_iso()},
            "usd_vnd": {"value": usd_vnd, "unit": "VND/USD", "source": "CafeF/SBV", "timestamp": now_iso()},
        },
        "series": series,
        "parse_quality": {"required_passed": not missing, "missing_fields": missing, "warnings": warnings},
        "quality_score": 0.95 if not missing else 0.7,
        "status": "real_parsed" if not missing else "real_parsed_partial_required_missing",
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.merge_live:
        OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print(json.dumps(out, ensure_ascii=False, indent=2))
    if missing and not args.allow_partial:
        return 2
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
