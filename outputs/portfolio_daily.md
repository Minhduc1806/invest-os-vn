# Báo cáo danh mục cá nhân — 2026-05-05 12:39 GMT+7

## 1. Tóm tắt điều hành

Danh mục hiện ghi nhận trạng thái không có vị thế cổ phiếu, không có NAV thực, không có cash thực và không có P&L thực để đánh giá. Vì vậy, khuyến nghị hành động chính là chưa ra quyết định mua/bán theo danh mục hiện tại; cần nhập dữ liệu vị thế thật trước khi tối ưu tỷ trọng, drawdown, concentration hoặc beta.

Mức tin cậy: 0.76  
Chất lượng dữ liệu: đạt quality gate, quality_score 1  
Cảnh báo chất lượng: không có

## 2. NAV / P&L

| Chỉ tiêu | Giá trị |
|---|---:|
| NAV | 0 VND |
| Giá trị cổ phiếu | 0 VND |
| Tiền mặt | 0 VND |
| Tỷ trọng tiền mặt | 0% |
| P&L tổng | 0 VND |
| P&L tổng | 0% |

Diễn giải: số liệu hiện tại phản ánh chưa có danh mục thực được nhập, không nên hiểu là danh mục đang giữ 100% tiền mặt thật.

## 3. Vị thế hiện tại

Không có vị thế cổ phiếu.

| Mã | Tỷ trọng | Giá trị | P&L | Ghi chú |
|---|---:|---:|---:|---|
| Không có | 0% | 0 VND | 0% | Chưa có dữ liệu vị thế |

## 4. Rủi ro chính

- Không có dữ liệu vị thế thật, nên không thể tính drawdown thực, beta thực, concentration theo mã/ngành, hoặc mức chịu lỗ.
- Nguồn `manual_real_portfolio_required` cho thấy danh mục cần nhập thủ công dữ liệu thật trước khi tư vấn cá nhân hóa.
- Có nguồn `mock_news_hub`, nên không dùng phần tin tức để ra quyết định giao dịch chắc chắn.
- Không có ngành/mã dẫn dắt được xác nhận từ danh mục, nên không gán nhãn leadership.

## 5. Quyết định / hành động đề xuất

- Chưa mua/bán theo báo cáo này.
- Giữ trạng thái chờ cho đến khi có positions thật hoặc kế hoạch giải ngân thật.
- Nếu anh DUC muốn tư vấn danh mục cá nhân, cần nhập tối thiểu: mã, số lượng, giá vốn, giá hiện tại hoặc nguồn giá, NAV/cash, mức chịu lỗ tối đa, thời gian nắm giữ.
- Sau khi có dữ liệu thật, chạy lại phân tích: tỷ trọng từng mã, ngành, P&L, drawdown, beta gần đúng, mức lệch so với mục tiêu và kế hoạch tái cân bằng.

## 6. Điều kiện kích hoạt phân tích tiếp theo

Chỉ nâng báo cáo lên mức hành động khi có đủ:

1. Danh sách vị thế thực.
2. Giá vốn và giá thị trường cập nhật.
3. Cash còn lại.
4. Khẩu vị rủi ro: thận trọng / cân bằng / tăng trưởng.
5. Mức cắt lỗ danh mục hoặc từng mã.
6. Mục tiêu: bảo toàn vốn, trading ngắn hạn, hay tích sản trung hạn.

## 7. Nguồn dữ liệu

- manual_real_portfolio_required
- vnstock_history_adapter_partial_market
- mock_news_hub
- fdata_universe_filter

## 8. Kết luận

Danh mục hiện chưa đủ dữ liệu để đưa khuyến nghị cá nhân hóa. Hành động đúng là không giao dịch theo báo cáo này, ưu tiên nhập vị thế thật rồi mới tính rủi ro và kế hoạch tái cân bằng.

Lưu ý: kế hoạch danh mục cần đối chiếu khẩu vị rủi ro thật và lệnh thực tế.
