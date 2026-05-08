# Exploratory scan scripts archive — 2026-05-08

Archived instead of keeping in production `scripts/`:

- `fireant_foreign_click_scan.js`
- `fireant_scan_playwright.js`
- `fireant_ws_scan.js`
- `scan_derivatives_js.py`
- `scan_derivatives_sources.py`

Reason: these are useful research/debug scanners, but not production-safe pipeline tools. They may write raw browser/websocket artifacts, depend on transient frontend bundles, and can accidentally capture token-bearing URLs unless redaction is handled by caller.

Production replacements now committed:

- `scripts/fireant_adapter.py`
- `scripts/fireant_supplement_reports.py`
- `scripts/refresh_derivatives_live.py`
- `scripts/build_hf_lens_data_rich_report.py`

Rule: keep archived scanners for reference only. Do not call from live pipeline or user-facing report builder.
