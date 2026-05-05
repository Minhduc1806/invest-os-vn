#!/usr/bin/env python
"""Refresh Trading Economics Vietnam interest-rate extracted-text cache.

Raw HTTP often returns 403. This script uses a supplied extracted text file or URL
text fetch, validates policy-rate text, then writes data_live/raw/te_interest_rate_fetch_text.txt.
No fake fallback.
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
CACHE = ROOT / "data_live" / "raw" / "te_interest_rate_fetch_text.txt"
META = ROOT / "data_live" / "raw" / "te_interest_rate_fetch_text.meta.json"
DEFAULT_URL = "https://tradingeconomics.com/vietnam/interest-rate"


def fetch_text(url: str) -> str:
    req = Request(url, headers={"User-Agent": "Mozilla/5.0 InvestOSVN/phase4-cache-refresh", "Accept": "text/html,text/plain;q=0.9,*/*;q=0.8"})
    with urlopen(req, timeout=30) as resp:
        raw = resp.read().decode("utf-8", errors="replace")
    text = re.sub(r"<script.*?</script>", " ", raw, flags=re.S | re.I)
    text = re.sub(r"<style.*?</style>", " ", text, flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def extract_rate(text: str) -> float | None:
    patterns = [
        r"benchmark interest rate in Vietnam was last recorded at\s+([0-9]+(?:[,.][0-9]+)?)\s+percent",
        r"Interest Rate\s+([0-9]+(?:[,.][0-9]+)?)\s+([0-9]+(?:[,.][0-9]+)?)\s+percent\s+[A-Za-z]{3}\s+\d{4}",
    ]
    for pat in patterns:
        m = re.search(pat, text, re.I)
        if m:
            v = float(m.group(1).replace(",", "."))
            if 0 <= v <= 30:
                return v
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--from-file", help="Browser/web_fetch extracted text file. Preferred when direct TE HTTP is 403.")
    ap.add_argument("--url", default=DEFAULT_URL, help="URL to try via plain HTTP text extraction.")
    args = ap.parse_args()

    if args.from_file:
        text = Path(args.from_file).read_text(encoding="utf-8")
        source_mode = "manual_extracted_text_file"
        source = args.from_file
    else:
        text = fetch_text(args.url)
        source_mode = "http_text_extract"
        source = args.url

    value = extract_rate(text)
    if value is None:
        print("TE_INTEREST_CACHE_REFRESH_FAILED: cannot extract validated interest rate", file=sys.stderr)
        return 1

    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(text, encoding="utf-8")
    sha = hashlib.sha256(text.encode("utf-8")).hexdigest()
    meta = {
        "as_of": datetime.now().astimezone().isoformat(timespec="seconds"),
        "source": source,
        "source_mode": source_mode,
        "cache_path": str(CACHE.relative_to(ROOT)),
        "sha256": sha,
        "validated_policy_rate_pct": value,
    }
    META.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(meta, ensure_ascii=False, indent=2))
    print("TE_INTEREST_CACHE_REFRESH_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
