#!/usr/bin/env python
"""Validate Phase 5 real-only generated reports.

Checks report JSON/MD outputs for mock/placeholder leakage, source/as_of, and
forbidden assumed leadership language unless structured evidence exists.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REPORTS = [
    ("portfolio_daily_advice", ROOT / "outputs" / "portfolio_daily.json", ROOT / "outputs" / "portfolio_daily.md"),
    ("eod_market_brief", ROOT / "outputs" / "eod_market_brief.json", ROOT / "outputs" / "eod_market_brief.md"),
    ("stock_signal_scan", ROOT / "outputs" / "stock_signal_scan_investable.json", ROOT / "outputs" / "stock_signal_report_investable.md"),
]
DIRTY_TERMS = ["mock", "placeholder", "sample", "TBD"]
LEADERSHIP_TERMS = ["dẫn dắt", "mạnh nhất", "dòng tiền lớn nhất"]


def strings(x: Any) -> list[str]:
    if x is None:
        return []
    if isinstance(x, str):
        return [x]
    if isinstance(x, dict):
        out: list[str] = []
        for v in x.values():
            out.extend(strings(v))
        return out
    if isinstance(x, list):
        out: list[str] = []
        for v in x:
            out.extend(strings(v))
        return out
    return [str(x)]


def has_leadership_evidence(data: dict[str, Any]) -> bool:
    regime = data.get("market_regime") or {}
    sectors = regime.get("top_sectors_by_data") or data.get("sector_table") or []
    if isinstance(sectors, list) and sectors:
        return True
    signals = data.get("signals") or []
    return isinstance(signals, list) and any(isinstance(s, dict) and s.get("score") is not None for s in signals)


def validate_one(name: str, json_path: Path, md_path: Path) -> list[str]:
    gaps: list[str] = []
    if not json_path.exists():
        return [f"{name}:missing_json"]
    if not md_path.exists():
        return [f"{name}:missing_md"]
    data = json.loads(json_path.read_text(encoding="utf-8"))
    md = md_path.read_text(encoding="utf-8", errors="replace")
    if not data.get("as_of"):
        gaps.append(f"{name}:missing_as_of")
    if not data.get("sources"):
        gaps.append(f"{name}:missing_sources")
    combined = "\n".join(strings(data) + [md])
    for term in DIRTY_TERMS:
        if re.search(rf"\b{re.escape(term)}\b", combined, re.I):
            gaps.append(f"{name}:dirty_term:{term}")
    if any(term in combined.lower() for term in LEADERSHIP_TERMS) and not has_leadership_evidence(data):
        gaps.append(f"{name}:leadership_without_structured_evidence")
    return gaps


def main() -> int:
    gaps: list[str] = []
    for item in REPORTS:
        gaps.extend(validate_one(*item))
    if gaps:
        print("PHASE5_REPORT_VALIDATION_FAILED")
        for gap in gaps:
            print("-", gap)
        return 1
    print("PHASE5_REPORTS_CLEAN")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
