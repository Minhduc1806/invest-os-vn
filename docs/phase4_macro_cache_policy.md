# Phase 4 macro cache policy

## Scope

`data_live/raw/` is live fetch cache. It is ignored by git. Do not commit raw HTML/text cache.

## Trading Economics interest-rate fallback

Direct HTTP for `https://tradingeconomics.com/vietnam/interest-rate` can return `HTTP Error 403: Forbidden`.
Production parser may use extracted real page text from:

`data_live/raw/te_interest_rate_fetch_text.txt`

Rules:

- cache must come from browser/web_fetch extracted text of real Trading Economics page
- parser records `source_mode: extracted_text_cache`
- cache older than 1440 minutes fails
- missing cache + TE HTTP 403 fails real-only gate
- no mock, no hardcoded policy-rate fallback

## Refresh command

Preferred, when browser/web_fetch text saved to file:

```powershell
python scripts\refresh_te_interest_text_cache.py --from-file path\to\te_interest_extracted_text.txt
python scripts\macro_rates_parser.py --merge-live
python scripts\phase4_real_data_gap_audit.py --mode eod
```

HTTP attempt, if not blocked:

```powershell
python scripts\refresh_te_interest_text_cache.py
```

Validation requires text like:

`The benchmark interest rate in Vietnam was last recorded at 4.50 percent.`

If validation fails, command exits non-zero and does not provide fake data.
