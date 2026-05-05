import json
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.macro_rates_parser import decode_webgia_nb, parse_te_interest_rate, parse_vcb_usd_fx
from scripts.phase4_real_data_gap_audit import audit_payload


def test_decode_webgia_nb_rejects_integer_noise():
    assert decode_webgia_nb("30") is None


def test_vcb_thousands_number_parses_fx():
    xml = '<Exrate CurrencyCode="USD" Buy="26,096.00" Transfer="26,126.00" Sell="26,366.00" />'
    assert parse_vcb_usd_fx(xml) == 26126.0


def test_te_interest_text_extracts_policy_rate():
    text = "The benchmark interest rate in Vietnam was last recorded at 4.50 percent. source: The State Bank of Vietnam"
    item = parse_te_interest_rate(text)
    assert item is not None
    assert item["value"] == 4.5


def test_audit_eod_uses_1440m_window_for_market():
    data = {"source": "real", "as_of": (datetime.now().astimezone() - timedelta(minutes=60)).isoformat()}
    result = audit_payload("market_snapshot", ROOT / "data_live" / "market_snapshot.vn.json", data, mode="eod")
    assert not any(g.startswith("stale_as_of") for g in result["gaps"])


def test_audit_intraday_still_uses_30m_window_for_market():
    data = {"source": "real", "as_of": (datetime.now().astimezone() - timedelta(minutes=60)).isoformat()}
    result = audit_payload("market_snapshot", ROOT / "data_live" / "market_snapshot.vn.json", data, mode="intraday")
    assert "stale_as_of>30m" in result["gaps"]
