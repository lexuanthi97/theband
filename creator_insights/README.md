# Search Insights cho kênh Tự động hóa

App tự tìm mỗi ngày những gì người Việt đang tìm trên TikTok về **PLC, HMI, servo, biến tần, tự động hóa và mua bán thiết bị**, giống tính năng *Creator Search Insights* của TikTok Studio.

Dashboard: `https://lexuanthi97.github.io/theband/insights/` (sau khi merge vào nhánh chính và bật GitHub Pages).

## App làm gì

| Tính năng giống TikTok | Ở app này |
|---|---|
| Tab chủ đề ("Đề xuất cho bạn", các nhóm) | 6 nhóm: PLC, HMI & SCADA, Servo, Biến tần, Kiến thức, Mua bán |
| Độ phổ biến tìm kiếm | Điểm 0–100 tính từ thứ hạng gợi ý tìm kiếm TikTok + Google + YouTube |
| Xu hướng tìm kiếm | Đánh dấu **Đang tăng**, **Giảm**, **Mới**, biểu đồ 14 ngày |
| Content gap | **Cơ hội nội dung**: có người tìm nhưng TikTok còn ít nội dung |
| Tìm kiếm liên quan | Lấy từ gợi ý TikTok cho từng từ khóa hot |
| Gợi ý làm video | 3 ý tưởng video + hashtag cho từng từ khóa, nút chép nhanh |

## Cách hoạt động

1. Mỗi sáng 06:17 (giờ VN), GitHub Actions chạy `python -m creator_insights collect`.
2. App gửi khoảng 400 lượt tra gợi ý tìm kiếm (mỗi lượt cách nhau 0,8 giây) cho các từ khóa gốc trong `config.json`, kèm biến thể như "… là gì", "… cơ bản", "… giá".
3. Lọc bỏ từ khóa lạc đề (ví dụ "lập trình game"), chấm điểm và so sánh với các ngày trước.
4. Ghi kết quả vào `insights/data/` rồi commit. Dashboard đọc các file này.

## Chạy trên máy (Windows / Mac / Linux)

Chỉ cần Python 3.10 trở lên, không phải cài thêm gói nào.

```bash
python -m creator_insights collect          # tạo báo cáo hôm nay
python -m creator_insights serve            # mở http://localhost:8765
python -m creator_insights lookup "servo"   # tra nhanh trên terminal
```

Khi chạy `serve`, dashboard có thêm nút **Tra cứu trực tiếp**: gõ bất kỳ từ khóa nào (ví dụ "plc fx5u") để hỏi TikTok, Google và YouTube ngay lúc đó.

Muốn máy Windows tự chạy hằng ngày: mở Task Scheduler, tạo task chạy `python -m creator_insights collect` lúc 6:00, thư mục bắt đầu là thư mục repo.

## Tùy chỉnh chủ đề

Sửa `creator_insights/config.json`:

- `seeds`: từ khóa gốc để đi tìm, ví dụ thêm `"plc inovance"`.
- `terms`: từ giúp app nhận ra một từ khóa thuộc nhóm nào.
- `brands`: các hãng; một từ khóa có tên hãng + từ kỹ thuật cũng được giữ lại.
- `modifiers`: biến thể ghép vào sau từ khóa gốc.
- `max_requests`, `request_delay_seconds`: giới hạn số lượt gọi và tốc độ.

## Giới hạn cần biết

- TikTok không công khai số lượt tìm kiếm. **Độ phổ biến là điểm tương đối**, suy ra từ thứ hạng gợi ý, không phải số lượt tìm thật.
- **Cơ hội nội dung là ước tính.** Nên mở "Xem trên TikTok" để kiểm tra số video thực tế trước khi làm.
- App dùng endpoint gợi ý tìm kiếm công khai của TikTok. Nếu TikTok thay đổi hoặc chặn IP của GitHub Actions, workflow sẽ báo lỗi và **giữ nguyên báo cáo cũ**. Khi đó, chạy `collect` trên máy rồi push lên.
- Xu hướng (Đang tăng / Mới) chỉ có sau ít nhất 2 ngày dữ liệu.
