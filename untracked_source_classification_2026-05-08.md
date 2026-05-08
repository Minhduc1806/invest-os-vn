# Untracked source classification — 2026-05-08

## Keep for later cleanup, not committed now

### FireAnt/debug browser scans
- `scripts/fireant_foreign_click_scan.js` — exploratory Playwright click scan; writes `outputs/fireant_scan/`.
- `scripts/fireant_scan_playwright.js` — exploratory dashboard request/response scan; writes raw HTML/screenshot/requests.
- `scripts/fireant_ws_scan.js` — exploratory websocket frame scan; raw token-bearing URL risk unless redacted.

### Old/mojibake report builders
- `scripts/build_hf_lens_data_rich_fireant.py`
- `scripts/build_hf_lens_data_rich_template0507.py`
- `scripts/build_hf_lens_market_action_template.py`

These contain mojibake Vietnamese and hard-coded Desktop destination paths. Do not commit before rewriting into clean UTF-8/template-safe report builder.

### Derivatives exploratory ingest
- `scripts/refresh_derivatives_live.py`
- `scripts/scan_derivatives_js.py`
- `scripts/scan_derivatives_sources.py`

Useful research, but still exploratory and token/source brittle. Needs tests, redaction, source policy, and `.gitignore` review before commit.

### Templates
- `templates/HF_LENS_DATA_RICH_TEMPLATE.md` has mojibake text and points to a binary PDF template.
- `templates/invest-os-vn-bao-cao-hanh-dong-HF-lens-data-rich-template.pdf` is binary generated artifact; do not commit until template policy decided.

## Already committed safe FireAnt pieces
- `scripts/fireant_adapter.py`
- `scripts/fireant_supplement_reports.py`
- `tests/test_fireant_adapter.py`
- `fireant_source_review_2026-05-08.md`

## Recommendation
Next: move exploratory scripts/templates to `_archive/` or rewrite UTF-8 clean builders + tests, then commit only production-grade source.
