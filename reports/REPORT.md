# Lab 25B — Report

**Họ tên / nhóm:** Trần Anh Đăng — **MSV:** 2A202602992  
**Commit:** `c12cffb` — commit chứa toàn bộ code, cấu hình và artifacts được chấm. **Điểm tự động:** 84/88 (public seed 25; 4 điểm dữ liệu ẩn chưa chấm).


## 1. Kết quả Game Day

Chạy bằng Python trong `.venv`: `python -m pytest tests/test_client.py -q` và `python scripts/run_gameday.py --client both`. Bộ public, seed 25: **11/11 test client pass**, naive **0/6**, resilient **6/6** băng pass.

Nguồn: [naive.json](gameday/naive.json), [resilient.json](gameday/resilient.json). Availability tính theo lượt user; p95 chỉ tính trên lượt thành công. Chi phí là đơn vị mô phỏng, không phải USD. Dấu `—` là không áp dụng, không phải 0.

| Băng | Client | availability | p95 (s) | amplification | retry_ratio | cost/turn | recovery (s) | PASS? |
|---|---|---:|---:|---:|---:|---:|---:|:---:|
| G1 | naive | 0.7194 | 7.157 | 7.738 | 6.738 | 2.163 | 4.0 | FAIL |
| G1 | resilient | 1.0000 | 4.776 | 1.062 | 0.002 | 2.101 | 0.0 | PASS |
| G2 | naive | 0.4560 | 15.034 | 9.904 | 8.904 | 4.627 | 155.0 | FAIL |
| G2 | resilient | 1.0000 | 10.920 | 1.041 | 0.007 | 2.119 | 0.0 | PASS |
| G3 | naive | 1.0000 | 4.768 | 1.164 | 0.164 | 2.328 | 0.0 | FAIL |
| G3 | resilient | 1.0000 | 4.660 | 1.060 | 0.034 | 2.145 | 0.0 | PASS |
| G4 | naive | 1.0000 | 13.764 | 1.004 | 0.004 | 2.008 | 0.0 | FAIL |
| G4 | resilient | 1.0000 | 5.562 | 1.015 | 0.002 | 2.072 | 0.0 | PASS |
| G5 | naive | 0.3699 | 5.359 | 17.030 | 16.030 | 2.124 | — | FAIL |
| G5 | resilient | 0.8179 | 5.477 | 1.003 | 0.002 | 2.504 | — | PASS |
| G6 | naive | 0.5170 | 4.836 | 12.344 | 11.344 | 2.009 | 0.0 | FAIL |
| G6 | resilient | 1.0000 | 5.961 | 1.055 | 0.019 | 2.189 | 0.0 | PASS |

G2 tăng availability từ 45,60% lên 100%, giảm amplification từ 9,904 xuống 1,041 và recovery từ 155 s xuống 0 s. Recovery 0 s nghĩa là cửa sổ đo ngay sau mốc phục hồi đã đạt ngưỡng, không có nghĩa mọi call đều nhanh. G2 vẫn có p95 10,920 s, là điểm cần cải thiện.

G5 đạt 81,79%, với 413 lượt bị từ chối do request sai; không retry lỗi client và không failover vô ích. G6 đạt 100%, không có route không tương thích dù gamma-mini nhận 446 attempt: chỉ call chat được phép tới model này.

## 2. Cấu hình client và lý do

Giữ cấu hình `client:` hiện có vì đạt cả 6 băng public. Số liệu chứng minh hiệu quả của cấu hình kết hợp ở seed 25, chưa tách riêng ảnh hưởng từng tham số hoặc chứng minh tối ưu. Băng ẩn chưa được kiểm chứng.

