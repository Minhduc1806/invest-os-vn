# InvestOS VN — báo cáo hành động HF lens data-rich

## Mục tiêu
Template sạch UTF-8 cho báo cáo thị trường/danh mục dùng dữ liệu thật. Không chứa placeholder, mojibake, hoặc câu pipeline thay cho phân tích.

## Quy tắc nội dung
- Mỗi nhận định phải có số liệu cụ thể từ `outputs/` hoặc `data_live/`.
- Nếu thiếu dữ liệu, ghi đúng field thiếu: ví dụ `missing field: foreign_net_value`.
- Không dùng câu chung như “nguồn bổ sung”, “proxy” làm phân tích chính.
- Section stock signals không được trống; nếu không có setup đạt chuẩn, hiển thị nhóm điểm cao nhất dưới dạng non-buy monitoring list.
- Derivatives phải có basis, basis %, open interest, OI change, volume/value, foreign/proprietary net nếu có.
- Mỗi agent lens phải có: luận điểm số liệu, đọc chéo với lens khác, trigger hành động riêng.

## Kiểm trước publish
- Không có ký tự replacement `�`.
- Không có chuỗi mojibake như `NgA`, `t���`, `D?`, `Lu?n`.
- PDF/HTML tồn tại và size > 0 nếu build định dạng xuất bản.
- Nguồn dữ liệu live phải có `as_of` và `source`.
