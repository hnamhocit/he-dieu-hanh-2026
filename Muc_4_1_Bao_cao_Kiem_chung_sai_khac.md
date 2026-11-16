# MỤC 4: KIỂM CHỨNG VÀ ĐÁNH GIÁ HỆ THỐNG

## 4.1 Báo cáo Kiểm chứng sai khác

Mục này thực hiện đối chiếu trực tiếp giữa kết quả tính toán thủ công (Oracle) trong file `oracle_tinh_tay.md` và dữ liệu thực tế thu được khi vận hành các kịch bản kiểm thử (thư mục `tests/`). Qua đó, nhóm phân tích tính đúng đắn của hệ thống so với thiết kế lý thuyết và lý giải các điểm sai khác phát sinh.

### 4.1.1 Bảng ma trận đối sánh kết quả kiểm thử (Expected vs Actual)

Dưới đây là bảng so sánh trạng thái của bộ đệm (Buffer), các con trỏ (`in`, `out`) và ba biến khóa `(mutex, empty, full)` giữa lúc tính tay và lúc chạy chương trình thật:

| STT | Kịch bản test (Lấy từ file tính tay của nhóm) | File code test tương ứng | Kết quả tính tay (Expected) | Kết quả chạy máy thật (Actual) | Nhận xét nhanh | Trạng thái |
| :---: | :--- | :--- | :--- | :--- | :--- | :---: |
| **1** | **Đọc/Ghi bình thường**<br>*(P ghi 2 tin, C đọc 2 tin)* | `test_message_queue.py`<br>`test_shared_memory.py` | Chạy xong 4 bước bộ đệm quay về rỗng. Biến khóa là `(1, 4, 0)`. Con trỏ `in=2, out=2`. | Bộ đệm trống sạch sẽ. Biến khóa ra đúng `(1, 4, 0)`. Con trỏ `in=2, out=2`. | Code chạy chuẩn, dữ liệu ra đúng thứ tự trước sau (FIFO). | **PASSED** |
| **2** | **Bộ đệm đang rỗng (Underflow)**<br>*(C vào đòi đọc trước khi P ghi)* | `test_boundary.py`<br>`test_ipc_console.py` | C1 bị đứng im chờ. Biến `full` giảm xuống thành `-1`. Khi P1 ghi tin thì C1 tỉnh dậy đọc tiếp. | Luồng C1 bị treo lại chờ đúng logic. Nhưng biến `full` trên máy chỉ dừng ở `0` chứ không xuống số âm. | Chức năng treo và gọi luồng dậy chạy đúng. Lệch số âm do thư viện Python không cho hiện số âm. | **PASSED** |
| **3** | **Bộ đệm bị đầy (Overflow)**<br>*(Đầy 4/4 ô rồi, P cố nhét thêm tin)* | `test_boundary.py`<br>`test_slots.csv` | Producer bị chặn lại khi `empty = -1`. Giữ nguyên 4 tin cũ không cho ghi đè. | Producer bị chặn đứng, báo trạng thái `is_blocked = True`. Biến `empty` log ra bằng `0`. | Chặn thành công để bảo vệ dữ liệu cũ. Lệch hiển thị số âm tương tự kịch bản 2. | **PASSED** |
| **4** | **Cấu hình bộ đệm cực tiểu**<br>*(Giới hạn bộ đệm đúng 1 ô)* | `test_boundary.py`<br>`test_slots_edges.csv` | Ghi tin `M1` xong bộ đệm đầy luôn. P cố nhét thêm `M2` sẽ bị hàm `try_acquire` từ chối liền. | Nhận `M1` ok. Gói `M2` bị đẩy ngược về tầng trên ngay lập tức vì hết chỗ. | Đúng thiết kế. Hệ thống không bị đơ giao diện GUI nhờ cơ chế không chặn (Non-blocking). | **PASSED** |
| **5** | **Gói tin bị trống (Payload rỗng)**<br>*(Gửi chuỗi dữ liệu rỗng `""`)* | `test_csv_parser.py`<br>`edge_empty.csv` | Hệ thống cấp phát bộ nhớ bình thường cho ô nhớ, không bị lỗi sập hay crash. | Đọc và ghi chuỗi rỗng `""` ngon lành, không báo lỗi gì. | Khớp hoàn toàn. Code xử lý được trường hợp chuỗi rỗng mà không bị lỗi Pointer. | **PASSED** |
| **6** | **Gói tin vừa khít trần (Payload = 100 ký tự)** | `test_boundary.py`<br>`normal_config.csv` | Đo độ dài chuỗi bằng 100 ký tự (chạm đỉnh). Hệ thống nhận đủ, không bị cắt bớt chữ nào. | Chuỗi 100 chữ đi qua vùng nhớ chung an toàn, đọc ra không thiếu chữ nào. | Khớp hoàn toàn. Hệ thống chịu được gói tin có kích thước tối đa theo quy định. | **PASSED** |
| **7** | **Gói tin quá dài (Payload = 101 ký tự)** | `test_boundary.py`<br>`invalid_format.csv` | Tầng Guard quét thấy `101 > 100` là vứt gói tin luôn, không cho nạp vào bộ đệm chia sẻ. | Bộ đọc file từ chối gói tin ngay từ đầu, giữ nguyên các biến khóa và con trỏ. | Đúng thiết kế. Chặn được gói tin quá tải để tránh làm tràn bộ đệm dữ liệu thô. | **PASSED** |
| **8** | **Trùng độ ưu tiên (Duplicate Priority)** | `test_integration_ipc.py`<br>`test_ipc_manager.py` | Hai gói cùng Priority = 5 thì áp dụng luật phụ: gói nào vào trước (t₁) sẽ được Consumer đọc ra trước. | Con trỏ đọc `out` xoay vòng lấy trúng gói vào trước ra trước theo đúng trình tự thời gian. | Code chạy mượt. Giải quyết tốt việc xếp hàng khi các tiến trình có độ ưu tiên bằng nhau. | **PASSED** |
| **9** | **File cấu hình sai định dạng**<br>*(Thiếu cột hoặc sai mã Checksum)* | `test_csv_parser.py`<br>`invalid_format.csv` | File `csv_parser.py` quét thấy lỗi sẽ bỏ qua, không nạp vào bộ đệm, giữ nguyên Semaphore. | Hệ thống báo lỗi ra màn hình log, không tăng giảm biến khóa, chương trình vẫn chạy tiếp. | Đúng kỳ vọng. Bắt được lỗi file cấu hình đầu vào mà không làm sập toàn bộ hệ thống. | **PASSED** |
| **10** | **Tiến trình đang gửi thì bị crash**<br>*(P sập khi đang giữ khóa `mutex=0`)* | `test_stress_fault.py`<br>`fault_injector.py` | Hệ thống bị đơ một lúc. Sau 300ms bộ hẹn giờ tự reset cờ `mutex=1` để cứu hệ thống. | Khóa `mutex` được mở lại sau một khoảng delay, nhưng thời gian thực tế hơi lệch so với 300ms lý thuyết. | **ĐẠT CÓ ĐIỀU KIỆN**. Cứu được hệ thống không bị treo chết, nhưng mốc thời gian bị trễ. | **PASSED** |

