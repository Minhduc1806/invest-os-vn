from datetime import datetime, timedelta


def test_derivatives_build_rows_basis_and_oi_change():
    from scripts.refresh_derivatives_live import build_rows

    fireant_quotes = {
        "VN30": [
            {"date": "2026-05-07T00:00:00", "priceClose": 1200},
            {"date": "2026-05-08T00:00:00", "priceClose": 1210},
        ],
        "VN30F1M": [
            {"date": "2026-05-07T00:00:00", "priceClose": 1205, "totalVolume": 100, "totalValue": 1_000, "buyForeignQuantity": 10, "sellForeignQuantity": 3, "buyForeignValue": 100, "sellForeignValue": 40, "propTradingNetValue": 5},
            {"date": "2026-05-08T00:00:00", "priceClose": 1208, "totalVolume": 200, "totalValue": 2_000, "buyForeignQuantity": 4, "sellForeignQuantity": 9, "buyForeignValue": 80, "sellForeignValue": 120, "propTradingNetValue": -7},
        ],
    }
    mappings = {"VN30F1M": {"code": "41I1FA000"}}
    vnd_prices = {
        "VN30F1M": [
            {"date": "2026-05-07T00:00:00", "openInterest": 1000, "nmVolume": 90, "nmValue": 900},
            {"date": "2026-05-08T00:00:00", "openInterest": 1015, "nmVolume": 180, "nmValue": 1800},
        ]
    }

    rows = build_rows(fireant_quotes, mappings, vnd_prices, ["VN30F1M"])
    latest = rows[0]

    assert latest["date"] == "2026-05-08"
    assert latest["basis"] == -2
    assert round(latest["basis_pct"], 4) == round(-2 / 1210 * 100, 4)
    assert latest["foreign_net_qty"] == -5
    assert latest["foreign_net_value"] == -40
    assert latest["open_interest"] == 1015
    assert latest["oi_change"] == 15


def test_derivatives_build_payload_mocked_no_secret_store(monkeypatch, tmp_path):
    import scripts.refresh_derivatives_live as der

    secret = "fireant.public.token"
    monkeypatch.setattr(der, "RAW", tmp_path / "raw")
    monkeypatch.setattr(der, "fireant_public_token", lambda: secret)
    monkeypatch.setattr(
        der,
        "fetch_fireant_quotes",
        lambda token, symbols, start, end: {
            "VN30": [{"date": "2026-05-08T00:00:00", "priceClose": 1210}],
            "VN30F1M": [{"date": "2026-05-08T00:00:00", "priceClose": 1208, "totalVolume": 200, "totalValue": 2_000}],
        },
    )
    monkeypatch.setattr(
        der,
        "fetch_vndirect",
        lambda symbols: ({"VN30F1M": {"code": "41I1FA000"}}, {"VN30F1M": [{"date": "2026-05-08T00:00:00", "openInterest": 1015}]}),
    )

    payload = der.build_payload(symbols=["VN30F1M"], days=3)

    assert payload["status"] == "real_parsed"
    assert payload["quality_score"] >= 0.7
    assert payload["rows"][0]["basis"] == -2
    assert "production_safe_public_no_secret" in payload["source_policy"]
    raw_text = "\n".join(p.read_text(encoding="utf-8") for p in (tmp_path / "raw").glob("*.json"))
    assert secret not in raw_text


def test_derivatives_quality_flags_missing_latest_fields():
    from scripts.refresh_derivatives_live import quality

    rows = [{"date": "2026-05-08", "symbol": "VN30F1M", "future_close": 1208, "vn30_close": None, "basis": None, "fireant_volume": 100, "open_interest": None}]
    score, warnings = quality(rows, {"VN30F1M": {"code": "41I1FA000"}})

    assert score < 0.85
    assert "latest_missing_field:vn30_close" in warnings
    assert "latest_missing_field:basis" in warnings
    assert "latest_missing_field:open_interest" in warnings