| Tham số | Giá trị | Lý do và số liệu đối chiếu |
|---|---:|---|
| attempt_timeout_s | 8 s | Chặn thời gian mắc kẹt ở một deployment, chừa thời gian fallback trong deadline 30 s. G6 có 78 timeout nhưng availability 100%, p95 5,961 s. Timeout thực tế còn bị giới hạn bởi deadline. |
| max_attempts_per_provider | 2 | Tối đa một retry transient cùng provider trước khi chuyển tiếp, còn phụ thuộc budget và breaker. G2 amplification 1,041 so với naive 9,904. Rate limit/quota đi qua nhánh cooldown riêng. |
| min_time_left_s | 1 s | Không gửi khi thiếu thời gian cho attempt có ích, đồng thời trả permit. Cả 11 test client pass, gồm test deadline; G6 không có give-up. |
| backoff_base_s / cap_s | 0,25 / 4 s | Jitter phân tán retry. Với một retry transient mỗi provider, khoảng thường dùng là 0–0,25 s; cap 4 s chưa chi phối. G3 retry_ratio 0,034, p95 4,660 s. |
| retry_budget_ratio | 0,1 | Nạp 0,1 token mỗi logical call; retry tiêu 1 token. G3 retry_ratio 0,034 ≤ 0,10. Không phải bảo đảm cứng 10% ở mọi thời điểm vì còn token ban đầu và hồi theo thời gian. |
| retry_budget_min_per_s / max_tokens | 0,5 / 20 | Cho phép retry khi traffic thưa và giới hạn token tích trữ. Kết hợp breaker, G2 retry_ratio 0,007; mục 3 sẽ đo riêng ảnh hưởng budget. |
| quota_cooldown_s | 300 s | Tránh gọi liên tục deployment hết credit. G5 chỉ có 2 lỗi insufficient_quota, amplification 1,003 và availability 81,79%. Cooldown lưu riêng từng deployment. |
| breaker.window_size / min_calls | 20 / 10 | Xét 20 kết quả gần nhất, chờ đủ 10 để tránh phản ứng với quá ít mẫu. G2 recovery 0 s và primary share sau phục hồi 100%. |
| breaker.failure_rate_threshold | 0,5 | Ngắt khi ít nhất nửa cửa sổ báo lỗi sức khỏe provider. G2 amplification 1,041; G3 availability 100%. Không tính 400, rate limit hay quota vào breaker. |
| breaker.slow_call_s / slow_rate_threshold | 5 s / 0,6 | Phát hiện call thành công nhưng chậm khi đạt 60% cửa sổ. G4 p95 giảm 13,764 → 5,562 s, availability giữ 100%. |
| breaker.open_duration_s | 10 s | Nghỉ rồi thử phục hồi; G2 recovery 0 s, primary share 100%. Không dùng thời điểm sự cố trong code. |
| breaker.half_open_max_probes / half_open_successes | 2 / 2 | Giới hạn 2 probe đang chạy, đủ 2 thành công thì đóng. Part B pass 13/13 test; G2/G4 primary share sau phục hồi đều 100%. |

### Quyết định khi nhận lỗi

| Lỗi | Breaker | Retry cùng provider | Failover | Cooldown |
|---|---|---|---|---|
| CLIENT_ERROR | Release, không tính sức khỏe | Không | Không; GiveUp(client_error) | Không |
| QUOTA_EXHAUSTED | Release | Không | Ngay | 300 s cho deployment báo lỗi |
| RATE_LIMITED | Release | Không trực tiếp trong nhánh lỗi | Ngay; hết lựa chọn có thể đợi cooldown ngắn phù hợp deadline | Theo retry_after; code dự phòng 1 s nếu thiếu hoặc bằng 0 |
| OVERLOADED / SERVER_ERROR / TIMEOUT | Ghi failure | Nếu chưa đủ 2 attempt, còn token, breaker cấp permit và còn thời gian | Khi không thể retry | Breaker quản lý, không đặt cooldown riêng |

`start` khởi tạo trạng thái và budget; `on_success` báo latency; `on_cancel` trả permit cho attempt bị hủy. Mỗi logical call bắt đầu từ primary. `ladder(tool)` lọc theo `supports_tools` nên loại gamma-mini.

