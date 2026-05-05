# Tool Spec: fundamental_engine

## Purpose
Cung cấp capability `fundamental_engine` cho Invest OS VN.

## Interface
```json
{"tool":"fundamental_engine","input":{},"output":{"data":[],"as_of":"ISO-8601","source":"string","quality_score":0.0}}
```

## Requirements
- Idempotent.
- Log source + timestamp.
- Return empty with error_code, không hallucinate.
- Validate ticker chuẩn HOSE/HNX/UPCOM.

## Failure Modes
- stale_data, missing_ticker, provider_down, schema_invalid.
