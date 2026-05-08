# Derivatives/report cleanup closeout — 2026-05-08

## Scope

- Wired `data_live/derivatives_live.vn.json` into live orchestrator inputs for EOD, portfolio, and company-deep-dive pipelines.
- Added derivatives freshness/quality checks to `scripts/phase4_real_data_gap_audit.py`.
- Added derivatives brief output to EOD, portfolio, and company reports.
- Archived exploratory scanner scripts away from production `scripts/`.
- Exported clean derivatives HTML/PDF delivery files to Desktop.

## Validation

- `python scripts/run_pipeline.py --config orchestrator.yaml --pipeline eod_market_brief --live --no-refresh` passed.
- `python scripts/run_pipeline.py --config orchestrator.yaml --pipeline portfolio_daily_advice --live --no-refresh` passed.
- `python scripts/run_pipeline.py --config orchestrator.yaml --pipeline company_deep_dive --ticker FPT --live --no-refresh` passed.
- `python scripts/build_hf_lens_data_rich_report.py` passed.
- `python -m pytest tests -q` passed: `19 passed`.
- PDF/HTML spot-check: no mojibake detected; Vietnamese renders; derivatives table includes VN30F symbols, basis, OI, OI Δ, volume/value, foreign/proprietary fields.

## Delivery files

- `C:\Users\DUC\Desktop\InvestOS_VN_Full_Live_Run_2026-05-08\invest-os-vn-hf-lens-data-rich-clean-derivatives-2026-05-08.html`
- `C:\Users\DUC\Desktop\InvestOS_VN_Full_Live_Run_2026-05-08\invest-os-vn-hf-lens-data-rich-clean-derivatives-2026-05-08.pdf`
- Screenshot proof:
  `C:\Users\DUC\Desktop\InvestOS_VN_Full_Live_Run_2026-05-08\invest-os-vn-hf-lens-data-rich-clean-derivatives-2026-05-08-page1.png`

## Notes

- `derivatives_live.vn.json` remains live/runtime data and should not be committed blindly.
- Production source policy remains public/no-secret; FireAnt public token is runtime-only and redacted from raw artifacts.
- Next optional production step: wire derivatives into any older/full PDF builder still used downstream, or retire those builders in favor of `scripts/build_hf_lens_data_rich_report.py`.
