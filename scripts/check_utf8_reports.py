#!/usr/bin/env python
"""Check report files decode as UTF-8 and do not contain replacement/mojibake markers."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FILES = [
    ROOT / "reports" / "templates" / "portfolio_daily.md",
    ROOT / "reports" / "templates" / "eod_market_brief.md",
    ROOT / "reports" / "templates" / "stock_signal_report.md",
    ROOT / "outputs" / "portfolio_daily.md",
    ROOT / "outputs" / "eod_market_brief.md",
    ROOT / "outputs" / "stock_signal_report_investable.md",
]
BAD = ["�", "���", "Danh m?c", "B?o c?o", "d? li?u"]


def main() -> int:
    errors: list[str] = []
    for path in FILES:
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            errors.append(f"{path}: UTF-8 decode failed: {exc}")
            continue
        hits = [token for token in BAD if token in text]
        if hits:
            errors.append(f"{path}: mojibake markers {hits}")
    if errors:
        print("UTF8_REPORT_CHECK_FAILED")
        for err in errors:
            print("-", err)
        return 1
    print("UTF8_REPORT_CHECK_OK")
    print("PowerShell display mojibake usually means console codepage/font issue. Run: chcp 65001")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
