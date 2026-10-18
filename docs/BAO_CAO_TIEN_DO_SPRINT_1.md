# BÁO CÁO TIẾN ĐỘ & KẾT QUẢ THỰC HIỆN SPRINT 1
**HỌC PHẦN: HỆ ĐIỀU HÀNH - ĐỀ TÀI: MÔ PHỎNG CÁC CƠ CHẾ GIAO TIẾP LIÊN TIẾN TRÌNH (OS_IPC_09)**

---

## 1. THÔNG TIN CHUNG VÀ MỤC TIÊU ĐỀ TÀI

### 1.1. Mục tiêu đề tài (OS_IPC_09)
* **Nhiệm vụ trọng tâm:** Hiện thực và mô phỏng trực quan hai cơ chế giao tiếp liên tiến trình (IPC) kinh điển: **Bộ nhớ chia sẻ (Shared Memory)** và **Hàng đợi thông điệp (Message Queue)**.
* **Điểm cốt lõi:**
  * Giải quyết trọn vẹn bài toán đồng bộ hóa (Synchronization) và loại trừ tương hỗ (Mutual Exclusion).
  * Chống xung đột dữ liệu (Race Conditions) khi nhiều tiến trình đồng thời đọc/ghi.
  * Xử lý an toàn các trạng thái tới hạn của bộ nhớ đệm: **Tràn bộ đệm (Buffer Full)** và **Đói dữ liệu (Buffer Empty)**.
  * Cung cấp cơ chế ghi vết (Trace Log) chi tiết từng bước trao đổi dữ liệu để phục vụ đối soát với bảng tính tay (Oracle).
* **Cam kết kỹ thuật:** 
  * Ứng dụng Desktop GUI chuyên nghiệp (Python / PyQt6) chạy mượt mà trên Windows.
  * Tuyệt đối không sử dụng Console thuần túy hay Web App.
  * Kiến trúc phân tầng tách bạch hoàn toàn giữa **Tầng Lõi Thuật toán (Core IPC Logic)** và **Tầng Giao diện người dùng (GUI)**.

---

## 2. KIẾN TRÚC HỆ THỐNG VÀ KẾT QUẢ TÁI CẤU TRÚC (CLEAN TRASH)

Nhằm đảm bảo tính module hóa cao, dễ bảo trì và mở rộng cho Sprint 2, nhóm đã chuẩn hóa toàn bộ mã nguồn theo cấu trúc phân tầng:

```text
he-dieu-hanh-2026/
├── src/
│   ├── core/                      # TẦNG LÕI THUẬT TOÁN IPC (Decoupled Core)
│   │   ├── ipc_interface.py       # Abstract Base Class IIPCMechanism & IPCResult
│   │   ├── shared_memory.py       # Lõi Shared Memory (Circular Buffer + Mutex + Semaphore)
│   │   └── message_queue.py       # Lõi Message Queue (FIFO/Priority + Monitor/Condition)
│   ├── gui/                       # TẦNG GIAO DIỆN NGƯỜI DÙNG (PyQt6 Desktop)
│   │   ├── main_window.py         # Cửa sổ chính, tích hợp QThreadPool, non-blocking UI
│   │   ├── styles.py              # Dark Theme & CSS Stylesheet chuẩn
│   │   └── widgets.py             # Các thành phần widget hiển thị trạng thái
│   ├── utils/                     # TẦNG TIỆN ÍCH DỮ LIỆU
│   │   ├── csv_parser.py          # Bộ phân tích và kiểm tra tính hợp lệ của CSV kịch bản
│   │   └── csv_reader.py          # Xử lý ngoại lệ file đọc an toàn
│   └── main.py                    # Điểm khởi động ứng dụng
├── data/
│   ├── input/                     # Dữ liệu kịch bản CSV đầu vào
│   │   ├── sample_config.csv      # File kịch bản mẫu chuẩn 10 bước
│   │   ├── normal_config.csv      # Kịch bản chạy bình thường
│   │   ├── edge_empty.csv         # Kịch bản kiểm thử biên bộ đệm rỗng (Underflow)
│   │   └── invalid_format.csv     # Kịch bản kiểm thử dữ liệu sai định dạng
│   └── output/                    # Nơi xuất trace log mô phỏng (.csv)
├── docs/                          # TÀI LIỆU HỌC THUẬT & ĐẶC TẢ
│   ├── Test_plan.md               # Kế hoạch kiểm thử 10 test case chi tiết
│   ├── Oracle_tinh_tay.md         # Bảng tính tay Oracle đối soát trạng thái Semaphore
│   ├── checklist_cham_diem.md     # Checklist theo rubric giảng viên
│   ├── message_queue_spec.md      # Đặc tả gói tin MessagePacket & hàng đợi
│   └── queue_mechanism_spec.md    # Đặc tả cơ chế điều phối hàng đợi
└── tests/                         # BỘ KIỂM THỬ TỰ ĐỘNG (UNIT TEST SUITE)
    ├── test_shared_memory.py      # Kiểm thử lõi Shared Memory (6 test cases)
    ├── test_message_queue.py      # Kiểm thử lõi Message Queue (11 test cases)
    ├── test_csv_parser.py         # Kiểm thử Parser (13 test cases)
    ├── test_csv_reader.py         # Kiểm thử bắt ngoại lệ file (18 test cases)
    └── test_main_window.py        # Kiểm thử GUI Offscreen (11 test cases)
```