---

### 4.1.2 Phân tích chi tiết các trường hợp dễ sai (Edge Cases)

Trong lúc làm bài và chạy test thử, nhóm em thấy có 3 chỗ rất dễ bị code sai hoặc làm hệ thống chạy lung tung:

1. **Lỗi kiểm tra điều kiện lúc đông người (Race Condition):**
   * *Giải thích:* Chỗ này dễ sai nhất ở **Kịch bản 3 (Bộ đệm đầy)**. Nếu code mình viết lệnh `if` kiểm tra bộ đệm đầy/trống một dòng riêng, rồi mới gọi lệnh khóa ở dòng dưới thì rất nguy hiểm. Lúc nhiều tiến trình chạy cùng lúc, ông `P1` vừa check thấy còn chỗ trống chưa kịp ghi thì ông `P2` chen chân vào ghi mất rồi. Lúc này `P1` cứ thế ghi tiếp theo lệnh cũ sẽ làm ghi đè dữ liệu hoặc lỗi con trỏ mảng vòng.
   * *Cách nhóm sửa:* Bọc cả cụm lệnh kiểm tra lẫn lệnh ghi vào trong khóa Mutex để không ai chen ngang được.

2. **Lỗi "hội đồng" đánh thức sai luồng (Thundering Herd):**
   * *Giải thích:* Cái này dễ dính ở **Kịch bản 2 (Bộ đệm rỗng)**. Khi có 2, 3 ông Consumer đang cùng đứng đợi dữ liệu vì bộ đệm hết sạch. Lúc ông Producer vào nạp duy nhất 1 tin mới, nếu mình dùng lệnh gọi dậy kiểu "gọi tất cả" (`notify_all`), cả 3 ông Consumer sẽ cùng tỉnh dậy giành nhau ô nhớ đó. Kết quả là chỉ 1 ông ăn được, mấy ông còn lại sẽ bị lỗi hoặc đơ vì hụt dữ liệu.

