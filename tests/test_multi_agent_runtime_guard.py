import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_run_multi_agent_handoff_shim_passes():
    proc = subprocess.run(
        [sys.executable, "scripts/run_multi_agent_handoff.py", "--runtime", "shim"],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        timeout=120,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    payload = json.loads((ROOT / "outputs" / "multi_agent_handoff.json").read_text(encoding="utf-8"))
    assert payload["status"] == "ok"
    assert len(payload["required_agents"]) == 14
    assert payload["autonomy_level"] == "repo_level_shim_orchestration"
    assert payload["runtime_modes"] == ["phase3_local_agent_shim"]
    assert payload["native_openclaw_subagents"] is False


def test_run_multi_agent_handoff_native_openclaw_fails_without_bridge():
    proc = subprocess.run(
        [sys.executable, "scripts/run_multi_agent_handoff.py", "--runtime", "native-openclaw"],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        timeout=120,
    )
    combined = proc.stdout + proc.stderr
    assert proc.returncode != 0
    assert "NATIVE_OPENCLAW_BRIDGE_UNAVAILABLE" in combined
    failed = json.loads((ROOT / "outputs" / "subagents" / "market-strategist.json").read_text(encoding="utf-8"))
    assert failed["status"] == "failed"
    assert failed["error"] == "NATIVE_OPENCLAW_BRIDGE_UNAVAILABLE"
    assert failed["validation"]["native_openclaw_subagent"] is False
