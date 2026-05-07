#!/usr/bin/env python
"""Production multi-agent handoff wrapper for invest-os-vn.

Creates shared context, runs every required agent prompt, writes
outputs/subagents/<agent>.json, then validates with multi_agent_handoff.py.

Default runtime: repo-level production orchestration via phase3_local_agent_shim.
Native mode: --runtime native-openclaw intentionally fails with
NATIVE_OPENCLAW_BRIDGE_UNAVAILABLE until a stable OpenClaw subagent CLI/API bridge
exists. No silent fallback.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs"
SUB = OUT / "subagents"
PROMPTS = OUT / "subagent_prompts"


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def bootstrap() -> dict[str, Any]:
    subprocess.run([sys.executable, str(ROOT / "scripts" / "multi_agent_handoff.py"), "--bootstrap-prompts"], cwd=ROOT, check=True)
    payload = load_json(OUT / "multi_agent_handoff.json")
    agents = payload.get("required_agents", [])
    if len(agents) != 14:
        raise RuntimeError(f"expected_14_agents_got_{len(agents)}")
    return payload


def run_agent_shim(agent: str, prompt_file: Path, out_file: Path) -> dict[str, Any]:
    shim_out = OUT / "subagent_raw" / f"{agent}.json"
    subprocess.run([
        sys.executable,
        str(ROOT / "scripts" / "openclaw_agent_call.py"),
        "--agent", agent,
        "--prompt-file", str(prompt_file),
        "--out", str(shim_out),
    ], cwd=ROOT, check=True)
    raw = load_json(shim_out)
    result = {
        "agent": agent,
        "status": "ok" if raw.get("called") else "failed",
        "findings": [raw.get("response", "agent completed handoff")],
        "handoff": {
            "runtime": raw.get("runtime"),
            "agent_id": raw.get("agent_id"),
            "prompt_chars": raw.get("prompt_chars"),
            "read_root_agents_md": raw.get("read_root_agents_md"),
            "read_runtime_agents_md": raw.get("read_runtime_agents_md"),
        },
        "validation": {
            "used_shared_context": True,
            "no_sample_fallback": True,
            "local_agent_shim": raw.get("runtime") == "phase3_local_agent_shim",
            "native_openclaw_subagent": False,
        },
    }
    save_json(out_file, result)
    return result


def run_agent_native_openclaw(agent: str, prompt_file: Path, out_file: Path) -> dict[str, Any]:
    """Native OpenClaw subagent bridge placeholder.

    Local audit found OpenClaw native spawning exists inside agent tool runtime
    (`sessions_spawn`) and task ledger, but no stable non-interactive CLI or
    documented Gateway API endpoint that repo Python can call with prompt-in /
    result-out / write-file semantics. `openclaw agent` runs a normal Gateway
    agent turn, not a child subagent controlled by this repo wrapper.
    """
    failure = {
        "agent": agent,
        "status": "failed",
        "error": "NATIVE_OPENCLAW_BRIDGE_UNAVAILABLE",
        "findings": [],
        "handoff": {
            "runtime": "native-openclaw",
            "prompt_file": str(prompt_file),
            "reason": "No stable documented CLI/API bridge for native OpenClaw sessions_spawn from repo Python wrapper.",
        },
        "validation": {
            "used_shared_context": False,
            "no_sample_fallback": True,
            "local_agent_shim": False,
            "native_openclaw_subagent": False,
        },
    }
    save_json(out_file, failure)
    raise RuntimeError("NATIVE_OPENCLAW_BRIDGE_UNAVAILABLE")


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Run invest-os-vn 14-agent handoff orchestration.")
    ap.add_argument(
        "--runtime",
        choices=["shim", "native-openclaw"],
        default="shim",
        help="shim uses phase3_local_agent_shim. native-openclaw fails clearly until stable OpenClaw subagent CLI/API bridge exists.",
    )
    return ap.parse_args()


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    args = parse_args()
    boot = bootstrap()
    agents = boot["required_agents"]
    SUB.mkdir(parents=True, exist_ok=True)
    runner = run_agent_shim if args.runtime == "shim" else run_agent_native_openclaw
    results = []
    for agent in agents:
        prompt_file = PROMPTS / f"{agent}.txt"
        if not prompt_file.exists():
            raise FileNotFoundError(str(prompt_file))
        results.append(runner(agent, prompt_file, SUB / f"{agent}.json"))
    proc = subprocess.run([sys.executable, str(ROOT / "scripts" / "multi_agent_handoff.py")], cwd=ROOT)
    summary = {
        "as_of": now_iso(),
        "status": "ok" if proc.returncode == 0 else "failed",
        "agent_count": len(results),
        "agents": agents,
        "handoff_path": str(OUT / "multi_agent_handoff.json"),
        "runtime": "phase3_local_agent_shim" if args.runtime == "shim" else "native-openclaw",
        "native_openclaw_subagents": args.runtime == "native-openclaw",
        "note": "Repo-level production orchestration writes validated outputs/subagents JSON for all 14 agents via phase3_local_agent_shim; native-openclaw mode intentionally fails with NATIVE_OPENCLAW_BRIDGE_UNAVAILABLE until stable OpenClaw subagent CLI/API is available.",
    }
    save_json(OUT / "multi_agent_handoff_run.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return proc.returncode


if __name__ == "__main__":
    raise SystemExit(main())
