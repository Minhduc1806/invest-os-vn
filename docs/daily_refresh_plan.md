# Daily refresh plan

Real-only daily sequence. Use PowerShell `;` separators.

## 1. Macro cache + macro rates

If Trading Economics direct HTTP is blocked, refresh extracted text cache first from browser/web_fetch saved text:

```powershell
python scripts\refresh_te_interest_text_cache.py --from-file path\to\te_interest_extracted_text.txt
python scripts\macro_rates_parser.py --merge-live
```

Cache policy: `data_live/raw/` ignored, stale cache > 1440m fails.

## 2. Market snapshot

```powershell
python scripts\data_adapters.py --market --tickers PNJ,FPT,MWG,VCB,SSI,HPG,TCB,MBB,VIC,VHM,GVR,STB,VPB,CTG,ACB,MSN,VNM,GAS,PLX,SAB,VRE,VJC,POW,SHB,TPB,HDB,LPB,VIB,BCM,BID
```

## 3. HOSE EOD + investable universe

```powershell
python scripts\fdata_hose_universe.py --timeframe EOD
python scripts\fdata_universe_filter.py
```

## 4. News

```powershell
python scripts\refresh_news_live.py --allow-partial
```

Refresh `data_live/news_live.vn.json` from real sources only. No mock/sample/placeholder.

## 5. Gate + reports + validation

```powershell
python scripts\phase4_real_data_gap_audit.py --mode eod
python scripts\run_pipeline.py --config orchestrator.yaml --pipeline portfolio_daily_advice --live --universe investable
python scripts\run_pipeline.py --config orchestrator.yaml --pipeline eod_market_brief --live --universe investable
python scripts\run_pipeline.py --config orchestrator.yaml --pipeline stock_signal_scan --live --universe investable
python scripts\validate_phase5_reports.py
```

Expected:

- `PHASE4_REAL_DATA_READY`
- `OK portfolio_daily_advice`
- `OK eod_market_brief`
- `OK stock_signal_scan`
- `PHASE5_REPORTS_CLEAN`

## Phase 6 automation

Manual run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\daily_refresh_phase6.ps1
```

Register Windows Task Scheduler daily 18:10 local time:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\register_phase6_daily_task.ps1
```

Task name: `InvestOSVN Phase6 Daily Refresh`.
Logs: `logs\phase6_daily_refresh_*.log`.