Chỉ ResilientClient quyết định retry bằng action gửi simulator, không chồng retry ở app/gateway/SDK. G1 có 0 vi phạm retry-after; G5 có 0 retry lỗi client; G6 có 0 route không tương thích.



## 3. Ba thí nghiệm

Nguồn: [experiments.json](experiments.json). Tái lập bằng `python scripts/report_experiments.py`, seed 25. Script chỉ thay cấu hình trong bộ nhớ và dùng subclass cho thí nghiệm bỏ lọc tool; không sửa simulator, test hoặc client nộp bài.

### 3.1. Bật/tắt retry budget

Đặt `min_calls = 1000000000` để breaker không trip và `max_attempts_per_provider = 5`. Khi tắt budget, đặt ratio=100, max_tokens=1e9, min_per_s=1e6; các cấu hình khác giữ nguyên.

| Băng | Budget | Availability | Amplification | Retry ratio | Recovery (s) |
|---|---|---:|---:|---:|---:|
| G2 | Bật | 99,87% | 1,380 | 0,058 | 0 |
| G2 | Tắt | 96,66% | 1,675 | 0,495 | 25 |
| G3 | Bật | 100% | 1,136 | 0,068 | 0 |
| G3 | Tắt | 100% | 1,162 | 0,159 | 0 |

Ở G2, budget giảm retry ratio từ 0,495 xuống 0,058 và số call bỏ cuộc vì deadline từ 79 xuống 3. Ở G3, availability đều 100% nhưng tắt budget làm retry ratio 0,159 vượt ngưỡng 0,10. Breaker ngắt provider dựa trên sức khỏe; budget giới hạn lượng retry ngay cả khi breaker chưa đủ mẫu hoặc cấu hình sai. Khi breaker hoạt động đúng, cấu hình hiện tại đạt G2 amplification 1,041; vẫn cần cả hai vì hai cơ chế bảo vệ ở hai điều kiện khác nhau.

### 3.2. Timeout 30 giây

| Băng | Timeout | Availability | give_up_reasons | p95 lượt thành công (s) |
|---|---:|---:|---|---:|
| G6 | 8 s | 100% | Không | 5,961 |
| G6 | 30 s | 94,88% | deadline: 109; no_provider_available: 13 | 5,315 |
| G4 | 8 s | 100% | Không | 5,562 |
| G4 | 30 s | 100% | Không | 5,608 |

G6 mất 122 lượt thành công khi tăng timeout: chờ provider treo tiêu hết thời gian cần cho fallback. p95 giảm không phải cải thiện vì chỉ tính lượt thành công; các lượt chậm đã thất bại bị loại khỏi phân bố (survivorship bias). G4 gần như không đổi vì call chậm vẫn thường hoàn tất trước timeout cũ, còn slow-call breaker tiếp tục phát hiện qua latency. Timeout nên dựa trên phân vị latency lúc bình thường, deadline cả lượt và phần thời gian phải giữ cho fallback, không lấy nguyên deadline 30 s làm timeout mỗi attempt.

### 3.3. Bỏ lọc tool calling

| G6 | Availability | incompatible_routes | give_up_reasons | Cost/good turn |
|---|---:|---:|---|---:|
| Có lọc | 100% | 0 | Không | 2,189 |
| Không lọc | 90,19% | 234 | incompatible_model_output: 234 | 2,272 |

Không lọc năng lực làm 234 call đi tới model không hỗ trợ thao tác cần thiết. Với người dùng, hệ thống có thể trả lời bằng chữ nhưng không thực hiện được bước xử lý hoàn tiền, nên cả lượt thất bại. Model rẻ hơn không đồng nghĩa chi phí trên một lượt thành công thấp hơn: số này tăng từ 2,189 lên 2,272.

## 4. Workflow hoàn tiền

Nguồn: [workflows.json](workflows.json), 500 session cho mỗi executor.

