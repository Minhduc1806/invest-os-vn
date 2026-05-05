# Stock Signal Scan — Investable Universe

**Thời điểm dữ liệu:** 2026-05-05 12:26–12:37 GMT+7  
**Pipeline:** `stock_signal_scan`  
**Chế độ lọc:** investable  
**Quality gate:** đạt, `quality_score = 1`, không có cảnh báo chất lượng  
**Lưu ý dữ liệu:** nguồn `vnstock_history_adapter_partial_market`; thanh khoản thị trường/sector ghi nhận `0 tỷ VND`, nên không dùng để gán nhãn dẫn dắt tuyệt đối.

---

## 1. Tóm tắt hành động

Thị trường nghiêng **risk-off nhẹ** dù VNINDEX tăng **0.81%**. Lý do: độ rộng yếu, breadth **0/4**, sector positive ratio **0%**, dòng tiền ngoại ghi nhận **0 tỷ VND**. Không đủ bằng chứng để gọi nhóm/mã nào là “dẫn dắt”.

Ưu tiên hiện tại:

| Nhóm | Mã | Hành động |
|---|---|---|
| Watch | DXP, LLM | Theo dõi breakout, chỉ hành động khi giá giữ vùng vào + volume xác nhận |
| Idea | DXS, VHM, VRE, DXG | Ý tưởng quan sát, chưa nâng cấp vì điểm thấp hơn hoặc volume/RS chưa đủ chắc |
| Tránh mua đuổi | VRE, HNG, NVL nếu RSI căng | Chỉ chờ pullback/confirm lại, không mua khi mất tỷ lệ R/R |

---

## 2. Market regime

**Regime:** risk_off  
**Risk appetite:** 52.5/100  
**Confidence:** 0.74

Bằng chứng:

- VNINDEX: **+0.81%**
- Breadth adv/dec: **0.00 (0/4)**
- Sector positive ratio: **0%**
- Foreign net flow: **0 tỷ VND**

Đọc nhanh: chỉ số xanh nhưng nền thị trường không lan tỏa. Vì vậy tín hiệu cổ phiếu phải xử lý theo hướng **chọn lọc, giảm size, cần xác nhận volume**.

---

## 3. Sector theo dữ liệu hiện tại

| Sector | Change | RS20D | Value |
|---|---:|---:|---:|
| Bán lẻ | -0.12% | -0.66 | 0 tỷ VND |
| Ngân hàng | -1.48% | -0.75 | 0 tỷ VND |
| Chứng khoán | -1.44% | -1.12 | 0 tỷ VND |

Không gán nhãn “nhóm dẫn dắt” vì dữ liệu breadth/giá trị không đủ xác nhận. Chỉ kết luận: dữ liệu sector hiện tại cho thấy **độ rộng yếu, thiếu xác nhận dòng tiền**.

---

## 4. Trade candidates — nhóm watch

### DXP — Watch

- **Score:** 0.80  
- **Confidence:** 0.78  
- **Entry zone:** 15.19–15.65  
- **Close:** 15.5  
- **MA20 / MA50:** 13.99 / 13.19  
- **RS20D:** 0.95  
- **Volume ratio 20D:** 2.9  
- **Risk:** ATR14 3.78%, RSI14 62.5  
- **Invalidation:** đóng cửa dưới 14.62 hoặc volume breakout thất bại.

**Kịch bản:** giá đang trên MA20/MA50, volume cao hơn trung bình, cấu trúc tốt hơn phần lớn danh sách. Có thể theo dõi breakout/hold vùng 15.19–15.65. Không mua nếu thủng 14.62.

---

### LLM — Watch

- **Score:** 0.80  
- **Confidence:** 0.78  
- **Entry zone:** 22.15–22.83  
- **Close:** 22.6  
- **MA20 / MA50:** 20.97 / 20.62  
- **RS20D:** 0.59  
- **Volume ratio 20D:** 6.01  
- **Risk:** ATR14 7.08%, RSI14 57.58  
- **Invalidation:** đóng cửa dưới 20.20 hoặc volume breakout thất bại.