### Báo cáo Dọn dẹp & Tái cấu trúc mã nguồn (Clean Trash):
1. **Loại bỏ trùng lặp:** Xóa bỏ hoàn toàn các file clone đối phó (`ipc_manager2.py`, `ipc_manager3.py`), quy hoạch lõi Message Passing vào một module duy nhất `src/core/message_queue.py`.
2. **Tuân thủ chuẩn Interface:** Module `MessageQueue` được tái cấu trúc kế thừa trực tiếp từ `IIPCMechanism`, cung cấp đầy đủ các phương thức `produce()`, `consume()` và đặc biệt là `get_state()` để GUI có thể lấy snapshot vẽ đồ thị.
3. **Chuẩn hóa thư mục:** Toàn bộ file test console và tài liệu nằm rải rác ngoài thư mục gốc đã được di chuyển về đúng các thư mục `/docs` và `/tests`.

---

## 3. HIỆN THỰC THUẬT TOÁN ĐỒNG BỘ CỐT LÕI

### 3.1. Cơ chế Bộ nhớ chia sẻ (Shared Memory - Bounded Buffer)
* **Cấu trúc dữ liệu:** Mảng vòng (Circular Buffer) kích thước cố định $N$.
* **Cơ chế đồng bộ hóa:**
  * `mutex = threading.Lock()` (Nhị phân, khởi tạo = 1): Bảo vệ Critical Section (ghi/đọc ô nhớ, tăng/giảm con trỏ `in_ptr`, `out_ptr`).
  * `empty = threading.Semaphore(capacity)` (Đếm ô trống): Khi `empty == 0`, Producer dừng chờ.
  * `full = threading.Semaphore(0)` (Đếm ô có tin): Khi `full == 0`, Consumer dừng chờ.
* **Đặc tính Non-blocking phục vụ GUI:**
  * Hỗ trợ tham số `timeout=0.0`. Khi buffer đầy hoặc rỗng, hàm lập tức trả về `IPCResult(status="BLOCKED")` mà không làm đóng băng (freeze) giao diện người dùng.

### 3.2. Cơ chế Hàng đợi thông điệp (Message Queue)
* **Cấu trúc gói tin (`MessagePacket`):**
  * `id`: Định danh duy nhất của gói tin.
  * `sender` / `receiver`: Định danh tiến trình gửi và nhận.
  * `message`: Nội dung thông điệp (tính toán tự động `payload_size_bytes`).
  * `delay_ms`: Độ trễ mô phỏng.
  * `priority`: Độ ưu tiên (hỗ trợ điều phối Priority Queue).
* **Cơ chế đồng bộ hóa (Monitor Pattern):**
  * Sử dụng `threading.Lock()` kết hợp 2 Condition Variables: `not_full` và `not_empty`.
  * Producer chờ trên `not_full.wait()` khi hàng đợi đạt ngưỡng `capacity`.
  * Consumer sau khi lấy tin thành công sẽ phát tín hiệu `not_full.notify()`.
  * Hỗ trợ linh hoạt 2 chế độ điều phối: **FIFO thuần túy** và **Priority Queue** (tin ưu tiên cao hơn luôn được xử lý trước).

---

## 4. LUỒNG DỮ LIỆU, GIAO DIỆN & TRUY VẾT (TRACE LOG)