| Executor | Completion | Crashes | Duplicate refunds | Duplicate emails | Lost refunds | Overpaid (cents) | Wasted LLM/crash |
|---|---:|---:|---:|---:|---:|---:|---:|
| naive | 100% | 81 | 128 | 81 | 0 | 1496700 | 1,123 |
| yours | 100% | 66 | 0 | 0 | 0 | 0 | 0,303 |

Key ổn định theo session và step ngăn side effect lặp lại khi payment đã chạy nhưng response mất hoặc worker chết. Chỉ key chưa đủ: chạy lại từ đầu vẫn tốn LLM và thực hiện lại các bước đọc; checkpoint giúp resume với kết quả đã lưu. Chỉ checkpoint cũng chưa đủ vì worker có thể chết sau payment nhưng trước khi lưu: lần chạy lại phải dùng cùng idempotency key. Ghi checkpoint trước payment có thể đánh dấu hoàn thành dù tiền chưa được chuyển, khiến lần resume bỏ qua và làm mất hoàn tiền. Executor để WorkerCrash truyền ra runner; chỉ retry lỗi dịch vụ. Số crash giữa hai lần chạy khác nhau do đường thực thi và số lần gọi dịch vụ khác nhau.

## 5. Alerting và error budget

Nguồn: [slo.json](slo.json). Độ trễ tính bằng phút từ lúc sự cố bắt đầu.

| Sự cố | Mong đợi | Naive | Burn-rate | Độ trễ naive / burn-rate |
|---|---|---|---|---|
| checkout_bug | page | Page | Page | 1 / 27 |
| provider_outage | page | Page | Page | 0 / 4 |
| deploy_blip | none | Page sai | Không page | Không áp dụng |
| slow_leak | ticket | Bỏ sót | Ticket, không page | Không phát hiện / 1337 |
| degraded_evening | page | Page | Page | 214 / 291 |
| night_spike | none | Page sai | Không page | Không áp dụng |
| small_bump | none | Page sai | Không page | Không áp dụng |

Burn-rate có 3 page, 1 ticket, **0 false page**; naive có 7 page, 0 ticket và 3 false page. Hai cửa sổ của mỗi luật đều phải vượt ngưỡng: 14,4× (60/5 phút), 6× (360/30 phút), 1× (4320/360 phút); prefix sum cho phép tính mỗi tổng cửa sổ trong O(1).

Trong 30 ngày có 25.901.755 request, 55.618 lỗi. Budget cho SLO 99,5% là 25.901.755 × 0,005 = **129.508,775 lỗi** (hiển thị 129.508,8); đã tiêu **42,95%**, còn **57,05%**, availability **99,7853%** nên **không đóng băng release**. `small_bump` dài 20 phút ở 12% lỗi không duy trì đủ mức burn trên cả cửa sổ dài và ngắn: nếu tải đều, đóng góp trong 1 giờ chỉ khoảng 4% lỗi (8× budget), thấp hơn 14,4×. Dữ liệu thật xác nhận không page; không đánh thức on-call chỉ vì một cửa sổ 5 phút vượt ngưỡng.

## 6. Postmortem — G2 với client naive

### Tóm tắt

Trong mô phỏng G2, alpha mất 75% năng lực từ t=120 đến t=300. NaiveClient khuếch đại 3.481 logical call thành 34.475 attempt, khiến 1.285/2.362 lượt user không thành công. Provider phục hồi ở t=300 nhưng cửa sổ đạt ngưỡng phục hồi chỉ bắt đầu tại t=455, trễ thêm 155 giây.

![G2: tải attempt và tỷ lệ call thành công của naive so với resilient](gameday/G2_overload_storm.png)

Nguồn: [JSON](gameday/naive.json), [CSV naive](gameday/naive_G2_overload_storm_timeseries.csv), [CSV resilient](gameday/resilient_G2_overload_storm_timeseries.csv). Biểu đồ dùng cửa sổ trượt 10 s; bảng dưới tổng hợp cửa sổ 30 s, tỷ lệ là call thành công / call hoàn tất, không phải availability theo user.

