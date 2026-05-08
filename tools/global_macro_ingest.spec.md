# Tool Spec: global_macro_ingest

## Purpose
Cung cấp capability `global_macro_ingest` cho Invest OS VN để cập nhật macro toàn cầu ảnh hưởng VN equity.

## Interface
```json
{
  "tool": "global_macro_ingest",
  "input": {
    "topics": ["fed", "oil", "gold", "dxy", "us_yields", "trade_war", "geopolitics", "global_risk"]
  },
  "output": {
    "as_of": "ISO-8601",
    "source": ["string"],
    "quality_score": 0.0,
    "events": [],
    "indicators": {},
    "vn_equity_impact": [],
    "warnings": []
  }
}
```

## Required coverage
- FED/FOMC policy stance, Fed Funds range, next FOMC event if available.
- DXY/USD and US 2Y/10Y yields where available.
- Brent/WTI oil and gold trend where available.
- Trade war/export-control/tariff headlines relevant to Vietnam supply chain.
- War/geopolitical/shipping/sanctions events relevant to oil, FX, risk appetite, export demand.

## Quality rules
- Idempotent.
- Log source + timestamp.
- Return partial data with `warnings`, not hallucinated fields.
- Every event must include source, timestamp/date, confidence, and VN transmission channel.
- Prefer primary/official sources for rates/events; market data can use public feeds with source labels.

## Failure modes
- provider_down
- stale_data
- partial_coverage
- schema_invalid
- source_conflict
