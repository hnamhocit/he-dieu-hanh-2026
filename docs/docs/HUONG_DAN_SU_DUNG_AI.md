# CẨM NANG HƯỚNG DẪN SỬ DỤNG AI TRONG DỰ ÁN HỆ ĐIỀU HÀNH
**Áp dụng cho toàn bộ thành viên nhóm: he-dieu-hanh-2026**

---

## 1. TẠI SAO PHẢI CÓ CẨM NANG NÀY? (BÀI HỌC TỪ SPRINT 1)

Trong Sprint 1 vừa qua, các thành viên đều sử dụng AI (ChatGPT, Claude, Gemini...) để hỗ trợ làm task, nhưng do **chưa biết cách nạp ngữ cảnh (Context Injection)** và **hỏi cụt lủn**, nhóm đã gặp phải những hậu quả rất nặng nề:
1. **Lương Sơn bị AI "lừa" đẻ file rác:** Do mỗi task mới lại mở một chat mới và hỏi câu hỏi rời rạc, AI không biết dự án đã có file gì nên tự động sinh ra các file độc lập ở root (`ipc_manager.py`, `ipc_manager2.py`, `ipc_manager3.py`).
2. **Code của AI làm gãy kiến trúc chung:** Sơn không nạp file Interface của PM cho AI đọc, dẫn đến AI tự bịa ra hàm `enqueue()` / `dequeue()`, không có hàm `get_state()`, khiến giao diện GUI không thể kết nối được.
3. **Hải Đăng bị AI viết thừa code:** Do không nhắc AI rằng dự án đã có `csv_parser.py`, AI đã viết hẳn một file mới `csv_reader.py` gây phân mảnh và trùng lặp code.
4. **Khánh Ly bị AI làm vỡ Unit Test:** Khi bảo AI thêm dòng vào CSV, không cung cấp file test cho AI kiểm tra, khiến số dòng tăng từ 7 lên 10 và làm đỏ toàn bộ test tự động của cả nhóm.

> [!IMPORTANT]
> **NGUYÊN TẮC VÀNG:**  
> **AI chỉ thông minh khi bạn cung cấp đủ ngữ cảnh (Context).** Nếu không nạp đúng file và kiến trúc, AI sẽ trở thành kẻ phá hoại làm rác repo và làm gãy hệ thống.

---

## 2. KỸ THUẬT "CONTEXT INJECTION" (CÁCH NHỒI NGỮ CẢNH CHUẨN)

Mỗi khi mở một phiên chat với AI để làm một task Jira, **bắt buộc phải copy nội dung các file nền tảng sau ném vào đầu prompt**:

### 2.1. Khi làm việc với Tầng Thuật toán lõi (Core IPC)
* **File bắt buộc phải nạp vào Context:**
  1. `src/core/ipc_interface.py`: Chứa class trừu tượng `IIPCMechanism` và `IPCResult`.
  2. `src/core/shared_memory.py`: File mẫu chuẩn để AI học theo phong cách đồng bộ hóa và cách viết `get_state()`.
* **Câu lệnh ép AI tuân thủ:**
  > *"Class mới bắt buộc phải kế thừa `IIPCMechanism` từ `src/core/ipc_interface.py`. Bắt buộc phải có đủ 3 phương thức: `produce()`, `consume()`, và `get_state()`. Phải hỗ trợ tham số `timeout=0.0` (non-blocking) trả về `IPCResult(status='BLOCKED')`."*

### 2.2. Khi làm việc với Tầng Giao diện (PyQt6 GUI)
* **File bắt buộc phải nạp vào Context:**
  1. `src/gui/main_window.py`: Cấu trúc cửa sổ chính hiện tại.
  2. `src/core/ipc_interface.py`: Để AI biết các hàm và tín hiệu cần gọi từ Backend.
* **Câu lệnh ép AI tuân thủ:**
  > *"Tuyệt đối không chạy logic IPC hoặc đọc file nặng trên UI Thread. Bắt buộc phải dùng `QThreadPool` hoặc `QRunnable` / `QThread` để giao diện luôn đạt 60 FPS, không được freeze khi bộ đệm bị BLOCKED."*

