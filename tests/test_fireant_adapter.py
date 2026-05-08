import json
from pathlib import Path


def test_fireant_normalize_industry_flow():
    from scripts.fireant_adapter import normalize_industry

    row = {
        "industryCode": "3010",
        "date": "2026-05-07T15:00:00.933",
        "indexValues": {
            "ICBName": "Ngân hàng",
            "IndexClose": 123.4,
            "IndexPrev": 120.0,
            "Volume": 240336500,
            "Value": 6592711450000,
            "BuyForeignQuantity": 23595113,
            "SellForeignQuantity": 34674320,
            "BuyForeignValue": 725186890732,
            "SellForeignValue": 1008490757441,
            "PE": 11.97,
            "PB": 1.94,
            "MarketCap": 2788403515439950,
        },
    }
    out = normalize_industry(row)
    assert out["industry_code"] == "3010"
    assert out["industry_name"] == "Ngân hàng"
    assert out["level"] == 4
    assert out["foreign_net_value_vnd"] == -283303866709
    assert out["foreign_net_qty"] == -11079207
    assert out["value_vnd"] == 6592711450000
    assert out["pe"] == 11.97


def test_fireant_extract_public_bearer_no_store_value():
    from scripts.fireant_adapter import extract_public_bearer

    token = extract_public_bearer("const e={headers:{Authorization:`Bearer abc.def.ghi`}}")
    assert token == "abc.def.ghi"


def test_fireant_map_rows_to_symbols_order():
    from scripts.fireant_adapter import TRADING_STAT_FIELDS, map_rows_to_symbols, normalize_sparse_row

    rows = [[None] * 164, [None] * 164]
    rows[0][12] = 1.2
    rows[1][12] = 3.4
    symbols = [{"symbol": "AAA"}, {"symbol": "BBB"}, {"symbol": "CCC"}]

    mapped, source = map_rows_to_symbols(rows, symbols)
    out = [normalize_sparse_row(row, TRADING_STAT_FIELDS, i, symbol, source) for i, (row, symbol) in enumerate(mapped)]

    assert source == "GetSymbols_order"
    assert out[0]["symbol"] == "AAA"
    assert out[0]["symbol_mapping_source"] == "GetSymbols_order"
    assert out[0]["row_index"] == 0
    assert out[0]["price_change_1w"] == 1.2
    assert out[1]["symbol"] == "BBB"
    assert out[1]["price_change_1w"] == 3.4


def test_fireant_map_rows_to_symbols_fallback_when_counts_mismatch():
    from scripts.fireant_adapter import TRADING_STAT_FIELDS, map_rows_to_symbols, normalize_sparse_row

    rows = [[None] * 164, [None] * 164]
    symbols = [{"symbol": "AAA"}]

    mapped, source = map_rows_to_symbols(rows, symbols)
    out = [normalize_sparse_row(row, TRADING_STAT_FIELDS, i, symbol, source) for i, (row, symbol) in enumerate(mapped)]

    assert source == "row_index_only"
    assert out[0]["row_index"] == 0
    assert "symbol" not in out[0]


def test_fireant_build_payload_phase1_mocked_no_token_store(monkeypatch, tmp_path):
    import scripts.fireant_adapter as fireant

    monkeypatch.setattr(fireant, "RAW", tmp_path / "raw")

    class DummySession:
        headers = {}

    secret = "public.dashboard.token"

    monkeypatch.setattr(fireant, "session", lambda: DummySession())
    monkeypatch.setattr(fireant, "discover_worker_url", lambda _s: "https://fireant.vn/assets/quote.worker-test.js")
    monkeypatch.setattr(fireant, "fetch_text", lambda _s, _url: f"const h={{Authorization:`Bearer {secret}`}};")
    monkeypatch.setattr(
        fireant,
        "fetch_icb_latest",
        lambda _s, bearer: [
            {
                "industryCode": "3010",
                "date": "2026-05-07T15:00:00.933",
                "indexValues": {
                    "ICBName": "Ngân hàng",
                    "IndexClose": 123.4,
                    "IndexPrev": 120.0,
                    "Value": 6592711450000,
                    "BuyForeignValue": 725186890732,
                    "SellForeignValue": 1008490757441,
                },
            }
        ],
    )

    payload = fireant.build_payload(phases="phase1", wait_ms=1)

    assert payload["status"] == "real_parsed"
    assert payload["records"] == 1
    assert payload["industry_flows"][0]["industry_name"] == "Ngân hàng"
    assert payload["auth_note"] == "public dashboard app bearer/access token extracted at runtime; token not stored"
    redacted = (tmp_path / "raw" / "quote_worker.redacted.js").read_text(encoding="utf-8")
    assert secret not in redacted
    assert "[REDACTED]" in redacted


def test_fireant_supplement_report_utf8_clean(tmp_path, monkeypatch):
    import scripts.fireant_supplement_reports as reports

    monkeypatch.setattr(reports, "LIVE", tmp_path / "data_live")
    monkeypatch.setattr(reports, "OUT", tmp_path / "outputs")
    reports.LIVE.mkdir(parents=True)
    payload = {
        "source": "fireant_public_dashboard",
        "timestamp": "2026-05-08T10:00:00+07:00",
        "quality_score": 0.8,
        "industry_flows": [
            {
                "industry_name": "Ngân hàng",
                "level": 4,
                "index_close": 123.4,
                "index_prev": 120.0,
                "value_vnd": 6592711450000,
                "foreign_net_value_vnd": -283303866709,
                "foreign_buy_value_vnd": 725186890732,
                "foreign_sell_value_vnd": 1008490757441,
                "positive_money_flow_vnd": 1_000_000_000,
                "negative_money_flow_vnd": 2_000_000_000,
                "pe": 11.97,
                "pb": 1.94,
                "market_cap_vnd": 2_788_403_515_439_950,
            }
        ],
        "ticker_trading_statistics": [],
        "financial_ratios": [],
    }
    (reports.LIVE / "fireant_foreign_flow.vn.json").write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    assert reports.main() == 0
    md = (reports.OUT / "fireant_supplement_summary.md").read_text(encoding="utf-8")
    assert "lớp dữ liệu bổ sung" in md
    assert "Ngân hàng" in md
    assert "tỷ" in md
    assert "�" not in md
    assert "NgA" not in md
