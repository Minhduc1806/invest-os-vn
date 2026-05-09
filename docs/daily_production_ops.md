# Daily production ops

## Standard commands

Full refresh, cron-friendly quiet log:

```bash
python scripts/run_daily_production.py --quiet
```

Smoke using existing cache, no provider refresh:

```bash
python scripts/run_daily_production.py --no-refresh --quiet
```

## Notes

- Daily runner sequence: `eod_market_brief`, `stock_signal_scan --universe investable`, `portfolio_daily_advice`, `company_deep_dive --ticker FPT`.
- Full PDF builds automatically after `company_deep_dive` via pipeline post-step.
- `--no-refresh` still runs the real-data gate, but skips provider refresh before the gate.
- If cache is stale, `--no-refresh` smoke should fail fast; run full refresh command first.