### 2.3. Khi làm việc với Dữ liệu CSV & Tiện ích
* **File bắt buộc phải nạp vào Context:**
  1. `data/input/sample_config.csv`: File mẫu chuẩn về schema dữ liệu.
  2. `tests/test_csv_parser.py`: File unit test hiện tại để AI không viết code làm gãy test.

---

## 3. QUY TẮC "4 KHÔNG" KHI SỬ DỤNG AI

1. ❌ **KHÔNG ĐƯỢC để AI tạo file ở thư mục gốc (root):**  
   Mọi file mới phải được AI chỉ định rõ đường dẫn: `src/core/...`, `src/gui/...`, `src/utils/...`, hoặc `tests/...`.
2. ❌ **KHÔNG ĐƯỢC để AI tự chế tên hàm:**  
   Không dùng `push`, `pop`, `enqueue`, `dequeue`, `send_msg`... Mọi cơ chế IPC của dự án **CHỈ ĐƯỢC PHÉP** dùng `produce()`, `consume()`, và `get_state()`.
3. ❌ **KHÔNG ĐƯỢC để AI clone ra file mới (`file_v2.py`, `file_new.py`):**  
   Luôn yêu cầu: *"Hãy sửa trực tiếp trên file hiện tại (in-place modification), không tạo file mới"*.
4. ❌ **KHÔNG ĐƯỢC commit code nếu chưa chạy lệnh kiểm thử:**  
   Trước khi `git add` và `git commit`, bắt buộc chạy:
   ```bash
   python -m unittest discover -s tests -v
   ```
   Nếu có bất kỳ chữ `FAIL` hoặc `ERROR` nào, ném lỗi đó lại cho AI sửa ngay lập tức!

---

## 4. BỘ TEMPLATE PROMPT CHUẨN THEO TỪNG VAI TRÒ (ROLE-BASED PROMPTS)

### Template 1: Dành cho Dev Thuật toán (Core IPC)
```markdown
Tôi đang phát triển module IPC cho môn Hệ điều hành trong dự án Python 3.10+.
Dự án của tôi tuân thủ nghiêm ngặt kiến trúc phân tầng. 

Dưới đây là file Interface chuẩn của dự án:
```python
[DÁN NỘI DUNG src/core/ipc_interface.py VÀO ĐÂY]
```

Nhiệm vụ của bạn:
Hãy hiện thực cơ chế Message Queue (Hàng đợi tin nhắn) bằng ngôn ngữ Python, lưu tại đường dẫn `src/core/message_queue.py`.

Yêu cầu kỹ thuật bắt buộc:
1. Kế thừa trực tiếp từ class `IIPCMechanism`.
2. Đồng bộ hóa bằng Monitor Pattern: dùng `threading.Lock()` và 2 Condition Variable (`not_full`, `not_empty`).
3. Hàm `produce(item, process_id, timeout)`:
   - Nếu `timeout=0.0` (non-blocking) và hàng đợi đầy, trả về ngay `IPCResult(status="BLOCKED")`.
   - Nếu `timeout=None`, chờ vô hạn trên Condition Variable cho đến khi có chỗ trống.
4. Hàm `consume(process_id, timeout)`:
   - Nếu `timeout=0.0` và hàng đợi rỗng, trả về ngay `IPCResult(status="BLOCKED")`.
   - Nếu `timeout=None`, chờ vô hạn trên Condition Variable cho đến khi có tin nhắn mới.
5. Hàm `get_state()` trả về dict snapshot chứa: `buffer`, `in_ptr`, `out_ptr`, `mutex`, `empty`, `full`, `blocked_processes`.
6. Viết code sạch, có docstring tiếng Việt, type hints đầy đủ. Không viết script chạy thử ở thư mục gốc.
```

---

