# Tool Spec: fdata_adapter

## Purpose
Dùng nguồn FData có sẵn trên máy anh DUC để cấp dữ liệu giá/khối lượng thật cho Invest OS VN.

## Detected Source
```text
C:\Users\DUC\Documents\FDATA\AmiBroker\EOD\stock\*.dat
C:\Users\DUC\Documents\FDATA\AmiBroker\EOD\index\*.dat
C:\Users\DUC\Documents\FDATA\AmiBroker\15m\stock\*.dat
C:\Users\DUC\Documents\FDATA\Common\symbols.dat
```

## Implemented Adapter
```text
scripts/fdata_adapter.py
```

## Observed AmiBroker DAT Format
- Header: 40 bytes.
- Record size: 40 bytes.
- Struct: `<IIfffffII`.
- Fields: `date_yyyymmdd`, `time`, `open`, `high`, `low`, `close`, `volume`, `open_interest`, `aux`.

## Generated Live Files
```text
data_live/ohlcv_sample.vn.json
data_live/market_snapshot.vn.json
```

## Commands
```bash
python scripts/fdata_adapter.py --all --tickers FPT,MWG,VCB,SSI
python scripts/run_pipeline.py --config orchestrator.yaml --pipeline stock_signal_scan --live
python scripts/run_pipeline.py --config orchestrator.yaml --pipeline eod_market_brief --live
```

## Data Quality Notes
- FData EOD stock files found and usable as primary price/volume source.
- Full-market breadth now scans all `EOD/stock/*.dat`; latest test universe size: 1676 symbols.
- `Common/symbols.dat` / `symbolInfo.dat` parser added best-effort metadata extraction; industry still partial because FData protobuf schema not fully decoded.
- Intraday adapter supports `--timeframe 15m` reading `AmiBroker/15m/stock/*.dat`.
- Stale check added: `--fallback-intraday --stale-days N` uses 15m when EOD stale.
- Foreign flow/proprietary flow not present in parsed EOD DAT.

## Production Next
- Improve protobuf decode for exact exchange/ngành from `symbolInfo.dat`.
- Add official sector map CSV override.
- Add liquidity value if FData exposes turnover value elsewhere.
- Add derivative basis from `AmiBroker/EOD/der` or `15m/der`.
