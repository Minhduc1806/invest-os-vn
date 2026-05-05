#!/usr/bin/env python
"""Extract Vietnam bond yield and currencies from Trading Economics pages.

Direct raw HTML first. If provider blocks, pass --text-file snapshots from browser/web_fetch.
No fake fallback: required missing fields return non-zero.
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
LIVE = ROOT / "data_live"
RAW = LIVE / "raw"
OUT = LIVE / "tradingeconomics_macro_live.vn.json"
BOND_URL = "https://tradingeconomics.com/vietnam/government-bond-yield"
CURR_URL = "https://tradingeconomics.com/currencies"

def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")

def fetch(url: str) -> tuple[str, str, str | None]:
    try:
        req = Request(url, headers={"User-Agent": "Mozilla/5.0 InvestOSVN/te-extract", "Accept": "text/html,*/*"})
        with urlopen(req, timeout=30) as resp:
            raw = resp.read()
        return raw.decode("utf-8", errors="replace"), hashlib.sha256(raw).hexdigest(), None
    except Exception as exc:
        return "", "", str(exc)

def num(s: str | None) -> float | None:
    if not s:
        return None
    x = re.sub(r"[^0-9,.-]", "", s)
    if "," in x and "." in x:
        x = x.replace(".", "").replace(",", ".")
    elif "," in x:
        x = x.replace(",", ".")
    try:
        return float(x)
    except ValueError:
        return None

def strip_html(html: str) -> str:
    text = re.sub(r"<script.*?</script>", " ", html, flags=re.S | re.I)
    text = re.sub(r"<style.*?</style>", " ", text, flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text)

def parse_bond(text: str) -> tuple[dict[str, object], list[dict[str, object]]]:
    bond: dict[str, object] = {}
    m = re.search(r"yield on Vietnam 10Y Bond Yield (?:rose|fell|was|increased|decreased).*?to\s+([0-9.]+)%\s+on\s+([A-Za-z]+\s+\d{1,2},\s+\d{4}).*?marking a\s+([0-9.-]+)\s+percentage points", text, re.I)
    if m:
        v, ch = num(m.group(1)), num(m.group(3))
        if v is not None and 0 <= v <= 30:
            bond = {"value": v, "unit": "percent", "change_pp": ch, "date_text": m.group(2), "source": "Trading Economics"}
    series: list[dict[str, object]] = []
    for name in ["Vietnam Inflation Rate", "Vietnam Interest Rate", "Vietnam Unemployment Rate"]:
        r = re.search(re.escape(name) + r"\s+([0-9.]+)\s+([0-9.]+)\s+percent\s+([A-Za-z]{3}\s+\d{4})", text)
        if r:
            v = num(r.group(1))
            if v is not None and 0 <= v <= 30:
                series.append({"name": name, "value": v, "previous": num(r.group(2)), "unit": "percent", "reference_period": r.group(3), "source": "Trading Economics", "timestamp": now_iso()})
    return bond, series

def parse_currencies(html_or_text: str, targets: list[str]) -> tuple[dict[str, object], list[str]]:
    warnings: list[str] = []
    out: dict[str, object] = {}
    # Raw HTML/scripts often include pair labels near numeric fields. Keep strict: never map unlabeled readability rows.
    for pair in targets:
        patterns = [
            pair + r".{0,300}?([0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]+)?|[0-9]+\.[0-9]+)\s+(-?[0-9.]+%)\s+(-?[0-9.]+%)\s+(May/\d{2}|[A-Za-z]{3}/\d{2})",
            pair.replace("USD", "USD/") + r".{0,300}?([0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]+)?|[0-9]+\.[0-9]+)",
        ]
        found = None
        for pat in patterns:
            m = re.search(pat, html_or_text, re.I | re.S)
            if m:
                found = m
                break
        if found:
            value = num(found.group(1))
            if value is not None:
                out[pair] = {"value": value, "source": "Trading Economics", "timestamp": now_iso()}
        else:
            warnings.append(f"{pair}:currency_pair_labels_missing")
    return out, warnings

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--targets", default="USDVND,EURUSD,USDJPY,USDCNY")
    ap.add_argument("--bond-text-file")
    ap.add_argument("--currencies-text-file")
    ap.add_argument("--allow-partial", action="store_true")
    args = ap.parse_args()
    RAW.mkdir(parents=True, exist_ok=True)
    sources = []
    warnings: list[str] = []

    if args.bond_text_file:
        bond_html = Path(args.bond_text_file).read_text(encoding="utf-8")
        bond_sha = hashlib.sha256(bond_html.encode("utf-8")).hexdigest()
        bond_err = None
        source_mode = "text_file"
    else:
        bond_html, bond_sha, bond_err = fetch(BOND_URL)
        source_mode = "raw_http"
    if bond_html:
        (RAW / "tradingeconomics_bond_yield.html").write_text(bond_html, encoding="utf-8")
    if bond_err:
        warnings.append(f"bond:provider_down:{bond_err}")
    sources.append({"name": "Trading Economics", "url": BOND_URL, "fetched_at": now_iso(), "sha256": bond_sha or None, "source_mode": source_mode, "error": bond_err})

    if args.currencies_text_file:
        curr_html = Path(args.currencies_text_file).read_text(encoding="utf-8")
        curr_sha = hashlib.sha256(curr_html.encode("utf-8")).hexdigest()
        curr_err = None
        curr_mode = "text_file"
    else:
        curr_html, curr_sha, curr_err = fetch(CURR_URL)
        curr_mode = "raw_http"
    if curr_html:
        (RAW / "tradingeconomics_currencies.html").write_text(curr_html, encoding="utf-8")
    if curr_err:
        warnings.append(f"currencies:provider_down:{curr_err}")
    sources.append({"name": "Trading Economics", "url": CURR_URL, "fetched_at": now_iso(), "sha256": curr_sha or None, "source_mode": curr_mode, "error": curr_err})

    bond, series = parse_bond(strip_html(bond_html) if "<" in bond_html else bond_html)
    currencies, cw = parse_currencies(curr_html, [x.strip().upper() for x in args.targets.split(",") if x.strip()])
    warnings.extend(cw)
    missing = []
    if not bond:
        missing.append("VN10Y.value")
    if "USDVND" not in currencies:
        missing.append("USDVND.value")
    out = {"as_of": now_iso(), "source": sources, "bond_yields": {"VN10Y": bond}, "currencies": currencies, "series": series, "parse_quality": {"required_passed": not missing, "missing_fields": missing, "warnings": warnings}}
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if (not missing or args.allow_partial) else 2

if __name__ == "__main__":
    raise SystemExit(main())