1. **Đầu vào (Input):**
   * Người dùng nạp kịch bản thông qua file CSV (ví dụ: `data/input/sample_config.csv`).
   * Module `CSVParser` tự động kiểm tra cú pháp, encoding UTF-8 BOM, validate các trường bắt buộc (`id`, `action`, `sender`, `receiver`) và các tham số tùy chọn (`delay_ms`, `priority`).
2. **Xử lý & Hiển thị trên GUI (PyQt6):**
   * Quá trình nạp và kiểm tra file diễn ra hoàn toàn trên Worker Thread (`QRunnable`), đảm bảo giao diện đạt 60 FPS mượt mà.
   * Giao diện bố trí 4 khối trực quan:
     * **Panel Nạp CSV & Trạng thái:** Báo mã lỗi chi tiết nếu dữ liệu không hợp lệ.
     * **Panel Cấu hình tham số:** Chọn cơ chế IPC (Shared Memory / Message Queue), dung lượng Buffer ($N$), số Producer / Consumer.
     * **Khu vực Trực quan hóa (Buffer Visualization):** Vẽ trực quan từng ô nhớ, con trỏ đọc/ghi và trạng thái khóa Mutex.
     * **Bảng Trace Log thời gian thực:** Hiển thị chi tiết từng bước thực thi kèm timestamp chính xác đến mili-giây.
3. **Đầu ra (Output):**
   * Nút **Xuất Trace CSV** cho phép trích xuất toàn bộ lịch sử chạy của phiên mô phỏng ra file CSV để phục vụ đối chiếu, kiểm chứng.

---

## 5. KẾT QUẢ KIỂM THỬ VÀ ĐỐI SOÁT TÍNH ĐÚNG ĐẮN