### Ảnh hưởng và budget tháng

Availability của toàn băng là **45,60%**, tức **54,40%** lượt không thành công; p95 của lượt thành công là 15,034 s. Khoảng từ trigger đến đầu cửa sổ phục hồi dài **335 s**, gồm 180 s giảm năng lực và 155 s kéo dài; không có nghĩa mọi request trong 335 s đều thất bại.

Để quy đổi sang budget tháng, giả định ShopAgent giữ tải **4 lượt/s** trong 30 ngày, SLO 99,5% tính theo lượt, và chỉ xảy ra sự cố này. Khi đó tổng tháng là 10.368.000 lượt, budget là 51.840 lượt lỗi; 1.285 lượt lỗi tiêu **2,48% budget**, còn **97,52%**, **không vượt budget tháng**. Đây là giả định ngoại suy riêng cho G2, không trộn với tập SLI 25.901.755 request ở mục 5; chưa có mẫu số tháng thì không thể khẳng định sự cố vượt budget.

### Timeline

| Khoảng giây ảo | Sự kiện | Attempts alpha/s | Calls OK/done | Success ratio |
|---|---|---:|---:|---:|
| 90–120 | Trước trigger | 7,93 | 234/234 | 100% |
| 120–150 | Alpha giảm 75% năng lực | 90,77 | 51/98 | 52,04% |
| 270–300 | Retry storm cuối thời gian giảm năng lực | 155,80 | 0/127 | 0% |
| 300–330 | Alpha phục hồi, call vẫn thất bại | 23,43 | 0/55 | 0% |
| 420–450 | Thất bại tiếp diễn sau trigger | 21,53 | 0/108 | 0% |
| 455–485 | Đạt ngưỡng phục hồi ≥95% | 10,87 | 352/368 | 95,65% |

### Trigger, nguyên nhân và vòng lặp duy trì

Trigger là mất năng lực GPU; nguyên nhân hệ thống là retry chồng 4×3×3, delay cố định 0,2 s, thiếu jitter, budget, breaker và fallback. Client timeout nhưng provider vẫn xử lý request cũ; attempt mới tiếp tục nối hàng đợi và tạo thêm timeout/quá tải. Ở t=300, năng lực trở lại không xóa hàng đợi đó, còn retry tiếp tục duy trì tải: đây là metastable failure. G2 ghi 2.737 timeout, 3.194 lỗi overloaded, 26.298 rate-limit và 28.381 vi phạm retry-after. Những chỉ số này phản ánh thiếu cơ chế kiểm soát tải và kiểm thử sự cố, không phải lỗi cá nhân.

Điều làm tệ hơn là chỉ gửi alpha, retry cả rate limit không chờ và không phối hợp các tầng retry. Điều giúp phục hồi ở thiết kế mới là một tầng retry có budget, ngắt provider lỗi/chậm, giới hạn probe và chuyển deployment phù hợp: availability đạt 100%, amplification 1,041 và recovery 0 s. Kết quả kết hợp không tự chứng minh từng thay đổi riêng lẻ; thí nghiệm mục 3 cung cấp đối chứng cho budget.

### Action items đề xuất

Owner theo vai trò; trong bài cá nhân, Trần Anh Đăng đảm nhiệm các vai trò này. Các mục dưới là kế hoạch kiểm chứng, không khẳng định đã triển khai cảnh báo production.

| Hành động | Loại | Owner | Cách kiểm chứng |
|---|---|---|---|
| Duy trì một tầng retry, jitter và token budget | Prevent | Đăng — client | CI G2 amplification ≤1,6; G3 retry_ratio ≤0,10; unit test retry pass |
| Giám sát timeout, overload, amplification và burn rate | Detect | Đăng — vận hành | Replay G2 phát hiện tải tăng; tập SLI public có 0 false page và phát hiện đủ sự cố |
| Breaker có slow-call detection, fallback theo capability | Mitigate | Đăng — reliability | G2 recovery ≤30 s, primary share ≥80%; G4 p95 ≤10 s; G6 incompatible_routes=0 |
| Kiểm thử HALF-OPEN và kết quả generation cũ | Prevent | Đăng — kiểm thử | Test giới hạn probe và bỏ qua kết quả cũ pass; replay nhiều seed trước phát hành |

