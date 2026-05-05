# Invest OS VN Runbook

## Mục tiêu
Chạy end-to-end hệ điều hành đầu tư nhiều AI agent cho thị trường chứng khoán Việt Nam.

## Cấu trúc
```text
invest-os-vn/
  orchestrator.yaml
  agents/*.md
  tools/*.spec.md
  skills/*.yaml
  schemas/*.json
  reports/templates/*.md
  mock_data/*.json
  outputs/
  logs/
  state/
```

## Luồng chạy chuẩn
1. Nạp `orchestrator.yaml`.
2. Validate folder + file tồn tại.
3. Nạp `mock_data/*.json` hoặc data provider thật.
4. Chạy quality gate đầu vào: `as_of`, `source`, stale check.
5. Chạy agents theo pipeline.
6. Validate output bằng `schemas/*.json`.
7. Render markdown bằng `reports/templates/*.md`.
8. Ghi `outputs/*.json`, `outputs/*.md`, `logs/*.jsonl`.
9. Gửi kênh đích nếu bật Telegram/email/dashboard.

## Lệnh mô phỏng cho dev
```bash
python scripts/run_pipeline.py --config orchestrator.yaml --pipeline eod_market_brief --mock
python scripts/run_pipeline.py --config orchestrator.yaml --pipeline stock_signal_scan --mock
python scripts/run_pipeline.py --config orchestrator.yaml --pipeline portfolio_daily_advice --mock
python scripts/run_pipeline.py --config orchestrator.yaml --pipeline company_deep_dive --ticker FPT --mock
```

## Lệnh nối data thật qua adapter
```bash
python scripts/data_adapters.py --all --tickers FPT,MWG,VCB,SSI
python scripts/run_pipeline.py --config orchestrator.yaml --pipeline eod_market_brief --live
python scripts/run_pipeline.py --config orchestrator.yaml --pipeline stock_signal_scan --live --universe hose_all
python scripts/run_pipeline.py --config orchestrator.yaml --pipeline stock_signal_scan --live --universe investable
python scripts/run_pipeline.py --config orchestrator.yaml --pipeline company_deep_dive --ticker FPT --live
```

Ghi chú: adapter thật hiện dùng `vnstock`. Nếu thiếu full-market breadth/foreign flow/phái sinh, file live sẽ có `warnings`; hệ thống không được dùng nhãn dẫn dắt nếu dữ liệu ranking chưa đủ.

## OpenClaw mapping
- `agents/*.md`: system/developer prompt cho từng subagent.
- `skills/*.yaml`: workflow spec, trigger, steps, quality gate.
- `tools/*.spec.md`: contract để dev nối API/tool thật.
- `schemas/*.json`: output validator.
- `reports/templates/*.md`: final renderer.
- `orchestrator.yaml`: router + pipeline graph.

## Pipeline: eod_market_brief
Input: `market_snapshot`, `news`, `macro_rates`.
Agents: Market Strategist, News Editor, Rates Analyst, Data Designer.
Output: bản tin sau phiên, regime, risk appetite, sector table, watch conditions.

## Pipeline: stock_signal_scan
Input: `market_snapshot`, `ohlcv`.
Agents: Market Strategist, Technical Analyst, Quant Researcher.
Output: actionable/watch/idea/avoid với entry zone, invalidation, risk/reward.

## Pipeline: portfolio_daily_advice
Input: `portfolio`, `market_snapshot`, `news`, `ohlcv`.
Agents: Portfolio Advisor, News Editor, Technical Analyst.
Output: NAV/P&L, concentration risk, vị thế cần chú ý, action plan.

## Pipeline: company_deep_dive
Input: `fundamentals`, `news`, `ohlcv`, param `ticker`.
Agents: Fundamental Analyst, News Editor, Technical Analyst.
Output: hồ sơ doanh nghiệp, peer, valuation range, risks.

## Data freshness SLA
| Data | Max stale |
|---|---:|
| Intraday market | 30 phút |
| EOD market | 1 ngày |
| News | 1 ngày |
| Fundamentals | 12 tuần |
| Portfolio | 1 ngày |

## Quality gate bắt buộc
- Có `as_of`.
- Có `source`.
- Có `confidence` nếu là kết luận.
- Có `invalidation` nếu là tín hiệu cổ phiếu.
- Không dùng nhãn “dẫn dắt/mạnh nhất/yếu nhất” nếu không có ranking data.
- Không nói “đảm bảo lợi nhuận”.

## Human review
Cần review trước khi gửi public nếu:
- Dữ liệu stale.
- Tin nhạy cảm doanh nghiệp.
- Cảnh báo margin/call.
- Action đề xuất giảm/tăng tỷ trọng > 20% NAV.
- Confidence < 0.6 nhưng output có action.

## Production checklist
- [ ] Nối provider giá/khối lượng HOSE/HNX/UPCOM.
- [ ] Nối provider tin tức có URL nguồn.
- [ ] Nối DB danh mục khách hàng.
- [ ] Nối financial statements + sector mapping.
- [ ] Bật JSON schema validation.
- [ ] Bật audit log.
- [ ] Bật retry/backoff cho provider_down.
- [ ] Bật delivery Telegram/email.
- [ ] Chạy shadow mode 2 tuần trước khi dùng thật.

## Shadow mode
Chạy hệ thống sau phiên, lưu output, không gửi quyết định. So sánh:
- tín hiệu vs diễn biến T+1/T+5/T+20,
- false positive,
- false negative,
- drawdown sau tín hiệu,
- chất lượng action plan danh mục.

## Incident response
1. Dừng delivery public.
2. Gắn cờ run_id lỗi.
3. Lưu input/output/audit.
4. Xác định lỗi: data, prompt, tool, schema, renderer.
5. Fix + backtest lại với cùng input.
6. Ghi postmortem.

## Disclaimer chuẩn
Thông tin hỗ trợ quyết định, không phải khuyến nghị đầu tư cá nhân hóa bắt buộc mua/bán. Nhà đầu tư tự chịu trách nhiệm và cần quản trị rủi ro.
