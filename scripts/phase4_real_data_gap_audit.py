#!/usr/bin/env python
"""Phase 4 real-data expansion gap audit.

Reports live/mock/placeholder gaps before replacing Phase 3 warning-tolerant flows.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

CHECKS = {
    "market_snapshot": ROOT / "data_live" / "market_snapshot.vn.json",
    "ohlcv_investable": ROOT / "data_live" / "fdata_investable_bars.json",
    "ohlcv_hose_all": ROOT / "data_live" / "fdata_hose_all_bars.json",
    "portfolio": ROOT / "data_live" / "portfolio_real.json",
    "news_live": ROOT / "data_live" / "news_live.vn.json",
    "macro_rates_live": ROOT / "data_live" / "macro_rates_live.vn.json",
    "global_macro_live": ROOT / "data_live" / "global_macro_live.json",
    "derivatives_live": ROOT / "data_live" / "derivatives_live.vn.json",
}

PIPELINE_CHECKS = {
    "eod_market_brief": ["market_snapshot", "news_live", "macro_rates_live", "global_macro_live", "derivatives_live"],
    "stock_signal_scan": ["market_snapshot", "ohlcv_investable", "ohlcv_hose_all"],
    "portfolio_daily_advice": ["portfolio", "market_snapshot", "news_live", "macro_rates_live", "global_macro_live", "ohlcv_investable", "derivatives_live"],
    "company_deep_dive": ["market_snapshot", "news_live", "macro_rates_live", "global_macro_live", "ohlcv_investable", "derivatives_live"],
    "all": list(CHECKS),
}

BLOCKED_SOURCES = {"mock_news_hub", "mock_macro_provider", "manual_real_portfolio_required", "sample", "template"}
PLACEHOLDER_STATUSES = {"placeholder_not_real", "template", "sample"}
STALE_MINUTES = {
    "eod": {
        "market_snapshot": 1440,
        "ohlcv_investable": 1440,
        "ohlcv_hose_all": 1440,
        "portfolio": 4320,
        "news_live": 1440,
        "macro_rates_live": 1440,
        "global_macro_live": 1440,
        "derivatives_live": 1440,
    },
    "intraday": {
        "market_snapshot": 30,
        "ohlcv_investable": 30,
        "ohlcv_hose_all": 30,
        "portfolio": 4320,
        "news_live": 1440,
        "macro_rates_live": 1440,
        "global_macro_live": 1440,
        "derivatives_live": 1440,
    },
}


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def source_values(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        out: list[str] = []
        for item in value:
            out.extend(source_values(item))
        return out
    if isinstance(value, dict):
        out: list[str] = []
        for key in ("source", "provider", "name"):
            out.extend(source_values(value.get(key)))
        return out
    return [str(value)]


def parse_dt(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        text = str(value).replace("Z", "+00:00")
        dt = datetime.fromisoformat(text)
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except Exception:
        return None


def audit_payload(name: str, path: Path, data: Any, mode: str = "eod") -> dict[str, Any]:
    gaps: list[str] = []
    sources = source_values(data.get("source")) if isinstance(data, dict) else []
    if not sources:
        gaps.append("missing_source")
    blocked = sorted(set(sources) & BLOCKED_SOURCES)
    if blocked:
        gaps.append("blocked_source:" + ",".join(blocked))
    as_of = parse_dt(data.get("as_of")) if isinstance(data, dict) else None
    if not as_of:
        gaps.append("missing_or_invalid_as_of")
    else:
        max_min = STALE_MINUTES.get(mode, STALE_MINUTES["eod"]).get(name)
        if max_min and (datetime.now().astimezone() - as_of).total_seconds() / 60 > max_min:
            gaps.append(f"stale_as_of>{max_min}m")
    status = data.get("status") if isinstance(data, dict) else None
    if status in PLACEHOLDER_STATUSES:
        gaps.append(f"placeholder_status:{status}")
    if name == "portfolio" and isinstance(data, dict):
        positions = data.get("positions") or []
        valuation = data.get("valuation") or {}
        cash = float(data.get("cash_vnd") or 0)
        equity_value = sum(float(p.get("quantity") or 0) * float(p.get("last_price") or 0) for p in positions if isinstance(p, dict))
        nav = cash + equity_value - float(data.get("margin_debt_vnd") or 0)
        if data.get("status") == "placeholder_not_real" or (not positions and cash <= 0) or nav <= 0:
            gaps.append("portfolio_not_real")
        if not isinstance(valuation, dict) or valuation.get("nav_vnd") is None:
            gaps.append("missing_valuation")
        for i, pos in enumerate(positions):
            missing = [k for k in ("ticker", "quantity", "avg_cost", "last_price", "source") if not pos.get(k)]
            if missing:
                gaps.append(f"position_{i}_missing:" + ",".join(missing))
    if name.startswith("news") and isinstance(data, dict):
        items = data.get("items") or data.get("news") or []
        if not items:
            gaps.append("empty_news_items")
        keys = []
        for item in items:
            if isinstance(item, dict):
                keys.append(item.get("dedupe_key") or item.get("url") or item.get("title"))
                if not (item.get("timestamp") or item.get("published_at")):
                    gaps.append("news_item_missing_timestamp")
        if len([k for k in keys if k]) != len(set(k for k in keys if k)):
            gaps.append("duplicate_news_items")
    if name.startswith("macro") and isinstance(data, dict):
        if not any(k in data for k in ("rates", "macro", "items", "series")):
            gaps.append("empty_macro_series")
    if name == "global_macro_live" and isinstance(data, dict):
        if not data.get("indicators"):
            gaps.append("empty_global_macro_indicators")
        if not data.get("events"):
            gaps.append("empty_global_macro_events")
        if float(data.get("quality_score") or 0) < 0.7:
            gaps.append("low_global_macro_quality")
    if name == "derivatives_live" and isinstance(data, dict):
        rows = data.get("rows") or []
        if not rows:
            gaps.append("empty_derivatives_rows")
        if float(data.get("quality_score") or 0) < 0.7:
            gaps.append("low_derivatives_quality")
        source_policy = str(data.get("source_policy") or "")
        if "production_safe_public_no_secret" not in source_policy:
            gaps.append("invalid_derivatives_source_policy")
        for i, row in enumerate(rows[:10]):
            if not isinstance(row, dict):
                gaps.append(f"derivatives_row_{i}_not_object")
                continue
            missing = [k for k in ("date", "symbol", "future_close", "vn30_close", "basis", "basis_pct", "open_interest") if row.get(k) is None]
            if missing:
                gaps.append(f"derivatives_row_{i}_missing:" + ",".join(missing))
    if name.startswith("ohlcv") and isinstance(data, dict):
        bars = data.get("bars") or []
        if not bars:
            gaps.append("empty_bars")
    return {
        "name": name,
        "path": str(path.relative_to(ROOT)),
        "exists": path.exists(),
        "source": sources,
        "as_of": data.get("as_of") if isinstance(data, dict) else None,
        "gaps": gaps,
    }


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["eod", "intraday"], default="eod", help="Stale window policy: eod=1440m for market/OHLCV, intraday=30m")
    ap.add_argument("--pipeline", choices=sorted(PIPELINE_CHECKS), default="all", help="Audit only inputs needed by one pipeline; default audits all live layers")
    ap.add_argument("--allow-stale-portfolio", action="store_true", help="Portfolio can be stale when explicitly user-provided and not needed for price/history freshness checks")
    args = ap.parse_args()
    results = []
    check_names = PIPELINE_CHECKS[args.pipeline]
    for name in check_names:
        path = CHECKS[name]
        if not path.exists():
            results.append({"name": name, "path": str(path.relative_to(ROOT)), "exists": False, "gaps": ["missing_file"]})
            continue
        try:
            results.append(audit_payload(name, path, load(path), mode=args.mode))
        except Exception as exc:
            results.append({"name": name, "path": str(path.relative_to(ROOT)), "exists": True, "gaps": [f"read_error:{exc}"]})
    out = {"as_of": datetime.now().astimezone().isoformat(timespec="seconds"), "mode": args.mode, "pipeline": args.pipeline, "results": results}
    out_path = ROOT / "scripts" / "results" / "phase4_real_data_gap_audit.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.allow_stale_portfolio:
        for r in results:
            if r.get("name") == "portfolio":
                r["gaps"] = [g for g in r.get("gaps", []) if not str(g).startswith("stale_as_of>")]
                if r.get("source"):
                    r["stale_policy"] = "allowed_user_provided_portfolio"
    open_gaps = [r for r in results if r.get("gaps")]
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print(json.dumps(out, ensure_ascii=False, indent=2))
    print("PHASE4_REAL_DATA_GAPS" if open_gaps else "PHASE4_REAL_DATA_READY")
    return 1 if open_gaps else 0


if __name__ == "__main__":
    raise SystemExit(main())
