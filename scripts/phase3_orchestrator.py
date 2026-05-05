#!/usr/bin/env python
"""Phase 3 production orchestrator.

Runs tool pipeline, builds quality report, then calls OpenClaw agent runtime when
`openclaw` CLI is available. Without CLI, writes exact agent-call plan and keeps
base markdown as final artifact instead of faking agent output.
"""
from __future__ import annotations
import argparse, json, os, shutil, subprocess, sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "scripts" / "results"

PIPELINE_AGENTS = {
    "stock_signal_scan": {"lead_agent": "equity-technical-analyst", "final_writer": "financial-news-editor"},
    "eod_market_brief": {"lead_agent": "market-strategist", "final_writer": "financial-news-editor"},
    "portfolio_daily_advice": {"lead_agent": "portfolio-advisor", "final_writer": "portfolio-advisor"},
    "company_deep_dive": {"lead_agent": "fundamental-analyst", "final_writer": "financial-news-editor"},
}

def load_yaml(path: Path) -> Dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))

def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))

def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def run_tool_pipeline(args: argparse.Namespace) -> subprocess.CompletedProcess[str]:
    cmd = [sys.executable, "scripts/run_pipeline.py", "--config", args.config, "--pipeline", args.pipeline]
    if args.live:
        cmd.append("--live")
    if args.mock:
        cmd.append("--mock")
    if args.universe:
        cmd += ["--universe", args.universe]
    if args.ticker:
        cmd += ["--ticker", args.ticker]
    if args.allow_quality_warnings:
        cmd.append("--allow-quality-warnings")
    return subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True)

def output_paths(config: Dict[str, Any], pipeline: str, live: bool, universe: str) -> tuple[Path, Path]:
    outs = config["pipelines"][pipeline]["outputs"]
    json_path = ROOT / outs["json"]
    md_path = ROOT / outs["markdown"]
    if pipeline == "stock_signal_scan" and live:
        json_path = json_path.with_name(f"{json_path.stem}_{universe}{json_path.suffix}")
        md_path = md_path.with_name(f"{md_path.stem}_{universe}{md_path.suffix}")
    return json_path, md_path

def build_quality_report(tool_json: Path, proc: subprocess.CompletedProcess[str]) -> Dict[str, Any]:
    data = load_json(tool_json) if tool_json.exists() else {}
    return {
        "as_of": datetime.now().astimezone().isoformat(timespec="seconds"),
        "tool_json": str(tool_json),
        "returncode": proc.returncode,
        "quality_warnings": data.get("quality_warnings", []),
        "quality_score": data.get("quality_score", 1 if proc.returncode == 0 else 0),
        "stderr": proc.stderr[-4000:],
    }

def extract_json_object(text: str) -> Optional[Dict[str, Any]]:
    start = text.find("{")
    while start != -1:
        depth = 0
        in_string = False
        escape = False
        for idx in range(start, len(text)):
            ch = text[idx]
            if in_string:
                if escape:
                    escape = False
                elif ch == "\\":
                    escape = True
                elif ch == '"':
                    in_string = False
            else:
                if ch == '"':
                    in_string = True
                elif ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        candidate = text[start:idx + 1]
                        try:
                            return json.loads(candidate)
                        except Exception:
                            break
        start = text.find("{", start + 1)
    return None

def strip_plugin_banner(stdout: str) -> str:
    lines = stdout.replace("\r\n", "\n").split("\n")
    kept = [ln for ln in lines if not ln.startswith("[plugins]")]
    return "\n".join(kept).strip()

def extract_agent_text(stdout: str) -> Optional[str]:
    cleaned = strip_plugin_banner(stdout or "")
    payload = extract_json_object(cleaned)
    if payload:
        texts = payload.get("result", {}).get("payloads", [])
        if texts and isinstance(texts[0], dict):
            text = texts[0].get("text")
            if isinstance(text, str) and text.strip():
                return text.strip()
    blocks = [b.strip() for b in cleaned.split("\n\n") if b.strip()]
    for block in reversed(blocks):
        if not block.startswith("[plugins]"):
            return block
    return cleaned or None

def report_like(text: str) -> bool:
    t = (text or "").strip()
    if not t or t.upper() == "OK":
        return False
    if t.startswith("#") or t.startswith("##"):
        return True
    vietnamese_marks = sum(t.lower().count(ch) for ch in "ăâđêôơưáàảãạấầẩẫậắằẳẵặéèẻẽẹếềểễệíìỉĩịóòỏõọốồổỗộớờởỡợúùủũụứừửữựýỳỷỹỵ")
    markdown_signals = sum(t.count(sig) for sig in ["\n## ", "\n- ", "**", "|", "\n### "])
    return len(t) >= 500 and vietnamese_marks >= 20 and markdown_signals >= 3

