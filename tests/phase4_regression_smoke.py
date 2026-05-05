#!/usr/bin/env python
from datetime import datetime, timedelta
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.macro_rates_parser import decode_webgia_nb, parse_te_interest_rate, parse_vcb_usd_fx, parse_webgia_deposit_rates
from scripts.phase4_real_data_gap_audit import audit_payload


def check(name, cond):
    if not cond:
        raise AssertionError(name)
    print(f"OK {name}")

check('decode_webgia_nb("30") is None', decode_webgia_nb("30") is None)
check('VCB 26,126.00 -> 26126.0', parse_vcb_usd_fx((ROOT / 'tests/fixtures/vcb_usd_fx.xml').read_text(encoding='utf-8')) == 26126.0)
item = parse_te_interest_rate((ROOT / 'tests/fixtures/te_interest_rate_text.txt').read_text(encoding='utf-8'))
check('TE interest text -> 4.5', item is not None and item['value'] == 4.5)
dep = parse_webgia_deposit_rates((ROOT / 'tests/fixtures/webgia_deposit_tiny.html').read_text(encoding='utf-8'))
check('WebGia fixture rejects dirty bank and 0m', 'Á' not in dep and '0m' not in dep.get('Vietcombank', {}))
old_data = {'source': 'real', 'as_of': (datetime.now().astimezone() - timedelta(minutes=60)).isoformat()}
check('audit eod ignores 60m EOD stale', not any(g.startswith('stale_as_of') for g in audit_payload('market_snapshot', ROOT / 'data_live' / 'market_snapshot.vn.json', old_data, mode='eod')['gaps']))
check('audit intraday fails 60m stale', 'stale_as_of>30m' in audit_payload('market_snapshot', ROOT / 'data_live' / 'market_snapshot.vn.json', old_data, mode='intraday')['gaps'])
print('PHASE4_REGRESSION_SMOKE_OK')
