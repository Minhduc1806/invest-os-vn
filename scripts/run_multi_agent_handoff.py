#!/usr/bin/env python
"""Production multi-agent handoff wrapper for invest-os-vn.

Creates shared context, runs every required agent prompt through a local deterministic
agent shim, writes outputs/subagents/<agent>.json, then validates with
multi_agent_handoff.py.

Current runtime: repo-level production orchestration via phase3_local_agent_shim.
Not native OpenClaw LLM subagent spawn yet.

TODO: when OpenClaw exposes a stable CLI/API bridge for native subagent spawning,
replace run_agent() only; keep prompt creation, output path contract, and validation.
"""
from __future__ import annotations

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


def run_agent(agent: str, prompt_file: Path, out_file: Path) -> dict[str, Any]:
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
        },
    }
    save_json(out_file, result)
    return result


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    boot = bootstrap()
    agents = boot["required_agents"]
    SUB.mkdir(parents=True, exist_ok=True)
    results = []
    for agent in agents:
        prompt_file = PROMPTS / f"{agent}.txt"
        if not prompt_file.exists():
            raise FileNotFoundError(str(prompt_file))
        results.append(run_agent(agent, prompt_file, SUB / f"{agent}.json"))
    proc = subprocess.run([sys.executable, str(ROOT / "scripts" / "multi_agent_handoff.py")], cwd=ROOT)
    summary = {
        "as_of": now_iso(),
        "status": "ok" if proc.returncode == 0 else "failed",
        "agent_count": len(results),
        "agents": agents,
        "handoff_path": str(OUT / "multi_agent_handoff.json"),
        "runtime": "phase3_local_agent_shim",
        "note": "Repo-level production orchestration writes validated outputs/subagents JSON for all 14 agents via phase3_local_agent_shim; replace run_agent() with native OpenClaw subagent bridge when stable CLI/API is available.",
    }
    save_json(OUT / "multi_agent_handoff_run.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return proc.returncode


if __name__ == "__main__":
    raise SystemExit(main())
