# T+5 vs T+10 Comparison

| Tier | Horizon | N | AvgRet % | Win % | Target % | Stop % | Avg MAE % |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Tier A | T+5 | 1380 | 0.92 | 51.4 | 1.7 | 2.0 | -3.78 |
| Tier A | T+10 | 1380 | 2.01 | 55.8 | 6.6 | 4.9 | -5.02 |
| Tier B | T+5 | 6806 | 0.27 | 46.0 | 1.9 | 5.8 | -3.67 |
| Tier B | T+10 | 6806 | 0.6 | 45.1 | 6.0 | 12.6 | -5.02 |

## Kết luận
- Tier A: T+10 tốt hơn T+5 về avg return (2.01% vs 0.92%) và win-rate (55.8% vs 51.4%), nhưng MAE xấu hơn (-5.02% vs -3.78%).
- Tier B: T+10 avg return cao hơn (0.6% vs 0.27%), nhưng win-rate thấp hơn (45.1% vs 46.0%) và stop hit cao hơn (12.6% vs 5.8%).
- Rule đề xuất: Tier A dùng T+10 làm holding window chính; Tier B dùng T+5 hoặc chỉ watch/confirm, không kéo tới T+10 nếu chưa lên Tier A.
