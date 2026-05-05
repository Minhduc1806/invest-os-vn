# Tool Spec: fdata_hose_universe

## Purpose
Lấy đủ dữ liệu toàn bộ cổ phiếu đang niêm yết HOSE từ FData local. Không lọc thanh khoản, không giới hạn 245 mã.

## Implemented Files
```text
scripts/fdata_hose_universe.py
scripts/fdata_hose_breadth.py
```

## Data Source
```text
C:\Users\DUC\Documents\FDATA\Common\symbols.dat
C:\Users\DUC\Documents\FDATA\Common\ICBs.dat
C:\Users\DUC\Documents\FDATA\AmiBroker\EOD\stock\*.dat
```

## Commands
```bash
python scripts/fdata_proto_tool.py --sample FPT,MWG,VCB,SSI
python scripts/fdata_hose_universe.py --timeframe EOD
python scripts/fdata_hose_breadth.py
python scripts/run_pipeline.py --config orchestrator.yaml --pipeline stock_signal_scan --live
```

## Outputs
```text
data_live/fdata_hose_all_bars.json
outputs/fdata_hose_all_bars.json
outputs/fdata_hose_all_bars.md
outputs/fdata_hose_breadth.json
outputs/fdata_hose_breadth.md
```

## Verified Current Run
- HOSE metadata symbols: 431.
- Parsed bars: 428.
- Missing DAT: 3.
- Latest date: 2026-05-04 for 428 symbols.

## Rule
- `fdata_hose_all_bars.json`: all HOSE listed, no liquidity filter.
- `fdata_investable_bars.json`: filtered universe for investable signal quality.
- Strategy modules must state which universe they use.
