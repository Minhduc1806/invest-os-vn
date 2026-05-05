#!/usr/bin/env python
"""Run all Phase 3 pipelines with real OpenClaw agents, then verify artifacts."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PIPELINES = ["portfolio_daily_advice", "eod_market_brief", "stock_signal_scan"]
MD_FILES = {
    "portfolio_daily_advice": ROOT / "outputs" / "portfolio_daily.md",
    "eod_market_brief": ROOT / "outputs" / "eod_market_brief.md",
    "stock_signal_scan": ROOT / "outputs" / "stock_signal_report_investable.md",
}
BAD_TOKENS = [
    "```json",
    '"runtime":',
    '"stdout":',
    '"stderr":',
    "Traceback (most recent call last)",
    "Command exited with code",
    "RuntimeError:",
]


def validate_markdown(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    stripped = text.strip()
    errors: list[str] = []
    if not stripped.startswith("#"):
        errors.append(f"{path}: does not start with #")
    if stripped.upper() in {"OK", "DONE", "ACCEPTED"}:
        errors.append(f"{path}: status-only report")
    if len(stripped) < 200:
        errors.append(f"{path}: too short")
    if any(token in stripped for token in BAD_TOKENS):
        errors.append(f"{path}: contains JSON/log/status text")
    return errors


def validate_manifest(pipeline: str) -> list[str]:
    path = ROOT / "scripts" / "results" / f"{pipeline}_phase3_manifest.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    errors: list[str] = []
    for key in ["lead_agent_call", "final_writer_call"]:
        call = data.get(key, {})
        if call.get("runtime") != "gateway/openclaw_agent":
            errors.append(f"{path}: {key}.runtime != gateway/openclaw_agent")
        if call.get("called") is not True:
            errors.append(f"{path}: {key}.called != true")
    return errors


def main() -> int:
    all_errors: list[str] = []
    for pipeline in PIPELINES:
        cmd = [sys.executable, "scripts/phase3_orchestrator.py", "--pipeline", pipeline, "--universe", "investable", "--call-agents"]
        print("RUN", " ".join(cmd), flush=True)
        proc = subprocess.run(cmd, cwd=ROOT, text=True, encoding="utf-8", errors="replace")
        if proc.returncode != 0:
            all_errors.append(f"{pipeline}: command failed code={proc.returncode}")
        all_errors.extend(validate_markdown(MD_FILES[pipeline]))
        all_errors.extend(validate_manifest(pipeline))
    if all_errors:
        print("PHASE3_E2E_FAILED")
        for err in all_errors:
            print("-", err)
        return 1
    print("PHASE3_E2E_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
