#!/usr/bin/env python
"""Run Invest OS VN daily production chain with full PDF post-build.

Sequence:
- eod_market_brief
- stock_signal_scan --universe investable
- portfolio_daily_advice
- company_deep_dive --ticker FPT

The full HF lens PDF is built automatically by the company_deep_dive post_step.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "scripts" / "run_pipeline.py"


def run_step(args: list[str], *, quiet: bool = False) -> None:
    cmd = [sys.executable, str(RUNNER), "--config", "orchestrator.yaml", *args]
    pipeline = args[args.index("--pipeline") + 1]
    print("RUN", " ".join(str(part) for part in cmd), flush=True)
    if quiet:
        completed = subprocess.run(
            cmd,
            cwd=ROOT,
            text=True,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
        )
        if completed.returncode != 0:
            if completed.stdout:
                print(completed.stdout, end="")
            if completed.stderr:
                print(completed.stderr, end="", file=sys.stderr)
            completed.check_returncode()
    else:
        subprocess.run(cmd, cwd=ROOT, check=True)
    print(f"OK {pipeline}", flush=True)


def main() -> int:
    ap = argparse.ArgumentParser(description="Run full Invest OS VN daily production chain")
    ap.add_argument("--ticker", default="FPT", help="Ticker for company_deep_dive; default FPT")
    ap.add_argument("--no-refresh", action="store_true", help="Use existing data_live cache and skip provider refresh")
    ap.add_argument("--quiet", action="store_true", help="Hide child stdout/stderr unless a step fails")
    args = ap.parse_args()

    common = ["--live"]
    if args.no_refresh:
        common.append("--no-refresh")

    run_step(["--pipeline", "eod_market_brief", *common], quiet=args.quiet)
    run_step(["--pipeline", "stock_signal_scan", "--universe", "investable", *common], quiet=args.quiet)
    run_step(["--pipeline", "portfolio_daily_advice", *common], quiet=args.quiet)
    run_step(["--pipeline", "company_deep_dive", "--ticker", args.ticker.upper(), *common], quiet=args.quiet)
    print("DAILY_PRODUCTION_READY")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
