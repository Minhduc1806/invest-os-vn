# Walk-Forward Backtest — Regime Aware

Train: 2025-05-09 → 2026-02-03 | Test: 2026-02-04 → 2026-05-05

Train signals: 5081 | Test signals: 0 | Regime counts: {'risk_on': 0, 'neutral': 0, 'risk_off': 0}

## Calibration by regime
```json
{
  "setup": {
    "risk_on": [
      "pullback",
      "trend_follow",
      "breakout",
      "base_building"
    ]
  },
  "sector": {
    "risk_on": [
      "Thực phẩm và đồ uống",
      "Bán lẻ",
      "Ngân hàng",
      "Xây dựng và Vật liệu",
      "Bất động sản",
      "Dịch vụ tài chính",
      "Bảo hiểm",
      "Tài nguyên Cơ bản",
      "Dầu khí",
      "Du lịch và Giải trí"
    ]
  }
}
```