def call_agent(agent_id: str, prompt: str, timeout: int = 180, fallback_shim: bool = False) -> Dict[str, Any]:
    RESULTS.mkdir(parents=True, exist_ok=True)
    prompt_path = RESULTS / f"{agent_id}_prompt.txt"
    out_path = RESULTS / f"{agent_id}_agent_call.json"
    prompt_path.write_text(prompt, encoding="utf-8")
    cli = shutil.which("openclaw")
    if cli:
        max_prompt = 3500
        if len(prompt) > max_prompt:
            prompt = prompt[:max_prompt] + "\n[TRUNCATED: see tool_outputs/quality_report files in manifest]"
        prompt_path.write_text(prompt, encoding="utf-8")
        exe = str(Path(cli).with_suffix(".cmd")) if os.name == "nt" else cli
        cmd = f'"{exe}" agent --agent {agent_id} --message "{prompt.replace(chr(34), chr(39))}" --json --timeout {timeout}'
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        proc = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True, timeout=timeout + 60, env=env, encoding="utf-8", errors="replace")
        result = {"runtime": "gateway/openclaw_agent", "called": True, "agent_id": agent_id, "returncode": proc.returncode, "stdout": proc.stdout, "stderr": proc.stderr, "prompt_file": str(prompt_path), "out_file": str(out_path)}
        out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        return result
    if not fallback_shim:
        raise RuntimeError("openclaw CLI not found and --fallback-shim not set")
    helper = ROOT / "scripts" / "openclaw_agent_call.py"
    proc = subprocess.run([sys.executable, str(helper), "--agent", agent_id, "--prompt-file", str(prompt_path), "--out", str(out_path)], cwd=ROOT, text=True, capture_output=True, timeout=timeout)
    data = load_json(out_path) if out_path.exists() else {}
    return {"runtime": "phase3_local_agent_shim", "called": True, "agent_id": agent_id, "returncode": proc.returncode, "stdout": proc.stdout, "stderr": proc.stderr, "result": data, "prompt_file": str(prompt_path), "out_file": str(out_path)}

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="orchestrator.yaml")
    ap.add_argument("--pipeline", required=True, choices=sorted(PIPELINE_AGENTS))
    ap.add_argument("--live", action="store_true", default=True)
    ap.add_argument("--mock", action="store_true")
    ap.add_argument("--universe", default="investable")
    ap.add_argument("--ticker", default="FPT")
    ap.add_argument("--allow-quality-warnings", action="store_true")
    ap.add_argument("--call-agents", action="store_true", help="Actually call OpenClaw CLI agents when available")
    ap.add_argument("--fallback-shim", action="store_true", help="Use local proof shim only if OpenClaw CLI unavailable")
    ap.add_argument("--agent-timeout", type=int, default=180)
    args = ap.parse_args()

    if args.mock and not args.allow_quality_warnings:
        raise RuntimeError("MOCK_BLOCKED: mock requires --mock --allow-quality-warnings")
    args.live = not args.mock

    config = load_yaml(ROOT / args.config)
    pipe_cfg = config["pipelines"][args.pipeline]
    agent_cfg = {**PIPELINE_AGENTS[args.pipeline], **{k: pipe_cfg.get(k) for k in ["lead_agent", "final_writer"] if pipe_cfg.get(k)}}

    proc = run_tool_pipeline(args)
    json_path, md_path = output_paths(config, args.pipeline, args.live, args.universe)
    quality = build_quality_report(json_path, proc)
    qpath = RESULTS / f"{args.pipeline}_quality_report.json"
    save_json(qpath, quality)

    tool_payload = load_json(json_path) if json_path.exists() else {"error": "missing tool json"}
    summary_payload = json.dumps(tool_payload, ensure_ascii=False)[:2500]
    lead_prompt = f"Read AGENTS.md. Lead agent for {args.pipeline}. Review tool output and quality report. Return decisions + risks only. Tool output excerpt: {summary_payload} Quality: {json.dumps(quality, ensure_ascii=False)}"
    final_prompt = f"""Read AGENTS.md. Final writer for {args.pipeline}.
Contract:
- Output final Vietnamese Markdown report only.
- First non-space character must be '#'.
- Include useful headings, bullets, and data tables when available.
- Do not answer only OK / Done / Accepted / placeholder.
- Do not emit JSON, logs, or status text.
- No unsupported leadership labels; cite actual data from tool output.
Tool output excerpt: {summary_payload}
Quality: {json.dumps(quality, ensure_ascii=False)}"""

    lead = call_agent(agent_cfg["lead_agent"], lead_prompt, timeout=args.agent_timeout, fallback_shim=args.fallback_shim) if args.call_agents else {"called": False, "agent_id": agent_cfg["lead_agent"], "reason": "--call-agents not set", "prompt": lead_prompt}
    final = call_agent(agent_cfg["final_writer"], final_prompt + "\nLead review:\n" + json.dumps(lead, ensure_ascii=False)[:2500], timeout=args.agent_timeout, fallback_shim=args.fallback_shim) if args.call_agents else {"called": False, "agent_id": agent_cfg["final_writer"], "reason": "--call-agents not set", "prompt": final_prompt}
    if args.call_agents and final.get("stdout"):
        final_text = extract_agent_text(final["stdout"])
        final["extracted_text_preview"] = (final_text or "")[:300]
        if report_like(final_text or ""):
            md_path.write_text(final_text.strip() + "\n", encoding="utf-8")
            final["overwrote_markdown"] = str(md_path)
        else:
            final["overwrite_skipped"] = "final writer output not report-like"

    manifest = {
        "as_of": datetime.now().astimezone().isoformat(timespec="seconds"),
        "pipeline": args.pipeline,
        "lead_agent": agent_cfg["lead_agent"],
        "final_writer": agent_cfg["final_writer"],
        "tool_outputs": str(json_path),
        "quality_report": str(qpath),
        "base_markdown": str(md_path),
        "lead_agent_call": lead,
        "final_writer_call": final,
    }
    save_json(RESULTS / f"{args.pipeline}_phase3_manifest.json", manifest)
    print(json.dumps(manifest, ensure_ascii=True, indent=2))
    return proc.returncode

if __name__ == "__main__":
    raise SystemExit(main())
