# Bước 2 — Baseline NaiveClient

Chạy bằng Python trong `.venv` (tương đương `make baseline`):

```powershell
.\.venv\Scripts\python.exe scripts/run_gameday.py --client naive
```

Seed cấu hình: **25**. Kết quả: **0/6 băng PASS**.
Nguồn: `gameday/naive.json` và các file `gameday/naive_*_timeseries.csv`.

| Băng | Availability | p95 (s) | Amplification | Retry ratio | Check không đạt |
|---|---:|---:|---:|---:|---|
| G1 | 71,94% | 7,157 | 7,738 | 6,738 | Availability, retry-after, amplification |
| G2 | 45,60% | 15,034 | 9,904 | 8,904 | Availability, amplification, recovery |
| G3 | 100% | 4,768 | 1,164 | 0,164 | Retry ratio |
| G4 | 100% | 13,764 | 1,004 | 0,004 | p95 |
| G5 | 36,99% | 5,359 | 17,030 | 16,030 | Retry lỗi client, availability |
| G6 | 51,70% | 4,836 | 12,344 | 11,344 | Availability |

## Số liệu G2 dành cho postmortem

- Tổng lượt user: **2.362**; thành công: **1.077**; không thành công: **1.285** (54,40%).
- Logical calls: **3.481**; attempts: **34.475**, tất cả tới `alpha`.
- Amplification: **9,904**, yêu cầu ≤ 1,6.
- Availability: **45,60%**, yêu cầu ≥ 95%.
- Recovery: **155 s** sau khi provider phục hồi ở t=300; cửa sổ phục hồi bắt đầu tại **t=455**. Yêu cầu ≤ 30 s.
- p95 lượt thành công: **15,034 s**; chi phí mỗi lượt thành công: **4,627 đơn vị mô phỏng**, không phải USD.
- Lỗi: 2.737 timeout, 3.194 overloaded, 26.298 rate limited, 5 API error.
- Vi phạm retry-after: **28.381**.

### Timeline từ CSV

Mỗi dòng tổng hợp khoảng 30 giây `[bắt đầu, kết thúc)`. Tỷ lệ thành công dưới đây là `sum(calls_ok) / sum(calls_done)` của **LLM call**, khác availability theo lượt user ở trên.

| Khoảng giây ảo | Attempts alpha/s | Call thành công / hoàn tất | Tỷ lệ | Diễn giải |
|---|---:|---:|---:|---|
| 90–120 | 7,93 | 234/234 | 100% | Trước sự cố |
| 120–150 | 90,77 | 51/98 | 52,04% | Alpha mất 75% năng lực; tải attempt tăng mạnh |
| 270–300 | 155,80 | 0/127 | 0% | Cuối sự cố, retry storm vẫn tiếp diễn |
| 300–330 | 23,43 | 0/55 | 0% | Provider đã phục hồi, client vẫn chưa phục hồi |
| 420–450 | 21,53 | 0/108 | 0% | Thất bại kéo dài sau khi hết trigger |
| 455–485 | 10,87 | 352/368 | 95,65% | Cửa sổ đạt ngưỡng phục hồi 95% |

### Cơ chế cần giải thích ở Bước 9

Trigger là mất năng lực GPU. Retry chồng ba tầng (tối đa 36 attempt/call), delay cố định và thiếu phân loại lỗi, jitter, budget, breaker, fallback khuếch đại tải. Client timeout không hủy công việc phía provider; hàng đợi và retry tiếp tục duy trì quá tải sau khi năng lực đã trở lại. Đây là cơ chế metastable failure cần phân tích, không phải lỗi của một cá nhân.

## Các ràng buộc đã ghi nhận

- Chỉ dùng thời gian ảo `now` cho logic sinh viên.
- `tool` chỉ được gửi tới deployment hỗ trợ tool calling; cả lượt có deadline 30 s.
- Phân biệt 429 rate limit với 429 hết quota; không retry/failover vô ích với request sai.
- Không sửa simulator, naive client, test gốc, services/runner hoặc kịch bản sự cố.
- Không hard-code tên băng hay thời điểm; giảng viên dùng băng ẩn và nhiều seed.

Đây là ghi chép baseline; chưa phải báo cáo hoàn chỉnh hay kết quả của ResilientClient.
