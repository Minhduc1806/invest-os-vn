def test_full_pdf_report_builder_derivatives_section(monkeypatch):
    import scripts.build_hf_lens_full_pdf_report as builder

    def fake_load(path):
        name = path.name
        if name == "fdata_hose_breadth.json":
            return {
                "breadth": {"advancers": 120, "decliners": 210, "adv_dec_ratio": 0.57, "above_ma20_pct": 38},
                "market": {"indices": [{"symbol": "VNINDEX", "close": 1234.5, "change_pct": 1.1, "volume_mn": 500}, {"symbol": "VN30", "close": 1250, "change_pct": 0.8, "volume_mn": 150}]},
            }
        if name == "stock_signal_scan_investable.json":
            return {"universe_size": 1, "signals": [{"ticker": "FPT", "status": "watch", "score": 0.66, "entry_zone": "100-102", "invalidation": "close < 98", "evidence": ["RS ok"]}]}
        if name in {"portfolio_action_report.json", "portfolio_daily.json"}:
            return {"nav_vnd": 1_000_000_000, "cash_vnd": 120_000_000, "risks": ["test risk"]}
        if name == "fireant_foreign_flow.vn.json":
            return {"industry_flows": [{"level": 4, "industry_name": "Banks", "value_vnd": 2_000_000_000_000, "foreign_net_value_vnd": 20_000_000_000, "positive_money_flow_vnd": 500_000_000_000, "negative_money_flow_vnd": 200_000_000_000, "index_close": 101, "index_prev": 100, "pe": 10, "pb": 1.5}]}
        if name == "derivatives_live.vn.json":
            return {"rows": [{"date": "2026-05-08", "symbol": "VN30F1M", "vndirect_code": "41I1FA000", "future_close": 1208, "vn30_close": 1210, "basis": -2, "basis_pct": -0.165, "fireant_volume": 200, "fireant_value": 2_000_000_000, "open_interest": 1015, "oi_change": 15, "foreign_net_qty": -5, "foreign_net_value": -40_000_000, "prop_net_value": 10_000_000}]}
        if name == "eod_market_brief.json":
            return {"market_thesis": "Test thesis"}
        return {}

    monkeypatch.setattr(builder, "load", fake_load)
    html = builder.build_html()
    issues = builder.sanity_check(html)

    assert issues == []
    assert "Derivatives Strategist" in html
    assert "VN30 derivatives" in html
    assert "VN30F1M" in html
    assert "basis" in html
    assert "OI Δ" in html
    assert "Foreign net" in html