**Kịch bản:** tín hiệu volume mạnh nhất nhóm watch, giá trên MA20/MA50. Rủi ro chính là ATR cao 7.08%, nên size phải nhỏ hơn DXP. Không đuổi nếu vượt vùng vào quá xa.

---

## 5. Watchlist mở rộng — nhóm idea

| Mã | Score | Entry zone | Invalidation | Risk chính | Nhận xét |
|---|---:|---|---|---|---|
| DXS | 0.55 | 7.71–7.95 | < 7.40 | ATR14 3.99%, vol_ratio 2.55 | Có volume, RS20D âm nhẹ; cần xác nhận thêm |
| VHM | 0.55 | 139.16–143.42 | < 128.73 | ATR14 6.23%, vol_ratio 0.85 | Trend mạnh, nhưng volume chưa xác nhận |
| VRE | 0.55 | 33.03–34.04 | < 31.58 | RSI14 77.98 | Quá nóng, ưu tiên chờ pullback |
| DXG | 0.55 | 15.19–15.65 | < 14.76 | ATR14 3.18%, RS20D -0.16 | Chỉ là idea, chưa đủ RS |
| VCG | 0.55 | 22.34–23.03 | < 21.71 | RSI14 48.48, RS20D -0.75 | Yếu hơn, cần cải thiện RS |
| KBC | 0.55 | 33.76–34.79 | < 33.02 | ATR14 2.76%, RS20D -0.19 | Setup nền, chưa nổi bật |
| TCH | 0.55 | 16.95–17.47 | < 16.17 | ATR14 4.34%, RS20D -1.0 | RS yếu, chỉ quan sát |
| NVL | 0.55 | 18.72–19.29 | < 17.63 | RSI14 68.75, ATR14 5.14% | Momentum có, rủi ro biến động cao |
| CEO | 0.55 | 17.35–17.88 | < 16.44 | ATR14 4.76%, RS20D -0.29 | Chưa đủ RS xác nhận |
| HNG | 0.55 | 6.86–7.07 | < 6.57 | RSI14 75.0 | Nóng, tránh mua đuổi |
| VHC | 0.55 | 60.47–62.32 | < 59.23 | ATR14 2.08%, RS20D -0.41 | Rủi ro thấp hơn, nhưng RS chưa tốt |
| PHR | 0.55 | 62.72–64.64 | < 61.44 | vol_ratio 2.87 | Volume tốt, RS20D âm |
| PSI | 0.55 | 8.23–8.48 | < 8.02 | vol_ratio 3.79 | Volume tốt, nhưng RS20D âm |
| TLD | 0.55 | 8.38–8.64 | < 8.21 | ATR14 0.89%, RSI14 68.42 | Biến động thấp, cần thanh khoản xác nhận |

---

## 6. Risk plan

- **Market risk:** regime risk-off, breadth yếu; không dùng full allocation.
- **Position sizing:**  
  - DXP: tối đa 0.5–1.0R nếu xác nhận.  
  - LLM: tối đa 0.3–0.7R vì ATR14 7.08%.  
  - Idea group: chỉ quan sát hoặc test size rất nhỏ nếu có xác nhận riêng.
- **Không mua đuổi:** nếu giá vượt entry zone >2–3% mà không có nền volume mới.
- **Stop/exit:** dùng invalidation từng mã; đóng dưới ngưỡng là loại setup.
- **Cash plan:** giữ tiền mặt cao hơn bình thường đến khi breadth và sector positive ratio cải thiện.

---

## 7. Kết luận

Danh sách hợp lệ sau quality gate: **DXP và LLM là 2 mã watch tốt nhất theo score**. Tuy nhiên thị trường vẫn chưa ủng hộ mua mạnh vì breadth yếu và dữ liệu dòng tiền chưa xác nhận. Kịch bản phù hợp: **theo dõi breakout có volume, vào nhỏ, cắt nhanh nếu mất invalidation**.

Không có nhãn “dẫn dắt” nào được dùng vì dữ liệu hiện tại không đủ hỗ trợ.
