# OpenClaw End-to-End Example

## Manual run prompt
Dán prompt này vào OpenClaw session để chạy mock end-to-end:

```text
Load `invest-os-vn/orchestrator.yaml`. Run pipeline `eod_market_brief` using mock inputs. Use agents in `agents/*.md`, tool contracts in `tools/*.spec.md`, validate against `schemas/*.json`, render `reports/templates/eod_market_brief.md`, save outputs to `invest-os-vn/outputs/`.
```

## Expected output files
```text
invest-os-vn/outputs/eod_market_brief.json
invest-os-vn/outputs/eod_market_brief.md
invest-os-vn/logs/invest_os_vn_audit.jsonl
```

## Minimal OpenClaw skill call shape
```yaml
skill: eod_market_brief
config: invest-os-vn/orchestrator.yaml
inputs:
  market_snapshot: invest-os-vn/mock_data/market_snapshot.vn.json
  news: invest-os-vn/mock_data/news_sample.vn.json
  macro_rates: invest-os-vn/mock_data/macro_rates_sample.vn.json
outputs:
  markdown: invest-os-vn/outputs/eod_market_brief.md
  json: invest-os-vn/outputs/eod_market_brief.json
```

## Success criteria
- Markdown report rendered.
- JSON output valid.
- Every claim has source/as_of.
- Stock signals include invalidation.
- No unsupported leadership label.