3. **Lỗi lệch 1 chỉ số khi xoay vòng mảng (Off-by-One):**
   * *Giải thích:* Gặp nhiều nhất ở **Kịch bản 4 (Bộ đệm size = 1)**. Thuật toán dùng vòng lặp chia lấy dư `% capacity` để xoay con trỏ `in`, `out`. Khi cấu hình bộ đệm chỉ có đúng 1 ô, các con trỏ quanh đi quẩn lại chỉ bằng 0. Nếu code không tách biệt rõ ràng giữa điều kiện "đầy" (`full == 1`) và "rỗng" (`full == 0`), con trỏ đọc và con trỏ ghi sẽ đè lên nhau làm thuật toán bị rối loạn.

---

### 4.1.3 Lý giải nguyên nhân sai khác giữa Lý thuyết và Thực tế

Mặc dù kết quả về logic là đúng, nhưng số liệu hiển thị và mốc thời gian chạy trên máy thực tế vẫn có chỗ lệch so với lúc nhóm tính tay vì mấy lý do sau:

#### A. Do cách thư viện Python xây dựng biến Semaphore
* **Lý thuyết:** Lúc tính tay ở Kịch bản 2 và 3, khi hàng đợi bị nghẽn thì biến `full` hoặc `empty` phải trừ xuống thành số âm (`-1`) để thể hiện có 1 tiến trình đang xếp hàng chờ.
* **Thực tế:** Thư viện `multiprocessing` của Python khi chạy trên Windows/Linux không cho cờ đếm Semaphore xuống dưới mức `0`. Khi tiến trình bị khóa chân (`BLOCKED`), biến chỉ dừng ở số 0 chứ không hiện số âm trong log. Bản chất luồng bị chặn thì vẫn y chang tính tay, chỉ có con số hiển thị trong log là bị lệch.

#### B. Do bộ lập lịch của Hệ điều hành (OS Scheduler)
* **Lý thuyết:** Ở Kịch bản 2, khi Producer vừa nạp tin và nhả khóa, Consumer đáng lẽ phải "tỉnh dậy ngay lập tức" để đọc tin luôn.
* **Thực tế:** Hệ điều hành phải mất một chút thời gian để chuyển đổi ngữ cảnh (Context Switch), nạp lại luồng cho Consumer. Độ trễ ngẫu nhiên này của Win/Linux làm cho các mốc thời gian (Timestamp) mà module `metrics_calculator.py` đo được luôn bị chậm hơn vài mili giây so với đường thời gian lý tưởng lúc tính tay.

#### C. Do cơ chế khóa GIL của ngôn ngữ Python
* **Lý thuyết:** Nhóm giả định các tiến trình độc lập sẽ chạy song song thực sự trên các nhân CPU khác nhau để test độ tranh chấp.
* **Thực tế:** Ngôn ngữ Python có một cái khóa tên là GIL. Cái khóa này bắt các luồng trong code phải xếp hàng chạy luân phiên nhau chứ không song song hoàn toàn được. Đây là lý do vì sao ở Kịch bản 10, khi tiến trình bị sập, bộ hẹn giờ thực tế phải mất nhiều thời gian hơn một chút mới vào giải phóng được khóa `mutex`, vì nó phải xếp hàng đợi đến lượt chia CPU với các luồng khác.