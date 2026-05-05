#!/usr/bin/env python
"""Refresh real news_live.vn.json from configured public sources.

No mock/sample fallback. Produces validated title/url/timestamp/dedupe_key items.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.parse import urljoin

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data_live" / "news_live.vn.json"
RAW = ROOT / "data_live" / "raw"
TE_CACHE = RAW / "te_news_fetch_text.txt"
SOURCES = [
    {"name": "Trading Economics", "url": "https://tradingeconomics.com/vietnam/news"},
    {"name": "PNJ investor relations", "url": "https://www.pnj.com.vn/quan-he-co-dong/"},
    {"name": "CafeF lãi suất - tỷ giá", "url": "https://cafef.vn/du-lieu/lai-suat-ngan-hang.chn"},
]
DIRTY = re.compile(r"\b(mock|sample|placeholder|TBD)\b", re.I)


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def read_text_cache(path: Path) -> str:
    if not path.exists():
        raise FileNotFoundError(str(path))
    age_min = (datetime.now().astimezone() - datetime.fromtimestamp(path.stat().st_mtime).astimezone()).total_seconds() / 60
    if age_min > 1440:
        raise RuntimeError(f"stale_te_news_cache>{int(age_min)}m")
    return path.read_text(encoding="utf-8", errors="replace")


def fetch(url: str) -> str:
    req = Request(url, headers={"User-Agent": "Mozilla/5.0 InvestOSVN/news-refresh", "Accept": "text/html,*/*;q=0.8"})
    with urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8", errors="replace")


def strip(text: str) -> str:
    text = re.sub(r"<script.*?</script>", " ", text, flags=re.S | re.I)
    text = re.sub(r"<style.*?</style>", " ", text, flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def extract_te_text_items(source: dict[str, str], text: str, limit: int = 5) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    for line in [x.strip(" -•\t") for x in text.splitlines()]:
        if len(line) < 18 or DIRTY.search(line):
            continue
        if not re.search(r"Vietnam|VN|VND|stock|market|interest|inflation|econom", line, re.I):
            continue
        key = hashlib.sha1((source["url"] + line).encode("utf-8")).hexdigest()
        items.append({
            "title": line[:220],
            "url": source["url"],
            "timestamp": now_iso(),
            "published_at": now_iso(),
            "source": source["name"],
            "source_mode": "extracted_text_cache",
            "dedupe_key": key,
            "tickers": [],
            "summary": line[:240],
        })
        if len(items) >= limit:
            break
    return items


def extract_links(source: dict[str, str], html: str, limit: int = 5) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    base = source["url"]
    for m in re.finditer(r'<a\s+[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', html, re.S | re.I):
        url = urljoin(base, m.group(1))
        title = strip(m.group(2))
        if len(title) < 12 or DIRTY.search(title) or url.startswith("javascript:"):
            continue
        if source["name"] == "Trading Economics" and "tradingeconomics.com" not in url:
            continue
        if source["name"].startswith("PNJ") and "pnj" not in url.lower():
            continue
        if source["name"].startswith("CafeF") and "cafef.vn" not in url:
            continue
        dedupe_key = hashlib.sha1((url or title).encode("utf-8")).hexdigest()
        items.append({
            "title": title[:220],
            "url": url,
            "timestamp": now_iso(),
            "published_at": now_iso(),
            "source": source["name"],
            "dedupe_key": dedupe_key,
            "tickers": ["PNJ"] if "pnj" in (title + url).lower() else [],
            "summary": title[:240],
        })
        if len(items) >= limit:
            break
    if not items:
        text = strip(html)
        title = text[:160]
        if len(title) >= 12 and not DIRTY.search(title):
            items.append({
                "title": title,
                "url": base,
                "timestamp": now_iso(),
                "published_at": now_iso(),
                "source": source["name"],
                "dedupe_key": hashlib.sha1(base.encode("utf-8")).hexdigest(),
                "tickers": ["PNJ"] if "pnj" in base.lower() else [],
                "summary": title,
            })
    return items


def validate(items: list[dict[str, str]]) -> list[str]:
    gaps: list[str] = []
    seen: set[str] = set()
    for i, item in enumerate(items):
        for key in ["title", "url", "timestamp", "dedupe_key"]:
            if not item.get(key):
                gaps.append(f"item_{i}_missing_{key}")
        if DIRTY.search(json.dumps(item, ensure_ascii=False)):
            gaps.append(f"item_{i}_dirty_term")
        key = item.get("dedupe_key")
        if key in seen:
            gaps.append(f"duplicate:{key}")
        seen.add(key)
    if not items:
        gaps.append("empty_news")
    return gaps


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--allow-partial", action="store_true")
    args = ap.parse_args()
    all_items: list[dict[str, str]] = []
    meta: list[dict[str, str]] = []
    warnings: list[str] = []
    for src in SOURCES:
        try:
            html = fetch(src["url"])
            meta.append({"name": src["name"], "url": src["url"], "fetched_at": now_iso(), "sha256": hashlib.sha256(html.encode("utf-8")).hexdigest()})
            all_items.extend(extract_links(src, html, limit=4))
        except Exception as exc:
            if src["name"] == "Trading Economics":
                try:
                    text = read_text_cache(TE_CACHE)
                    sha = hashlib.sha256(text.encode("utf-8")).hexdigest()
                    all_items.extend(extract_te_text_items(src, text, limit=4))
                    warnings.append(f"{src['name']}:provider_down:{exc};used_extracted_text_cache")
                    meta.append({"name": src["name"], "url": str(TE_CACHE), "fallback_from": src["url"], "fetched_at": now_iso(), "sha256": sha, "source_mode": "extracted_text_cache"})
                    continue
                except Exception as cache_exc:
                    warnings.append(f"{src['name']}:provider_down:{exc};cache:{cache_exc}")
                    meta.append({"name": src["name"], "url": src["url"], "fetched_at": now_iso(), "error": f"{exc}; cache:{cache_exc}"})
                    continue
            warnings.append(f"{src['name']}:provider_down:{exc}")
            meta.append({"name": src["name"], "url": src["url"], "fetched_at": now_iso(), "error": str(exc)})
    deduped = list({item["dedupe_key"]: item for item in all_items}.values())
    gaps = validate(deduped)
    if gaps or (warnings and not args.allow_partial):
        print("NEWS_REFRESH_FAILED")
        for x in warnings + gaps:
            print("-", x)
        return 1
    payload = {"as_of": now_iso(), "source": [m["name"] for m in meta], "source_meta": meta, "items": deduped, "warnings": warnings, "status": "real_parsed"}
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    print("NEWS_REFRESH_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