### Template 2: Dành cho Dev Giao diện (PyQt6 GUI)
```markdown
Tôi đang xây dựng giao diện Desktop bằng PyQt6 cho bài tập lớn Hệ điều hành mô phỏng IPC.
Dưới đây là file giao diện hiện tại của tôi:
```python
[DÁN NỘI DUNG src/gui/main_window.py VÀO ĐÂY]
```

Nhiệm vụ:
Tôi cần bổ sung tính năng [MÔ TẢ TÍNH NĂNG MỚI, ví dụ: kết nối nút bấm Start với Worker Thread chạy thuật toán IPC].

Yêu cầu kỹ thuật bắt buộc:
1. Giữ nguyên toàn bộ cấu trúc và Dark Theme hiện có trong `src/gui/styles.py`.
2. Logic mô phỏng IPC phải chạy trên QRunnable / QThreadPool, giao tiếp với GUI thông qua Qt Signal (tín hiệu).
3. Tuyệt đối không gọi các hàm blocking trực tiếp trên luồng chính để tránh làm đơ ứng dụng.
4. Chỉ cung cấp đoạn code sửa đổi chính xác trên file `src/gui/main_window.py`, không tạo thêm file mới.
```

---

### Template 3: Dành cho QA / Tester / Viết Kịch bản
```markdown
Tôi đang lập Kế hoạch kiểm thử (Test Plan) và Bảng tính tay (Oracle) cho môn Hệ điều hành, đề tài IPC Shared Memory và Message Queue.
Quy ước cấu hình bộ đệm:
- Dung lượng buffer = 4 ô. Ban đầu rỗng.
- Con trỏ in = 0, out = 0.
- Khóa Mutex = 1, Semaphore empty = 4, full = 0.

Nhiệm vụ:
Hãy phân tích và lập bảng tính tay từng bước (Step-by-step Oracle) cho kịch bản [TÊN KỊCH BẢN, ví dụ: Deadlock hoặc Race condition khi 3 Producer cùng tranh chấp].
Yêu cầu bảng gồm các cột:
| Bước | Hành động | Trạng thái Buffer | in/out | Semaphore (mutex, empty, full) | Tiến trình bị Blocked | Giải thích |
Giải thích chi tiết và ngắn gọn, bám sát lý thuyết Semaphore của Tanenbaum/Silberschatz.
```

---

## 5. CÁCH DÙNG AI ĐỂ TỰ LUYỆN VẤN ĐÁP BẢO VỆ VỚI GIẢNG VIÊN (AI DRILL)

Khi chuẩn bị bảo vệ đồ án, hãy dùng prompt dưới đây để AI đóng vai Giảng viên khó tính và "vấn đáp" bạn:

```markdown
Bạn là một Giảng viên khó tính dạy môn Hệ điều hành tại trường Đại học.
Nhóm tôi vừa hoàn thành đồ án mô phỏng IPC bằng Shared Memory và Message Queue viết bằng Python.

Hãy lần lượt đặt cho tôi 5 câu hỏi phỏng vấn hóc búa nhất về:
1. Cơ chế đồng bộ hóa: Sự khác nhau giữa Binary Semaphore (Mutex) và Counting Semaphore.
2. Tại sao lại xảy ra Race Condition nếu không có Mutex bảo vệ `in_ptr` và `out_ptr`?
3. Trạng thái `BLOCKED`: Hệ điều hành làm gì với tiến trình khi Semaphore giảm xuống dưới 0?
4. Monitor & Condition Variable: Khác biệt giữa cơ chế Hoare và Mesa khi gọi `signal()`/`notify()`.
5. Đánh giá hiệu năng và Trade-off: Khi nào nên chọn Shared Memory và khi nào nên chọn Message Queue?

Hãy hỏi tôi từng câu một. Sau khi tôi trả lời, hãy nhận xét xem câu trả lời của tôi đã đủ ý chưa, có bị sai sót học thuật nào không, và chấm điểm trên thang điểm 10.
```

---

### TÓM TẮT DÀNH CHO CẢ NHÓM:
* Sử dụng AI là kỹ năng tốt, nhưng **phải làm chủ được code của AI**.
* Trước khi nhấn `git commit`, tự hỏi:
  1. *Code này đã kế thừa đúng `IIPCMechanism` chưa?*
  2. *Có bị sinh file trùng lặp vô nghĩa không?*
  3. *Lệnh `python -m unittest discover -s tests` có chạy ra màu xanh (OK) không?*
  ➔ Nếu cả 3 câu trả lời là **CÓ**, bạn mới được phép push code lên nhánh tính năng của mình!
