# Tool Spec: macro_rates_parser

## Purpose
Parse Vietnam macro/rates numbers ổn định từ HTML/text/table sources into `data_live/macro_rates_live.vn.json` without fake fallback.

## Inputs
```json
{
  "tool": "macro_rates_parser",
  "input": {
    "sources": [
      {"name": "CafeF", "url": "https://cafef.vn/du-lieu/lai-suat-ngan-hang.chn", "kind": "rates_fx"},
      {"name": "WebGia", "url": "https://webgia.com/lai-suat/", "kind": "deposit_rates"},
      {"name": "Trading Economics", "url": "https://tradingeconomics.com/vietnam/stock-market", "kind": "macro_indicators"}
    ],
    "as_of_tz": "Asia/Ho_Chi_Minh",
    "required_fields": ["policy_rate", "inflation", "deposit_rates", "usd_vnd"]
  }
}
```

## Output
```json
{
  "as_of": "ISO-8601",
  "source": [{"name": "string", "url": "string", "fetched_at": "ISO-8601", "sha256": "string"}],
  "rates": {
    "policy_rate_pct": {"value": 4.5, "unit": "percent", "reference": "Apr 2026", "source": "Trading Economics"},
    "deposit_rates": {"unit": "%/year", "by_bank": {"VCB": {"1m": 0.0, "3m": 0.0, "6m": 0.0, "12m": 0.0}}},
    "usd_vnd": {"value": 0.0, "unit": "VND/USD", "source": "CafeF"}
  },
  "series": [{"name": "Vietnam Inflation Rate", "value": 5.46, "unit": "percent", "reference_period": "Apr 2026"}],
  "parse_quality": {"required_passed": true, "missing_fields": [], "warnings": []},
  "quality_score": 0.0,
  "status": "real_parsed"
}
```

## Stable parsing rules
- Fetch raw HTML, store raw checksum, never parse only readability text when tables exist.
- Prefer JSON-LD/embedded `__NEXT_DATA__`/script data, then HTML tables, then regex text.
- Normalize Vietnamese numbers: `1.234,56` -> `1234.56`; percent strings strip `%`; currency labels map `VND/USD`, `%/year`.
- Extract table headers by semantic labels: `Ngân hàng`, `01 tháng`, `03 tháng`, `06 tháng`, `12 tháng`, `USD`, `Mua`, `Bán`, `Chuyển khoản`.
- SBV fallback sources:
  - policy/rates page: `https://www.sbv.gov.vn/webcenter/portal/vi/menu/trangchu/lstk`
  - FX page: `https://www.sbv.gov.vn/webcenter/portal/vi/menu/rm/tygia`
- FX fallback sources:
  - WebGia USD page: `https://webgia.com/ty-gia/usd/`
  - Vietcombank XML endpoint: `https://portal.vietcombank.com.vn/UserControls/TVPortal.TyGia/pXML.aspx`
- Validate range gates:
  - policy/inflation/deposit percent: `0 <= value <= 30`
  - USD/VND: `10000 <= value <= 50000`
  - no duplicated bank+tenor rows after normalization
- If value missing or selector confidence low, set `value:null`, add warning, fail `required_passed` when field required.
- Do not copy watermark/anti-scrape tokens as numeric values.
- `decode_webgia_nb()` must accept only decimal tokens shaped `x,y`, `x.y`, or encoded `x2cy`; reject standalone integers like `30` from noise.
- Do not use mock, sample, default, previous day, or hardcoded fallback unless explicitly tagged `carry_forward` and blocked from production.

## Failure modes
- `provider_down`
- `table_schema_changed`
- `numeric_parse_failed`
- `range_validation_failed`
- `required_field_missing`
- `stale_data`
