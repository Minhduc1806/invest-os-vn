# Tool Spec: live_data_adapter

## Purpose
Nối dữ liệu thật cho Invest OS VN thay mock data.

## Current Adapter
File triển khai: `scripts/data_adapters.py`.
Provider hiện tại: `vnstock` Python package.

## Generated Files
```text
data_live/market_snapshot.vn.json
data_live/ohlcv_sample.vn.json
data_live/fundamentals_sample.vn.json
```

## Commands
```bash
python scripts/data_adapters.py --all --tickers FPT,MWG,VCB,SSI
python scripts/run_pipeline.py --config orchestrator.yaml --pipeline stock_signal_scan --live
python scripts/run_pipeline.py --config orchestrator.yaml --pipeline eod_market_brief --live
python scripts/run_pipeline.py --config orchestrator.yaml --pipeline company_deep_dive --ticker FPT --live
```

## Interface
```json
{
  "tool": "live_data_adapter",
  "input": {
    "provider": "vnstock",
    "tickers": ["FPT", "MWG", "VCB", "SSI"],
    "datasets": ["market_snapshot", "ohlcv", "fundamentals"]
  },
  "output": {
    "files": ["data_live/*.json"],
    "as_of": "ISO-8601",
    "warnings": []
  }
}
```

## Limitations
- Free `vnstock` adapter có thể thiếu foreign flow, phái sinh, full-market breadth.
- `market_snapshot` breadth hiện tính theo universe tickers truyền vào nếu không có full market provider.
- Fundamentals schema có thể partial do khác version `vnstock`.
- Nếu provider lỗi, adapter fallback mock và ghi `adapter_warning`.

## Production Upgrade
- Thay `build_market_live()` bằng provider full HOSE/HNX/UPCOM.
- Thêm industry classification chính thức.
- Thêm foreign flow + proprietary flow + derivatives.
- Thêm paid news API có URL nguồn.
- Thêm DB portfolio thật.