### 5.1. Bảng đối soát tính toán bằng tay (Oracle)
Nhóm đã xây dựng tài liệu [docs/Oracle_tinh_tay.md](file:///home/hnamhocit/Workspace/learning/he-dieu-hanh-2026/docs/Oracle_tinh_tay.md) tính toán trước kết quả lý thuyết cho 3 kịch bản cốt lõi:
1. **Kịch bản 1 (Bình thường - Không tranh chấp):** Producer ghi liên tiếp 2 tin ($M_1, M_2$), Consumer đọc lần lượt 2 tin ra. Kết quả: thứ tự FIFO chính xác, buffer quay về trạng thái rỗng `(mutex=1, empty=4, full=0)`.
2. **Kịch bản 2 (Biên Underflow - Đọc khi đệm rỗng):** Consumer gọi đọc khi bộ đệm rỗng. Hệ thống từ chối an toàn, chuyển tiến trình sang trạng thái `BLOCKED`, không crash app.
3. **Kịch bản 3 (Biên Overflow - Ghi khi đệm đầy):** Producer cố tình đẩy vượt dung lượng 4/4. Hệ thống chặn đứng tiến trình ghi, bảo vệ an toàn toàn vẹn dữ liệu đã có.

### 5.2. Kế hoạch kiểm thử (Test Plan)
Tài liệu [docs/Test_plan.md](file:///home/hnamhocit/Workspace/learning/he-dieu-hanh-2026/docs/Test_plan.md) liệt kê chi tiết **10 ca kiểm thử bắt buộc**:
* 5 ca kiểm thử cho Shared Memory: Đọc/Ghi cơ bản, Buffer Overflow, Buffer Underflow, Race Condition, Thu hồi tài nguyên.
* 5 ca kiểm thử cho Message Queue: Hàng đợi FIFO, Hàng đợi ưu tiên Priority, Mailbox Full, Giả lập độ trễ (Delay time), Định tuyến sai tiến trình.

### 5.3. Kết quả chạy Unit Test tự động
Dự án được bảo vệ bởi **60 ca kiểm thử tự động (100% Passed / Skipped GUI offscreen an toàn)**:
```text
Ran 60 tests in 0.725s
OK (skipped=11)
```
* `test_shared_memory.py`: 6/6 tests Passed.
* `test_message_queue.py`: 11/11 tests Passed.
* `test_csv_parser.py`: 13/13 tests Passed.
* `test_csv_reader.py`: 18/18 tests Passed.
* `test_main_window.py`: 11 tests (sẵn sàng chạy trên môi trường có màn hình hiển thị).

---

## 6. DANH MỤC TIẾN ĐỘ 25 TASKS SPRINT 1 (JIRA)

| Mã Task | Tóm tắt nội dung công việc | Người phụ trách | Trạng thái |
|:---|:---|:---:|:---:|
| `HDH-6` | Khởi tạo GitHub repo, phân quyền cộng tác viên | Hoàng Nam (PM) | **Hoàn thành** |
| `HDH-7` | Cấu hình branch protection rules cho nhánh main | Hoàng Nam (PM) | **Hoàn thành** |
| `HDH-8` | Soạn thảo `.gitignore` chuẩn cho Python | Hoàng Nam (PM) | **Hoàn thành** |
| `HDH-9` | Tạo cấu trúc thư mục dự án `/src`, `/docs`, `/data`, `/tests` | Hoàng Nam (PM) | **Hoàn thành** |
| `HDH-10` | Soạn đặc tả cấu trúc và đồng bộ Shared Memory | Hoàng Nam (PM) | **Hoàn thành** |
| `HDH-13` | Soạn đặc tả cấu trúc gói tin MessagePacket | Lương Sơn | **Hoàn thành** |
| `HDH-14` | Xác định cơ chế hàng đợi FIFO / Priority | Lương Sơn | **Hoàn thành** |
| `HDH-15` | Khai báo signature module Message Passing | Lương Sơn | **Hoàn thành** |
| `HDH-16` | Khởi tạo dự án Desktop GUI PyQt6 | Hải Đăng | **Hoàn thành** |
| `HDH-17` | Dựng wireframe phác thảo giao diện chi tiết | Hải Đăng | **Hoàn thành** |
| `HDH-18` | Thống nhất schema dữ liệu CSV với toàn nhóm | Hải Đăng | **Hoàn thành** |
| `HDH-19` | Lập tài liệu Test Plan 10 ca kiểm thử chi tiết | Khánh Ly | **Hoàn thành** |
| `HDH-20` | Tạo file cấu hình CSV mẫu hợp lệ đầu tiên | Khánh Ly | **Hoàn thành** |
| `HDH-21` | Lập checklist tiêu chí chấm điểm bám sát đề cương | Khánh Ly | **Hoàn thành** |
| `HDH-22` | Thiết kế kiến trúc trừu tượng `IIPCMechanism` | Hoàng Nam (PM) | **Hoàn thành** |
| `HDH-23` | Giám sát tiến độ Git/Jira và review quy trình | Hoàng Nam (PM) | **Hoàn thành** |
| `HDH-24` | Hiện thực và kiểm thử luồng lõi Shared Memory | Hoàng Nam (PM) | **Hoàn thành** |
| `HDH-27` | Hiện thực lớp lưu trữ MessageQueueCore | Lương Sơn | **Hoàn thành** |
| `HDH-28` | Cài đặt 2 chế độ Blocking và Non-blocking | Lương Sơn | **Hoàn thành** |
| `HDH-29` | Kiểm thử Console kiểm tra trạng thái đầy/rỗng | Lương Sơn | **Hoàn thành** |
| `HDH-30` | Lập trình module CSVParser đọc và kiểm tra kịch bản | Hải Đăng | **Hoàn thành** |
| `HDH-31` | Xử lý ngoại lệ file CSV rỗng, thiếu cột, sai kiểu | Hải Đăng | **Hoàn thành** |
| `HDH-32` | Dựng layout giao diện chính PyQt6 theo wireframe | Hải Đăng | **Hoàn thành** |
| `HDH-33` | Xây dựng bảng tính tay Oracle cho 3 test case mẫu | Khánh Ly | **Hoàn thành** |
| `HDH-34` | Chuẩn bị bộ dữ liệu test biên (Empty, Invalid, Normal) | Khánh Ly | **Hoàn thành** |

---

## 7. HƯỚNG DẪN CÀI ĐẶT VÀ CHẠY ỨNG DỤNG

### 7.1. Cài đặt môi trường
Yêu cầu: **Python 3.10+** đã được cài đặt trên hệ thống Windows/Linux.
```bash
# 1. Cài đặt các thư viện phụ thuộc
pip install -r requirements.txt
```

### 7.2. Chạy ứng dụng giao diện chính (Desktop GUI)
```bash
python -m src.main
# hoặc
python src/main.py
```

### 7.3. Chạy toàn bộ bộ kiểm thử tự động (Unit Test Suite)
```bash
python -m unittest discover -s tests -v
```

### 7.4. Chạy kiểm thử nhanh trên Console (Message Queue Core)
```bash
python test_ipc.py
```
