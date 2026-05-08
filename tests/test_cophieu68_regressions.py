import json
from pathlib import Path
from urllib.error import HTTPError

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_refresh_news_te_403_cache_fallback_exit0(tmp_path, monkeypatch):
    import scripts.refresh_news_live as news

    out = tmp_path / "news_live.vn.json"
    raw = tmp_path / "raw"
    raw.mkdir()
    cache = raw / "te_news_fetch_text.txt"
    cache.write_text("Vietnam stocks rise as market liquidity improves\nVietnam VND and interest rate outlook stabilizes\n", encoding="utf-8")

    def fake_fetch(url: str) -> str:
        if "tradingeconomics.com" in url:
            raise HTTPError(url, 403, "Forbidden", hdrs=None, fp=None)
        return '<html><a href="/tin-doanh-nghiep.htm">Kết quả kinh doanh quý 1/2026 cải thiện</a></html>'

    monkeypatch.setattr(news, "OUT", out)
    monkeypatch.setattr(news, "TE_CACHE", cache)
    monkeypatch.setattr(news, "SOURCES", [
        {"name": "Trading Economics", "url": "https://tradingeconomics.com/vietnam/news"},
        {"name": "Vietstock mới cập nhật", "url": "https://vietstock.vn/tin-moi.htm"},
    ])
    monkeypatch.setattr(news, "fetch", fake_fetch)
    monkeypatch.setattr(news.sys, "argv", ["refresh_news_live.py"])

    assert news.main() == 0
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["status"] == "real_parsed"
    assert payload["parse_quality"]["required_passed"] is True
    assert any("Trading Economics:provider_down" in w and "used_revalidated_existing_cache" in w for w in payload["warnings"])
    assert any(i.get("source_mode") == "extracted_text_cache" for i in payload["items"])


def test_phase4_preflight_refreshes_cophieu68_before_gate(monkeypatch):
    import scripts.run_pipeline as run_pipeline

    calls = []

    def fake_run(cmd, cwd=None, check=False, text=False, encoding=None, errors=None):
        calls.append([str(x) for x in cmd])
        class Proc:
            returncode = 0
        return Proc()

    monkeypatch.setattr(run_pipeline.subprocess, "run", fake_run)
    run_pipeline.run_phase4_real_only_gate()

    assert any(c[-1] == "--refresh" and c[-2].endswith("cophieu68_to_fdata.py") for c in calls)
    assert any(c[-1] == "--allow-partial" and c[-2].endswith("refresh_news_live.py") for c in calls)
    assert any(c[-1].endswith("macro_rates_parser.py") for c in calls)
    assert any(c[-1].endswith("global_macro_ingest.py") for c in calls)
    assert any(x.endswith("phase4_real_data_gap_audit.py") for x in calls[-1])
    assert "--pipeline" in calls[-1]
    assert calls[-1][-1] == "all"


def test_portfolio_review_alias_written(tmp_path, monkeypatch):
    import scripts.run_pipeline as run_pipeline

    out_json = tmp_path / "outputs" / "portfolio_daily.json"
    out_md = tmp_path / "outputs" / "portfolio_daily.md"
    result = {"pipeline": "portfolio_daily_advice", "as_of": "2026-05-07T00:00:00+07:00"}
    md = "# Portfolio\n"

    run_pipeline.save_json(out_json, result)
    run_pipeline.save_text(out_md, md)
    alias_json = out_json.with_name("portfolio_review.json")
    alias_md = out_md.with_name("portfolio_review.md")
    run_pipeline.save_json(alias_json, result)
    run_pipeline.save_text(alias_md, md)

    assert alias_json.exists()
    assert alias_md.exists()
    assert json.loads(alias_json.read_text(encoding="utf-8"))["pipeline"] == "portfolio_daily_advice"
    assert alias_md.read_text(encoding="utf-8") == md
