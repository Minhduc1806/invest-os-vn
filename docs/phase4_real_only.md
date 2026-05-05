# Phase 4 real-only contracts

Real-only gate blocks missing, placeholder, stale, mock source, zero NAV, empty news, empty macro.

Required live files:
- `data_live/portfolio_real.json`: `as_of`, real `source`, `valuation`, `cash_vnd`, `positions`.
- `data_live/news_live.vn.json`: real `source`, `as_of`, `items[]`, dedupe key/title/url.
- `data_live/macro_rates_live.vn.json`: real `source`, `as_of`, `rates`/`series`.

Run order:
1. `python scripts/macro_rates_parser.py --te-interest-text-file data_live/raw/te_interest_rate_fetch_text.txt --merge-live`
2. `python scripts/phase4_real_data_gap_audit.py --mode eod`
3. `python scripts/run_pipeline.py --config orchestrator.yaml --pipeline portfolio_daily_advice --live --universe investable`
4. `python scripts/run_pipeline.py --config orchestrator.yaml --pipeline eod_market_brief --live --universe investable`
5. `python scripts/run_pipeline.py --config orchestrator.yaml --pipeline stock_signal_scan --live --universe investable`
6. `python scripts/phase4_e2e.py`

No fallback giả allowed. Mock requires explicit `--mock --allow-quality-warnings` and remains non-production.
