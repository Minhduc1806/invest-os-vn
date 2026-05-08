# FireAnt source review — 2026-05-08

## Scope
Reviewed current FireAnt supplement source after global macro and gate work:

- `scripts/fireant_adapter.py`
- `scripts/fireant_supplement_reports.py`
- `tests/test_fireant_adapter.py`

## Verdict
FireAnt remains suitable as supplemental public-dashboard source, not primary source. Current adapter has usable REST ICB sector/industry extraction and opportunistic SignalR capture, but report supplement script needs encoding cleanup before promotion into production report path.

## Findings

1. `scripts/fireant_adapter.py` is structurally acceptable for experimental supplemental ingest.
   - Public dashboard only; no login bypass.
   - Bearer token extracted at runtime and redacted in saved worker artifact.
   - Writes policy metadata: `cophieu68_primary_fireant_supplement_for_realtime_breadth_sector_intelligence`.
   - Normalizes ICB industry flows, realtime prices, breadth, foreign flow, trading statistics, financial ratios.

2. SignalR capture is best-effort.
   - Absence of `order_books` / `ticker_flows` during short capture is warning, not hard failure.
   - `GetTradingStatistics` and `GetFinancialInfos` symbol mapping uses `GetSymbols_order`; if row counts mismatch, falls back to `row_index_only` to avoid fake ticker attribution.

3. `scripts/fireant_supplement_reports.py` has mojibake text.
   - Examples in generated labels: `t���`, `l���p`, `NgA�nh`.
   - Numeric enrichment logic is usable, but markdown text should be rewritten UTF-8 clean before user-facing report inclusion.

4. `tests/test_fireant_adapter.py` covers key safety behaviors but also has mojibake fixtures.
   - Tests cover industry normalization, token extraction, row-to-symbol mapping, and fallback when counts mismatch.
   - Need add adapter build smoke with mocked network to protect no-secret/no-store behavior.

## Recommendation

- Keep FireAnt scripts untracked until cleanup pass.
- Next cleanup pass:
  1. Fix UTF-8/mojibake in FireAnt supplement report and tests.
  2. Add mocked `build_payload(phases="phase1")` unit test.
  3. Add `.gitignore` entries for FireAnt raw websocket/debug artifacts if not already covered.
  4. Only then commit FireAnt adapter + tests as supplemental source.

## Production boundary
Do not make FireAnt a required live preflight source yet. Keep cophieu68 as baseline; FireAnt can enrich breadth/sector/foreign-flow only when quality score passes and warnings are visible.
