#!/usr/bin/env python
"""Live global macro ingest for InvestOS VN.

Public/no-secret sources only. Writes data_live/global_macro_live.json.
Partial data is allowed but all missing/failed fields are explicit warnings.
"""
from __future__ import annotations

import csv
import email.utils
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus
from urllib.request import Request, urlopen
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
LIVE = ROOT / "data_live"
RAW = LIVE / "raw" / "global_macro"
OUT = LIVE / "global_macro_live.json"

UA = "Mozilla/5.0 InvestOSVN/global-macro-ingest"

FRED_SERIES = {
    "fed_effective_rate": "DFF",
    "us_2y_yield": "DGS2",
    "us_10y_yield": "DGS10",
    "dxy": "DTWEXBGS",
    "brent_oil": "DCOILBRENTEU",
    "wti_oil": "DCOILWTICO",
    "gold_usd_oz": "GOLDAMGBD228NLBM",
    "vix": "VIXCLS",
}

RSS_SOURCES = [
    ("Federal Reserve press releases", "https://www.federalreserve.gov/feeds/press_all.xml", "fed"),
    ("Reuters Fed Google News", "https://news.google.com/rss/search?q=" + quote_plus("Federal Reserve FOMC interest rates when:7d") + "&hl=en-US&gl=US&ceid=US:en", "fed"),
    ("Oil geopolitics Google News", "https://news.google.com/rss/search?q=" + quote_plus("oil prices Middle East shipping sanctions war when:7d") + "&hl=en-US&gl=US&ceid=US:en", "oil_geopolitics"),
    ("Gold macro Google News", "https://news.google.com/rss/search?q=" + quote_plus("gold price dollar yields safe haven when:7d") + "&hl=en-US&gl=US&ceid=US:en", "gold"),
    ("US China trade war Google News", "https://news.google.com/rss/search?q=" + quote_plus("US China trade war tariffs export controls Vietnam supply chain when:14d") + "&hl=en-US&gl=US&ceid=US:en", "trade_war"),
    ("Geopolitical risk Google News", "https://news.google.com/rss/search?q=" + quote_plus("war geopolitical risk shipping sanctions markets when:7d") + "&hl=en-US&gl=US&ceid=US:en", "geopolitics"),
]


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def fetch(url: str, timeout: int = 25) -> bytes:
    req = Request(url, headers={"User-Agent": UA, "Accept": "text/html,application/xml,text/xml,text/csv,*/*"})
    with urlopen(req, timeout=timeout) as resp:
        return resp.read()


def parse_float(x: str | None) -> float | None:
    if x is None:
        return None
    x = str(x).strip()
    if not x or x == ".":
        return None
    try:
        return float(x)
    except ValueError:
        return None


def latest_fred(series: str) -> dict[str, Any]:
    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series}"
    raw = fetch(url)
    RAW.mkdir(parents=True, exist_ok=True)
    (RAW / f"fred_{series}.csv").write_bytes(raw)
    text = raw.decode("utf-8", errors="replace")
    rows = list(csv.DictReader(text.splitlines()))
    for row in reversed(rows):
        value = parse_float(row.get(series))
        if value is not None:
            return {"value": value, "date": row.get("observation_date"), "source": f"FRED:{series}", "url": url}
    raise RuntimeError(f"no numeric FRED value for {series}")


def parse_rss_date(text: str | None) -> str | None:
    if not text:
        return None
    try:
        return email.utils.parsedate_to_datetime(text).astimezone(timezone.utc).isoformat()
    except Exception:
        return text


def clean_title(text: str | None) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def fetch_rss(name: str, url: str, topic: str, limit: int = 6) -> tuple[list[dict[str, Any]], list[str]]:
    warnings: list[str] = []
    try:
        raw = fetch(url)
        RAW.mkdir(parents=True, exist_ok=True)
        safe = re.sub(r"[^a-z0-9_]+", "_", name.lower())[:60]
        (RAW / f"rss_{safe}.xml").write_bytes(raw)
        root = ET.fromstring(raw)
        items = []
        for item in root.findall(".//item")[:limit]:
            title = clean_title(item.findtext("title"))
            link = clean_title(item.findtext("link"))
            pub = parse_rss_date(item.findtext("pubDate"))
            if title:
                items.append({
                    "topic": topic,
                    "title": title,
                    "published_at": pub,
                    "url": link,
                    "source": name,
                    "confidence": 0.65 if "Google News" in name else 0.85,
                    "vn_transmission_channel": infer_vn_channel(topic, title),
                })
        return items, warnings
    except Exception as exc:
        warnings.append(f"rss_fetch_failed:{name}:{exc}")
        return [], warnings


def infer_vn_channel(topic: str, title: str) -> str:
    t = title.lower()
    if topic == "fed" or any(k in t for k in ["fed", "fomc", "rate", "yield", "dollar"]):
        return "USD/VND, foreign flow, equity discount rate, bank funding sentiment"
    if topic in {"oil_geopolitics", "geopolitics"} or any(k in t for k in ["oil", "shipping", "war", "sanction", "middle east"]):
        return "oil/import inflation, logistics cost, risk-off sentiment, energy sector"
    if topic == "gold" or "gold" in t:
        return "safe-haven demand, USD/yield expectations, domestic risk appetite proxy"
    if topic == "trade_war" or any(k in t for k in ["tariff", "trade", "export control", "china"]):
        return "Vietnam exports, industrial parks, electronics/textile supply chain relocation risk"
    return "global risk appetite and foreign flow into Vietnam equities"


