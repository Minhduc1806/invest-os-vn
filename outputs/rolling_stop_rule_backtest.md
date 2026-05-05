# Rolling Stop Rule Backtest — OOS Full Replay

| Strategy | N | AvgRet % | Win % | Avg MAE % | Avg exit day | Target % | Stop % |
| --- | --- | --- | --- | --- | --- | --- | --- |
| fixed_stop_T10 | 52 | -0.81 | 44.2 | -5.6 | 9.4 | 7.7 | 7.7 |
| breakeven_after_1R | 52 | -0.93 | 38.5 | -5.53 | 9.1 | 7.7 | 15.4 |
| time_stop_T5_if_negative | 52 | -0.01 | 38.5 | -4.66 | 7.0 | 7.7 | 1.9 |
| trailing_low3_after_T3 | 52 | 0.02 | 34.6 | -4.18 | 5.8 | 7.7 | 88.5 |

Selected OOS stop rule: `trailing_low3_after_T3`