## 7. Điểm yếu còn lại

G2 đã pass nhưng p95 **10,920 s**, cao hơn p95 G1 **4,776 s**, với 126 timeout. Khi đủ nhiều request đã gửi trước lúc breaker mở, chúng vẫn phải đợi timeout; breaker không thu hồi công việc đã chạy phía provider. Có thể thử giới hạn concurrency phía client, timeout riêng theo deployment dựa trên latency bình thường, hoặc giảm ngưỡng slow-call sau khi đo trade-off. Cần so sánh availability, chi phí và false trip trên nhiều seed trước khi đổi cấu hình; đây chưa phải cải tiến đã được triển khai. G5 cost/good turn **2,504** cũng cho thấy chi phí tăng khi chuyển sang beta.

## 8. Cache

Nguồn: [cached.json](cache/cached.json), [resilient.json](cache/resilient.json), [experiments.json](experiments.json); C1 public seed 25. Unit test cache: **17/17 pass**.

| Client | Availability | FAQ availability | Hit ratio | Stale served | Wrong | Outdated | Cost/good turn | PASS? |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| Không cache | 83,73% | 84,24% | 0% | 0 | 0 | 0 | 1,386 | FAIL |
| Cached | 91,17% | 96,40% | 57,90% | 152 | 0 | 4 | 0,965 | PASS |

### Cấu hình và thí nghiệm

| Tham số | Giá trị chọn | Căn cứ |
|---|---:|---|
| similarity_threshold | 0,97 | Không trả sai trên C1; ngưỡng 0,80 tạo 166 lỗi other_question. Chọn nghiêm ngặt nhưng chưa khẳng định tối ưu: 0,90 cũng không sai và rẻ hơn trên seed này. |
| ttl_s | 60 s | 4 câu outdated ≤15 và hit 57,9% ≥50%; TTL 30 s chỉ hit 49,5%, TTL 300 s có 95 outdated. |
| max_stale_s | 200 s | Cho phép giữ câu cũ qua khoảng outage; stale chỉ dùng sau GiveUp, vẫn kiểm tra scope và invalidation. So với 0 s, FAQ availability tăng 87,50% → 96,40%. |
| max_entries | 500 | Giới hạn bộ nhớ bằng LRU, unit test eviction pass; cấu hình này đạt hit 57,9%. Chưa thử sức chứa khác, không khẳng định 500 là tối thiểu hay tối ưu. |

**Ngưỡng similarity.** Giá trị đang chọn chính là 0,97 nên chạy thêm 0,90 làm đối chứng, không coi hai lần 0,97 là hai lựa chọn khác nhau.

| Ngưỡng | Hit ratio | Wrong answers | Outdated | Cost/good turn |
|---|---:|---:|---:|---:|
| 0,80 | 65,90% | 166 | 1 | 0,975 |
| 0,90 | 65,20% | 0 | 3 | 0,916 |
| 0,97 (chọn) | 57,90% | 0 | 4 | 0,965 |

Ở 0,80, cả 166 lỗi thuộc `other_question`; hit cao không đồng nghĩa câu trả lời đúng. Catalog mô phỏng có các cặp gần nghĩa nhưng khác nhu cầu: chính sách hoàn tiền/thời gian nhận tiền, đổi size/đổi màu, phí ship nội thành/ngoại tỉnh và phương thức thanh toán/COD. JSON chỉ thống kê theo loại lỗi, không đủ để gán số lỗi cụ thể cho từng cặp; ngưỡng 0,97 đánh đổi hit ratio để lọc nghiêm hơn, còn 0,90 là ứng viên cần kiểm chứng thêm trên nhiều seed.