def trend(current: float | None, prior: float | None) -> str | None:
    if current is None or prior is None:
        return None
    if current > prior:
        return "up"
    if current < prior:
        return "down"
    return "flat"


def fred_with_prior(series: str) -> dict[str, Any]:
    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series}"
    raw = fetch(url)
    RAW.mkdir(parents=True, exist_ok=True)
    (RAW / f"fred_{series}.csv").write_bytes(raw)
    rows = list(csv.DictReader(raw.decode("utf-8", errors="replace").splitlines()))
    vals = []
    for row in rows:
        v = parse_float(row.get(series))
        if v is not None:
            vals.append((row.get("observation_date"), v))
    if not vals:
        raise RuntimeError(f"no numeric FRED value for {series}")
    date, value = vals[-1]
    prior = vals[-6][1] if len(vals) >= 6 else (vals[-2][1] if len(vals) >= 2 else None)
    return {"value": value, "date": date, "source": f"FRED:{series}", "url": url, "prior_sample_value": prior, "trend_approx": trend(value, prior)}


def build_impact(ind: dict[str, Any], events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    impacts: list[dict[str, Any]] = []
    dxy = ind.get("dxy", {}).get("trend_approx")
    y10 = ind.get("us_10y_yield", {}).get("trend_approx")
    oil = ind.get("brent_oil", {}).get("trend_approx")
    gold = ind.get("gold_usd_oz", {}).get("trend_approx")
    if dxy == "up" or y10 == "up":
        impacts.append({"channel": "FX/rates", "vn_impact": "negative_bias", "detail": "DXY or US yields rising can pressure USD/VND, foreign flow, and equity valuation multiples.", "confidence": 0.7})
    if oil == "up":
        impacts.append({"channel": "oil/inflation", "vn_impact": "mixed_negative", "detail": "Oil rising can support oil & gas names but pressure transport, inflation expectation, and import costs.", "confidence": 0.65})
    if gold == "up":
        impacts.append({"channel": "safe_haven", "vn_impact": "risk_off_watch", "detail": "Gold rising often reflects safe-haven or lower-real-yield demand; check local risk appetite before increasing beta.", "confidence": 0.55})
    if any(e["topic"] in {"trade_war", "geopolitics", "oil_geopolitics"} for e in events):
        impacts.append({"channel": "headline/geopolitical", "vn_impact": "scenario_watch", "detail": "Trade-war/geopolitical headlines require sector mapping before acting: exporters, industrial parks, logistics, oil & gas, banks.", "confidence": 0.6})
    if not impacts:
        impacts.append({"channel": "global_macro", "vn_impact": "neutral_or_missing", "detail": "No strong directional impact inferred from available fields; keep source coverage warnings visible.", "confidence": 0.5})
    return impacts


def main() -> int:
    warnings: list[str] = []
    indicators: dict[str, Any] = {}
    for key, series in FRED_SERIES.items():
        try:
            indicators[key] = fred_with_prior(series)
        except Exception as exc:
            warnings.append(f"fred_fetch_failed:{key}:{series}:{exc}")
            indicators[key] = {"value": None, "source": f"FRED:{series}", "warning": "fetch_failed"}

    events: list[dict[str, Any]] = []
    sources: list[str] = [f"FRED:{s}" for s in FRED_SERIES.values()]
    for name, url, topic in RSS_SOURCES:
        items, ws = fetch_rss(name, url, topic)
        events.extend(items)
        warnings.extend(ws)
        if items:
            sources.append(name)

    coverage_required = ["fed_effective_rate", "us_2y_yield", "us_10y_yield", "dxy", "brent_oil", "wti_oil", "gold_usd_oz", "vix"]
    present = sum(1 for k in coverage_required if indicators.get(k, {}).get("value") is not None)
    event_topics = sorted(set(e["topic"] for e in events))
    quality_score = round(min(0.98, 0.45 + 0.045 * present + 0.025 * len(event_topics)), 2)
    if present < len(coverage_required):
        warnings.append(f"partial_indicator_coverage:{present}/{len(coverage_required)}")
    if len(event_topics) < 3:
        warnings.append(f"partial_news_topic_coverage:{event_topics}")

    payload = {
        "as_of": now_iso(),
        "source": sorted(set(sources)),
        "quality_score": quality_score,
        "status": "live_global_macro_layer" if quality_score >= 0.8 else "partial_live_global_macro_layer",
        "indicators": indicators,
        "events": events[:30],
        "vn_equity_impact": build_impact(indicators, events),
        "sector_impact_map": {
            "banks": ["USD/VND pressure", "US yields", "foreign flow", "funding sentiment"],
            "real_estate": ["global rates", "risk appetite", "credit/liquidity sensitivity"],
            "steel_materials": ["China demand", "trade barriers", "coal/iron ore/oil"],
            "exporters": ["US/EU demand", "tariffs/export controls", "USD/VND", "shipping cost"],
            "oil_gas": ["Brent/WTI", "Middle East risk premium", "sanctions"],
            "gold_sensitive_sentiment": ["safe-haven demand", "FX/inflation expectations"],
        },
        "warnings": warnings,
    }
    LIVE.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"GLOBAL_MACRO_LIVE_READY quality_score={quality_score} events={len(events)} warnings={len(warnings)}")
    print(f"JSON: {OUT}")
    return 0 if quality_score >= 0.7 else 2


if __name__ == "__main__":
    raise SystemExit(main())
