#!/usr/bin/env python
"""Refresh Trading Economics Vietnam news extracted-text cache.

No fake fallback: cache must contain Vietnam/news-like real text.
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

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data_live" / "raw"
OUT = RAW / "te_news_fetch_text.txt"
META = RAW / "te_news_fetch_text.meta.json"
URL = "https://tradingeconomics.com/vietnam/news"


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def fetch(url: str) -> str:
    req = Request(url, headers={"User-Agent": "Mozilla/5.0 InvestOSVN/te-news-cache", "Accept": "text/html,text/plain,*/*;q=0.8"})
    with urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8", errors="replace")


def strip_html(text: str) -> str:
    text = re.sub(r"<script.*?</script>", " ", text, flags=re.S | re.I)
    text = re.sub(r"<style.*?</style>", " ", text, flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", "\n", text)
    return re.sub(r"[ \t]+", " ", text)


def validate(text: str) -> list[str]:
    gaps: list[str] = []
    if len(text.strip()) < 80:
        gaps.append("te_news_text_too_short")
    if not re.search(r"Vietnam|Viet Nam|VN|VND", text, re.I):
        gaps.append("missing_vietnam_marker")
    if not re.search(r"news|stock|market|econom|interest|inflation|currency", text, re.I):
        gaps.append("missing_news_macro_marker")
    if re.search(r"\b(mock|sample|placeholder|TBD)\b", text, re.I):
        gaps.append("dirty_term")
    return gaps


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--from-file", help="Browser/web_fetch extracted text file when direct HTTP is 403")
    args = ap.parse_args()
    provider_error = None
    if args.from_file:
        text = Path(args.from_file).read_text(encoding="utf-8", errors="replace")
        source_mode = "text_file"
        source_url = str(Path(args.from_file))
    else:
        try:
            text = strip_html(fetch(URL))
            source_mode = "direct_http"
            source_url = URL
        except Exception as exc:
            provider_error = str(exc)
            if not OUT.exists():
                print("TE_NEWS_CACHE_REFRESH_FAILED")
                print("-", f"provider_down:{provider_error}")
                print("- no_existing_cache")
                return 2
            text = OUT.read_text(encoding="utf-8", errors="replace")
            source_mode = "revalidated_existing_cache"
            source_url = URL
    gaps = validate(text)
    if gaps:
        print("TE_NEWS_CACHE_REFRESH_FAILED")
        if provider_error:
            print("-", f"provider_down:{provider_error}")
        for gap in gaps:
            print("-", gap)
        return 2
    RAW.mkdir(parents=True, exist_ok=True)
    OUT.write_text(text, encoding="utf-8")
    sha = hashlib.sha256(text.encode("utf-8")).hexdigest()
    meta = {"as_of": now_iso(), "source": "Trading Economics Vietnam news", "url": source_url, "source_mode": source_mode, "sha256": sha, "bytes": len(text.encode("utf-8"))}
    if provider_error:
        meta["warning"] = f"provider_down:{provider_error};used_existing_validated_cache"
    META.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(meta, ensure_ascii=False, indent=2))
    print("TE_NEWS_CACHE_REFRESH_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
