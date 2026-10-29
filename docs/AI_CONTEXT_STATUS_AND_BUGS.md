# 🤖 TÀI LIỆU BÀN GIAO NGỮ CẢNH & DANH SÁCH LỖI CHO AI (AI HANDOVER & BUG TRACKER)

> **Dự án:** Mô phỏng & Hiện thực Trao đổi Dữ liệu Liên tiến trình (IPC - Inter-Process Communication)  
> **Môn học:** Hệ điều hành (Mã nhóm: `OS_IPC_09`)  
> **Repository:** https://github.com/hnamhocit/he-dieu-hanh-2026  
> **Đối tượng đọc:** Dành riêng cho các Agent AI (Claude, Gemini, ChatGPT...) tiếp nhận dự án để nắm bắt chính xác kiến trúc, những gì ĐÃ ỔN ĐỊNH (không được phá vỡ), những gì CẦN LÀM TIẾP THEO, và DANH SÁCH CÁC LOẠI BUG HỌC THUẬT cần sửa ngay.

---

## 📌 MỤC LỤC
1. [Bối cảnh học thuật & Tiêu chuẩn của Giảng viên](#1-bối-cảnh-học-thuật--tiêu-chuẩn-của-giảng-viên)
2. [Những gì ĐÃ HOÀN THÀNH & ĐÃ ỔN ĐỊNH (DO NOT BREAK)](#2-những-gì-đã-hoàn-thành--đã-ổn-định-do-not-break)
3. [Danh sách các Bug & Lỗ hổng học thuật (BUGLIST & ACADEMIC RED FLAGS)](#3-danh-sách-các-bug--lỗ-hổng-học-thuật-buglist--academic-red-flags)
4. [Lộ trình công việc CẦN LÀM TIẾP THEO (NEXT STEPS)](#4-lộ-trình-công-việc-cần-làm-tiếp-theo-next-steps)
5. [Quy tắc vàng bắt buộc cho AI khi lập trình (AI CONSTRAINTS)](#5-quy-tắc-vàng-bắt-buộc-cho-ai-khi-lập-trình-ai-constraints)

---

## 1. BỐI CẢNH HỌC THUẬT & TIÊU CHUẨN CỦA GIẢNG VIÊN

* **Đặc thù môn học:** Giảng viên chấm điểm tính **học thuật cực kỳ cao**, soi kỹ từng dòng mã nguồn, logic giải thuật Hệ điều hành, tính toàn vẹn toán học và tính chân thực của các ca kiểm thử.
* **Nguyên tắc sống còn:** **"ĐÃ LÀM GÌ PHẢI XONG CÁI ĐÓ"**. Dù đang ở Checkpoint 01 (chưa hoàn thành toàn bộ đồ án), các module đã công bố trong báo cáo phải hoàn thiện 100%, không chấp nhận code đối phó, không fake kết quả test, không hardcode để qua mặt bài kiểm thử.
* **Yêu cầu kỹ thuật cốt lõi:**
  1. Phân tầng độc lập (**Decoupled Core**): Tầng thuật toán lõi (`src/core/`) hoàn toàn không phụ thuộc GUI.
  2. Không làm treo giao diện (**Non-blocking GUI Guarantee**): Logic `produce()` / `consume()` hỗ trợ `timeout=0.0` trả về trạng thái `BLOCKED` tức thì trong $O(1)$, không busy-waiting trên Main Thread của PyQt6.
  3. Bất biến toán học (**System Invariants**): Luôn bảo toàn $Empty + Full = Capacity$ và loại trừ tương hỗ (Mutual Exclusion).

---

## 2. NHỮNG GÌ ĐÃ HOÀN THÀNH & ĐÃ ỔN ĐỊNH (DO NOT BREAK)

AI khi tiếp nhận dự án **TUYỆT ĐỐI KHÔNG ĐẬP ĐI XÂY LẠI** hoặc làm biến đổi chữ ký các thành phần đã ổn định sau đây:

### 2.1. Tầng Giao diện trừu tượng (`src/core/ipc_interface.py`)
- Lớp trừu tượng `IIPCMechanism`: Định nghĩa khung chuẩn gồm `capacity`, `produce()`, `consume()`, và `get_state()`.
- Lớp `IPCResult`: Chuẩn hóa kết quả trả về (`status`, `data`, `success`, `detail`), hỗ trợ so sánh chuỗi trực tiếp (`result == "BLOCKED"`), unpack tuple (`status, item = result`) và boolean evaluation.
- Enum `IPCStatus`: `SUCCESS`, `BLOCKED`, `TIMEOUT`, `ERROR`.

### 2.2. Lõi Bộ nhớ chia sẻ (`src/core/shared_memory.py`)
- **Mô hình:** Bounded Buffer (Mảng vòng tuần hoàn Circular Buffer).
- **Đồng bộ hóa:** Mutex nhị phân (`threading.Lock`) bảo vệ Critical Section + 2 Counting Semaphores (`empty` khởi tạo = $N$, `full` khởi tạo = $0$).
- **Cơ chế Rollback Semaphore:** Tự động hoàn trả Semaphore nếu không lấy được Mutex, chống rò rỉ tài nguyên (Semaphore Leak).
- **Hàm chẩn đoán bất biến:** `verify_invariants()` kiểm chứng $Empty + Full = Capacity$, con trỏ $in\_ptr, out\_ptr \in [0, N-1]$.
- **Snapshot GUI:** `get_state()` trả về snapshot thread-safe chứa `buffer`, `in_ptr`, `out_ptr`, `mutex`, `empty`, `full`, `blocked_processes`.

### 2.3. Lõi Hàng đợi thông điệp (`src/core/message_queue.py`)
- **Mô hình:** Monitor Pattern (Mesa-style) sử dụng `threading.Lock` cùng hai `threading.Condition` (`not_full`, `not_empty`).
- **Xử lý thức giả & Chen ngang:** Mọi điều kiện chờ đều nằm trong vòng lặp `while len(self._queue) >= self._capacity` và `while len(self._queue) == 0`.
- **Cấu trúc gói tin:** `MessagePacket` chuẩn gồm `id`, `sender`, `receiver`, `message`, `delay_ms`, `priority`, `simulate_error`, `timestamp`, `sequence`.
- **Luật phân xử hòa (Tie-breaking - HDH-88):** Khi bật `is_priority=True`, gói tin có `priority` cao hơn sẽ lên đầu; nếu hai gói tin có cùng `priority`, gói tin vào trước (có `sequence` nhỏ hơn) sẽ được lấy ra trước (FIFO).

### 2.4. Giao diện Desktop GUI (`src/gui/`)
- `src/gui/main_window.py`: Bố cục chuẩn theo Wireframe (Khối CSV Input, Cấu hình tham số, Visualization, Trace Table).
- `src/gui/simulation_controller.py`: Bộ điều khiển mô phỏng từng frame bằng `QTimer` và `deque` sự kiện, nhận kết quả `BLOCKED` chuyển bước mà không làm đứng GUI.
- `src/gui/widgets.py`: `BufferSlots` vẽ trạng thái ô nhớ động (`EMPTY`, `LOCKED`, `WRITTEN`, `READING`) và `BufferChart` vẽ đồ thị mức sử dụng buffer theo thời gian thực.
- `src/gui/styles.py`: Giao diện chuyên nghiệp, màu sắc chuẩn UX.

### 2.5. Tiện ích dữ liệu & Bộ kiểm thử đã có
- `src/utils/csv_reader.py`: Bộ đọc kiểm tra cấu trúc CSV an toàn.
- `tests/`: Đang có 89 tests tự động passed (bao gồm unit test cho parser, reader, core shm, core mq, simulation controller, offscreen GUI).

---

## 3. DANH SÁCH CÁC BUG & LỖ HỔNG HỌC THUẬT (BUGLIST & ACADEMIC RED FLAGS)

Dưới đây là các hạt sạn và lỗi nghiêm trọng cần AI sửa dứt điểm theo thứ tự ưu tiên:

---

### 🟢 BUG-01 (Mức độ: NGHIÊM TRỌNG - FAKE TEST / SILENT FAILURE) - [ĐÃ FIX XONG]
* **Vị trí file:** `src/core/test_stress_fault.py` -> Đã di chuyển sang `tests/test_stress_fault.py`.
* **Trạng thái:** ✅ **ĐÃ KHẮC PHỤC TRIỆT ĐỂ**
  - Xóa bỏ hoàn toàn file ở `src/core/` để không làm méo mó độ phủ mã nguồn `pytest-cov`.
  - Viết lại các hàm assertion kiểm tra nghiêm ngặt `assert os.path.exists(LOG_FILE_PATH)`, kiểm tra thứ tự timestamp đơn điệu tăng dần và độ toàn vẹn của file log không có dòng nào bị hỏng (corrupted).
  - Tích hợp ghi vết `log_trace` trong `MessageQueue` (BUG-03) và sửa lỗi race condition lấy timestamp bên trong lock `_trace_file_lock`, ghi nhận thành công >1500 dòng log thực tế dưới áp lực 500 gói tin đồng thời.

---

### 🟢 BUG-02 (Mức độ: NGHIÊM TRỌNG - HARDCODED BYPASS TRONG TEST BIÊN) - [ĐÃ FIX XONG]
* **Vị trí file:** `tests/test_boundary.py` và `docs/oracle_tinh_tay.md` (Kịch bản 7).
* **Trạng thái:** ✅ **ĐÃ KHẮC PHỤC TRIỆT ĐỂ**
  - Đã bổ sung tầng Guard bảo vệ biên cực đại trong cả `SharedMemory.produce()` và `MessageQueue.produce()`: Khi `len(message) > 100`, hệ thống lập tức từ chối và trả về `IPCResult(status=IPCStatus.ERROR.value, success=False, detail="Payload vượt quá giới hạn 100 ký tự...")`.
  - Xóa bỏ hoàn toàn đoạn mã lách luật `if len(g101.message) > 100: chan_ok = True` trong `tests/test_boundary.py`.
  - Viết lại bộ test case chuẩn `TestBoundaryCases` với đầy đủ `assert` cho từng kịch bản (Buffer size 1, Empty payload, Boundary 100 chars, Guard reject 101 chars, Tie-breaking FIFO). Khởi tạo lại file log báo cáo tránh ghi đè lặp header.

---

### 🟢 BUG-03 (Mức độ: CAO - MESSAGE QUEUE THIẾU LOG_TRACE VÀ TIÊM LỖI) - [ĐÃ FIX XONG]
* **Vị trí file:** `src/core/message_queue.py`
* **Trạng thái:** ✅ **ĐÃ KHẮC PHỤC TRIỆT ĐỂ**
  - Import và gọi `log_trace("ENQUEUE", ...)` khi gửi tin, `log_trace("DEQUEUE", ...)` khi nhận tin, `log_trace("WAIT_NOT_FULL", ...)` khi Producer bị nghẽn, và `log_trace("WAIT_NOT_EMPTY", ...)` khi Consumer bị nghẽn.
  - Xử lý mô phỏng độ trễ `DELAY` và sự kiện `CHECKSUM` qua `log_trace("FAULT_CHECKSUM", ...)`.

---

### 🟢 BUG-04 (Mức độ: TRUNG BÌNH - CSVPARSER TỪ CHỐI CỘT SIMULATE_ERROR) - [ĐÃ FIX XONG]
* **Vị trí file:** `src/utils/csv_parser.py`
* **Trạng thái:** ✅ **ĐÃ KHẮC PHỤC TRIỆT ĐỂ**
  - Bổ sung `"simulate_error"` vào `OPTIONAL_COLUMNS`.
  - Bổ sung trường `simulate_error: str = "NONE"` vào `dataclass SimulationStep`.
  - Cập nhật `_parse_row()` đọc và chuẩn hóa chữ hoa cho `simulate_error`.
  - Bổ sung unit test `test_simulate_error_column` trong `tests/test_csv_parser.py`.

---

### 🟢 BUG-05 (Mức độ: TRUNG BÌNH - GUI KHÔNG CÓ TÙY CHỌN PRIORITY QUEUE) - [ĐÃ FIX XONG]
* **Vị trí file:** `src/gui/main_window.py` & `src/gui/simulation_controller.py`
* **Trạng thái:** ✅ **ĐÃ KHẮC PHỤC TRIỆT ĐỂ**
  - Thêm `QCheckBox("Chế độ hàng đợi ưu tiên (Priority Queue)")` vào nhóm cấu hình `main_window.py`. Checkbox tự động enable khi chọn Message Queue và disable khi chọn Shared Memory.
  - Bổ sung `"is_priority"` vào dictionary trả về của `MainWindow.configuration()`.
  - Trong `SimulationController.start()`, truyền `is_priority=configuration.get("is_priority", False)` khi khởi tạo `MessageQueue`.
  - Cập nhật test GUI và simulation controller kiểm chứng kích hoạt Priority mode.

---

### 🟢 BUG-06 (Mức độ: THẤP - FILE RÁC TỒN ĐỌNG Ở ROOT) - [ĐÃ FIX XONG]
* **Vị trí file:** Thư mục gốc (`he-dieu-hanh-2026/`)
* **Trạng thái:** ✅ **ĐÃ KHẮC PHỤC TRIỆT ĐỂ**
  - Di chuyển `test_ipc.py` thành `tests/test_ipc_console.py` với import chuẩn từ `src.core.message_queue`.
  - Xóa bỏ hoàn toàn file thừa `ipc_manager.py` và `test_ipc.py` ở thư mục gốc. Thư mục gốc giờ đây hoàn toàn sạch sẽ, chỉ chứa file cấu hình và tài liệu chính thức.

---

## 4. LỘ TRÌNH CÔNG VIỆC CẦN LÀM TIẾP THEO (NEXT STEPS)

### Giai đoạn 1: Khắc phục dứt điểm để nộp Checkpoint 01 (Hạn: EOD 30/10/2026)
1. **Sửa 6 Bugs ở Mục 3:** Đảm bảo không còn bất kỳ chi tiết đối phó hay lừa dối nào trong code.
2. **Chạy kiểm thử toàn diện:**
   ```bash
   venv/bin/pytest -v --cov=src tests/
   ```
   Đạt 100% test pass với assertion thật, kiểm tra được file `trace_execution.csv` thực tế.
3. **Hoàn thiện Báo cáo Checkpoint 01 (PDF):**
   * Báo cáo phải có đủ 3 yêu cầu trong đề bài:
     1. Tiến độ thực tế nhóm đã đạt được & Kế hoạch chi tiết các tuần tiếp theo.
     2. Bảng phân công trách nhiệm của từng thành viên cho **toàn bộ đề tài**.
     3. Link GitHub công khai của nhóm: `https://github.com/hnamhocit/he-dieu-hanh-2026`.
   * Trả lời đủ các luận điểm học thuật trong **6 câu hỏi bắt buộc** (Q1 -> Q6 trong `checklist_cham_diem.md`).
   * Xuất file báo cáo chuẩn `BAO_CAO_CHECKPOINT_01_OS_IPC_09.pdf`.
4. **Đóng gói mã nguồn (zip):**
   * Tạo file zip sạch chứa toàn bộ source code cho checkpoint này (loại trừ `venv/`, `__pycache__/`, `.pytest_cache/`, `data/output/*.csv`).

### Giai đoạn 2: Phát triển Sprint 2 (Sau Checkpoint 01)
1. **Cơ chế Pipe:** Hiện thực lớp `NamedPipe` hoặc `AnonymousPipe` kế thừa `IIPCMechanism` và kích hoạt lựa chọn Pipe trên GUI.
2. **Giao diện Tiêm lỗi (Fault Injection Panel):** Thêm nút bấm trên GUI để chủ động gây lỗi `Corrupt Checksum`, `Inject Random Delay`, `Simulate Process Crash`.
3. **Cơ chế Chống đói (Aging Mechanism):** Bổ sung thuật toán tăng dần độ ưu tiên theo thời gian chờ trong `MessageQueue` để tránh hiện tượng Starvation cho tin nhắn ưu tiên thấp.
4. **Benchmark & Biểu đồ hiệu năng:** Viết script benchmark tự động đo Throughput và Latency khi tăng tải số lượng Producer/Consumer và kích thước Buffer, xuất biểu đồ trực quan vào báo cáo cuối kỳ.

---

## 5. QUY TẮC VÀNG BẮT BUỘC CHO AI KHI LẬP TRÌNH (AI CONSTRAINTS)

Mọi Agent AI khi đọc tài liệu này và thực hiện code trong repository phải tuân thủ nghiêm ngặt:

1. 🚫 **KHÔNG TẠO FILE Ở ROOT:** Mọi file mã nguồn mới phải nằm trong `src/` hoặc `tests/`, tài liệu nằm trong `docs/`.
2. 🚫 **KHÔNG TỰ BỊA METHOD:** Tầng Core IPC chỉ được phép giao tiếp qua các hàm chuẩn: `produce()`, `consume()`, `get_state()`, `reset()`.
3. 🚫 **KHÔNG BLOCK UI THREAD:** Tuyệt đối không dùng `time.sleep()` kéo dài hay vòng lặp bận `while True` bên trong Main Thread của PyQt6. Luôn tôn trọng cờ `timeout=0.0`.
4. 🚫 **KHÔNG VIẾT TEST FAKE / ASSERT TRỐNG:** Tuyệt đối không viết test theo kiểu `if điều_kiện: pass` hoặc chỉ in ra console mà không `assert`. Mọi test case phải kiểm chứng logic của module thật sự.
5. 🛡️ **BẢO TỒN COMMENT & DOCSTRING HỌC THUẬT:** Giữ gìn nguyên vẹn các công thức toán, pseudocode và trích dẫn lý thuyết HĐH trong các docstring hiện có.
