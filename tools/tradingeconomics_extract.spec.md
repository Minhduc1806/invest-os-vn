# Tool Spec: tradingeconomics_extract

## Purpose
Extract stable real macro/market fields from Trading Economics public pages, especially:
- `https://tradingeconomics.com/vietnam/government-bond-yield`
- `https://tradingeconomics.com/currencies`

## Inputs
```json
{
  "tool": "tradingeconomics_extract",
  "input": {
    "urls": [
      "https://tradingeconomics.com/vietnam/government-bond-yield",
      "https://tradingeconomics.com/currencies"
    ],
    "fields": ["vietnam_10y_yield", "currency_rates"],
    "target_pairs": ["USDVND", "EURUSD", "USDJPY", "USDCNY"],
    "as_of_tz": "Asia/Ho_Chi_Minh"
  }
}
```

## Output
```json
{
  "as_of": "ISO-8601",
  "source": [{"name": "Trading Economics", "url": "string", "fetched_at": "ISO-8601", "sha256": "string"}],
  "bond_yields": {
    "VN10Y": {"value": 4.37, "unit": "percent", "change_pp": 0.02, "date": "2026-05-05"}
  },
  "currencies": {
    "USDVND": {"value": 26000.0, "unit": "VND/USD", "day_pct": 0.0, "month_pct": 0.0, "date": "May/05"}
  },
  "parse_quality": {"required_passed": true, "missing_fields": [], "warnings": []}
}
```

## Stable parsing rules
- Fetch raw HTML first; store checksum + raw snapshot. If direct fetch 403, use browser/readability fetch as secondary source and mark `source_mode=extracted_text`.
- Bond yield page: parse sentence pattern `yield on Vietnam 10Y Bond Yield rose/fell/to X% on DATE, marking a Y percentage points ...`.
- Related macro table on bond page: parse `Vietnam Inflation Rate`, `Vietnam Interest Rate`, `Vietnam Unemployment Rate` blocks using `Last Previous Unit Reference` order.
- Currencies page: prefer embedded table rows/scripts with pair names. If readability strips symbols, parser must fail `currency_pair_labels_missing` instead of assigning unlabeled numbers.
- Numeric normalization: `1.234,56` -> `1234.56`; percent strip `%`; bond yields/rates range `0..30`; USD/VND range `10000..50000`.
- No fake fallback. Missing pair = null + warning; required pair missing blocks production.

## Failure modes
- `provider_down`
- `http_403_use_secondary_fetch`
- `currency_pair_labels_missing`
- `numeric_parse_failed`
- `range_validation_failed`
- `required_field_missing`
