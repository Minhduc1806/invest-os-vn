#!/usr/bin/env python
"""Minimal Phase 4 CI smoke runner."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMMANDS = [
    [sys.executable, "tests/phase4_regression_smoke.py"],
    [sys.executable, "scripts/macro_rates_parser.py", "--merge-live"],
    [sys.executable, "scripts/phase4_real_data_gap_audit.py", "--mode", "eod"],
    [sys.executable, "scripts/phase4_e2e.py"],
]


def main() -> int:
    for cmd in COMMANDS:
        print("RUN", " ".join(cmd), flush=True)
        rc = subprocess.run(cmd, cwd=ROOT).returncode
        if rc != 0:
            print("CI_PHASE4_SMOKE_FAILED", " ".join(cmd))
            return rc
    print("CI_PHASE4_SMOKE_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
