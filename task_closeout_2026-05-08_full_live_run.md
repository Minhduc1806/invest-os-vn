# invest-os-vn full live run closeout — 2026-05-08

## Fix
- Fixed `scripts/run_pipeline.py` live fundamentals mapping:
  - from `data_live/fundamentals_sample.vn.json`
  - to `data_live/fundamentals_live.vn.json`
- Added live preflight regeneration:
  - `scripts/fundamental_real_layer.py`
- Root cause fixed: live pipeline previously hit quality gate because sample/partial fundamentals had `quality_score=0.72`; real full fundamentals has `quality_score=0.88`.

## Verified pass
- `python -m pytest tests -q` -> `14 passed`
- Full live chain rerun after fix:
  - `eod_market_brief --live`
  - `stock_signal_scan --live --universe investable`
  - `portfolio_daily_advice --live`
  - `company_deep_dive --ticker FPT --live --no-refresh`
- Output JSON/MD artifacts validated parse/non-empty.

## Commits
- `2fd7067 Fix live fundamentals input path`
- `28bd58e Add full live run output artifacts`
- `5acc8f3 Add final full live PDF report HTML`

## Final report to remember
- Final PDF:
  - `C:\Users\DUC\Desktop\InvestOS_VN_Full_Live_Run_2026-05-08\invest-os-vn-bao-cao-hanh-dong-HF-lens-data-rich-2026-05-08.pdf`
- Final HTML:
  - `C:\Users\DUC\Desktop\InvestOS_VN_Full_Live_Run_2026-05-08\invest-os-vn-bao-cao-hanh-dong-HF-lens-data-rich-2026-05-08.html`
- Source HTML in repo:
  - `outputs/invest-os-vn-bao-cao-hanh-dong-HF-lens-data-rich-2026-05-08.html`

## Raw full-live outputs committed
- `outputs/eod_market_brief.json`
- `outputs/eod_market_brief.md`
- `outputs/stock_signal_scan_investable.json`
- `outputs/stock_signal_report_investable.md`
- `outputs/portfolio_daily.json`
- `outputs/portfolio_daily.md`
- `outputs/company_deep_dive.json`
- `outputs/company_deep_dive.md`