**TTL.** Giữ ngưỡng 0,97 và stale 200 s:

| TTL | Hit ratio | FAQ availability | Outdated | Cost/good turn |
|---|---:|---:|---:|---:|
| 30 s | 49,50% | 96,16% | 2 | 1,020 |
| 60 s | 57,90% | 96,40% | 4 | 0,965 |
| 300 s | 70,10% | 96,28% | 95 | 0,882 |

TTL 60 s cân bằng freshness và hit ratio để đạt cả hai ngưỡng chấm; TTL 300 s tiết kiệm call nhưng giữ câu trả lời cũ quá lâu. Webhook giúp thay đổi được thông báo ở t=150, không giúp thay đổi phí ship không thông báo ở t=480. Khi provider khỏe, hết TTL buộc lấy lại câu trả lời; khi provider lỗi, thời gian giữ cũ tối đa còn chịu cửa sổ stale (TTL + max_stale_s), nên TTL không phải giới hạn tuyệt đối duy nhất trong mọi tình huống.

**Tắt stale-if-error.** Với max_stale_s=0, FAQ availability chỉ **87,50%**, hit **49,40%**, cost/good turn **1,024**, so với **96,40%**, **57,90%**, **0,965** khi giữ 200 s. Cấu hình chọn phục vụ 152 câu stale; tắt stale khiến entry hết TTL không còn cứu được FAQ trong outage. Cả hai vẫn có 4 outdated, phản ánh lỗi freshness do thay đổi không thông báo khác với tính sẵn sàng trong outage.

### An toàn dữ liệu và cảnh báo

Câu hỏi cá nhân bị loại khỏi cache kể cả cache theo user: cùng user có thể hỏi nhiều đơn có embedding rất giống, và trạng thái đơn/hoàn tiền/điểm thay đổi theo thời gian. User scope chỉ ngăn lẫn giữa người dùng, không bảo đảm đúng đối tượng hoặc dữ liệu mới; lab yêu cầu luôn đọc nguồn trực tiếp cho các câu này. Prompt version là scope bắt buộc; webhook xóa mọi entry phụ thuộc source đã đổi, kể cả entry stale.

Không chỉ alert availability tổng vì cache che khuất lỗi provider. Theo dõi thêm tỷ lệ lỗi/timeout của origin trên các lần gọi thật, trạng thái breaker, số GiveUp trước fallback cache, tỷ lệ stale được phục vụ và tuổi câu trả lời; dùng health probe riêng khi hit cache cao làm ít call tới origin. Trong C1, FAQ availability 96,40% cùng 152 câu stale phải được hiểu là hệ thống đang chạy chế độ suy giảm, không phải provider vẫn khỏe.

## Đối chiếu rubric và tái lập

- Mục 1–2: đủ 12 dòng so sánh và lý do cấu hình.
- Mục 3: đủ 3 thí nghiệm có số trước/sau; giữ nguyên client nộp bài.
- Mục 4–5: workflow, lý do cần key/checkpoint, error budget và freeze.
- Mục 6: biểu đồ, 6 mốc có số, trigger/root cause, vòng lặp sau phục hồi, action items có owner và phép đo.
- Mục 8: bảng cache, ngưỡng/TTL/stale, dữ liệu cá nhân và cảnh báo origin.

Chạy từ root repo với Python của `.venv`: `python scripts/report_experiments.py`, `python scripts/plot_timeseries.py --scenario G2_overload_storm`, `python scripts/grade.py`. Plot cần `pip install -e ".[plot]"`. Grader public seed 25 đạt **84/88**: 4 điểm SLO ẩn chưa chấm; 12 điểm báo cáo do giảng viên đánh giá, không tự nhận đủ điểm. Kết quả mô phỏng không chứng minh pass mọi seed/băng ẩn.
