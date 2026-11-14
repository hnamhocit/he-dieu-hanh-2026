# PHẦN 1: TỔNG QUAN VỀ BÀI TẬP LỚN / DỰ ÁN MÔ PHỎNG IPC

> **Mã nhiệm vụ Jira:** `HDH-85`  
> **Tên nhiệm vụ:** Soạn thảo Phần 1 của Khung báo cáo chính: Bối cảnh, thuật ngữ, giả định, I/O, phạm vi  
> **Người thực hiện:** Đỗ Tường Minh (MT) & Review/Hiệu chỉnh: Hoàng Nam (PM)  
> **Đề tài:** Mô phỏng & Hiện thực trao đổi dữ liệu giữa các tiến trình (Inter-Process Communication - IPC) bằng **Shared Memory** và **Message Queue**; có cơ chế Trace và Xử lý lỗi (Fault Injection).

---

## 1.1. BỐI CẢNH (CONTEXT)
Trong các hệ thống máy tính hiện đại, các tiến trình (Processes) thường xuyên cần trao đổi thông tin, chia sẻ dữ liệu và đồng bộ hóa hoạt động để giải quyết các tác vụ tính toán phức tạp. Hệ điều hành (HĐH) cung cấp tầng kiến trúc **Inter-Process Communication (IPC)** nhằm phục vụ nhu cầu này. Hai mô hình truyền thông liên tiến trình kinh điển được giảng dạy và áp dụng rộng rãi nhất là:
1. **Vùng nhớ chia sẻ (Shared Memory):** Các tiến trình cùng ánh xạ và truy cập trực tiếp vào một vùng nhớ đệm chung (Bounded Buffer). Đây là cơ chế có tốc độ truyền tải cao nhất (Zero-copy), nhưng đòi hỏi cơ chế đồng bộ hóa nghiêm ngặt (Mutex, Semaphores) để ngăn chặn hiện tượng tranh chấp bộ nhớ (Race Condition).
2. **Truyền thông điệp (Message Passing / Message Queue):** Dữ liệu được đóng gói thành các thông điệp độc lập và chuyển qua một hàng đợi trung gian (Queue/Mailbox) do hệ điều hành quản lý. Cơ chế này an toàn, tránh can thiệp trực tiếp vào bộ nhớ nhưng tốn chi phí sao chép dữ liệu (Context Switch, Memory Copy).

Việc quan sát trực quan cách thức các tiến trình cạnh tranh khóa, bị chặn (Blocked) khi bộ đệm đầy/rỗng, và hành vi phục hồi khi gặp sự cố trên một HĐH thực tế là cực kỳ khó khăn do tốc độ xử lý phần cứng lên đến hàng triệu thao tác/giây và chạy ẩn dưới nhân (Kernel Mode). Dự án này được xây dựng nhằm **thiết kế, hiện thực và trực quan hóa mô phỏng cơ chế trao đổi dữ liệu IPC** chạy trên User Mode với giao diện Desktop GUI tương tác, ghi vết vi sự kiện (Trace Logging) và chèn lỗi chủ động (Fault Injection) để kiểm chứng độ bền vững của hệ thống.

---

## 1.2. THUẬT NGỮ (TERMINOLOGY)
* **Tiến trình gửi / Sản xuất (Producer Process):** Thực thể tạo ra dữ liệu/thông điệp và đẩy vào bộ đệm hoặc hàng đợi IPC.
* **Tiến trình nhận / Tiêu thụ (Consumer Process):** Thực thể trích xuất dữ liệu ra khỏi bộ đệm hoặc hàng đợi IPC để xử lý.
* **Bộ đệm giới hạn (Bounded Buffer / Circular Buffer):** Mảng nhớ vòng tuần hoàn có kích thước cố định $N = \text{capacity}$, sử dụng các con trỏ `in_ptr` và `out_ptr` tịnh tiến tuần hoàn theo modulo $N$.
* **Đoạn găng (Critical Section):** Vùng mã nguồn truy cập vào tài nguyên dùng chung (mảng đệm, con trỏ mảng vòng, số lượng phần tử). Tại một thời điểm chỉ cho phép duy nhất một tiến trình thực thi trong đoạn găng.
* **Khóa nhị phân (Mutex / Binary Semaphore):** Cơ chế đồng bộ đảm bảo tính loại trừ tương hỗ (Mutual Exclusion). Mutex nhận giá trị $1$ (Rảnh) hoặc $0$ (Bận).
* **Semaphore đếm (Counting Semaphore):** Biến đồng bộ nguyên dương đếm số tài nguyên khả dụng:
  * `empty`: Đếm số lượng ô nhớ trống khả dụng (Khởi tạo = $N$). Khi $\text{empty} = 0$, Producer ghi dữ liệu sẽ rơi vào trạng thái `BLOCKED` (Buffer Full / Overflow).
  * `full`: Đếm số lượng ô nhớ chứa dữ liệu khả dụng (Khởi tạo = $0$). Khi $\text{full} = 0$, Consumer đọc dữ liệu sẽ rơi vào trạng thái `BLOCKED` (Buffer Empty / Underflow).
* **Hàng đợi thông điệp (Message Queue):** Cấu trúc lưu trữ các gói tin (`MessagePacket`) hỗ trợ hai chế độ lấy tin: FIFO (Vào trước - Ra trước) hoặc Priority Queue (Theo mức độ ưu tiên giảm dần).
* **Trạng thái nghẽn (Blocked State):** Trạng thái một tiến trình phải dừng lại chờ tài nguyên khả dụng (ô trống hoặc dữ liệu) hoặc chờ giải phóng khóa.
* **Ghi vết vi sự kiện (Trace Logging):** Cơ chế ghi nhận mọi hành vi của hệ thống theo mốc thời gian nano giây (`LOCK_ACQUIRE`, `WRITE_SLOT`, `READ_SLOT`, `SIGNAL_FULL`,...).
* **Bộ chèn lỗi (Fault Injector):** Module chủ động gây lỗi giả lập (Delay, sai lệch Checksum, rớt gói) để kiểm chứng khả năng xử lý ngoại lệ của hệ thống.

---

## 1.3. GIẢ ĐỊNH HỆ THỐNG (SYSTEM ASSUMPTIONS)
1. **Môi trường thực thi:** Ứng dụng chạy trên tầng người dùng (User Mode), viết bằng Python 3.10+, giao diện đồ họa Desktop PyQt6.
2. **Tính độc lập giữa Core và GUI (Decoupled Architecture):** Tầng thuật toán cốt lõi (`SharedMemory`, `MessageQueue`) vận hành hoàn toàn độc lập với GUI. Giao diện người dùng lấy dữ liệu qua bản chụp snapshot `get_state()` và cơ chế `events`.
3. **Mô hình đồng bộ an toàn luồng (Thread-safety):** Các tiến trình Producer và Consumer được mô phỏng dưới dạng các luồng (`threading.Thread`) hoặc chạy theo kịch bản từng bước (Step-by-step Ticker).
4. **Không làm đông cứng giao diện (Non-blocking GUI Guarantee):** Trong chế độ Step-by-step mô phỏng trực quan trên GUI, các thao tác `produce` và `consume` sử dụng cờ `timeout=0.0` (Non-blocking). Nếu bộ đệm đầy/rỗng, hàm trả về ngay trạng thái `BLOCKED` mà không dùng vòng lặp bận (`busy-waiting`) hay làm treo Main Thread của PyQt6.
5. **Kịch bản kiểm thử tất định (Deterministic Test Scenarios):** Toàn bộ chuỗi thao tác được nạp từ file cấu hình chuẩn CSV với các trường thời gian, độ ưu tiên và lỗi giả lập định sẵn.

---

## 1.4. ĐẦU VÀO VÀ ĐẦU RA (INPUT / OUTPUT)

### 1.4.1. Dữ liệu đầu vào (Input)
Dữ liệu đầu vào được tiếp nhận từ các file định dạng chuẩn CSV:
* **File kịch bản gói tin / thao tác (`sample_messages.csv`, `test_slots.csv`):**
  * `id`: Định danh duy nhất của bước / gói tin (số nguyên dương).
  * `action`: Thao tác IPC (`PRODUCE`, `CONSUME`, `SEND`, `RECEIVE`).
  * `sender`: Định danh tiến trình gửi (ví dụ: `Producer_1`, `Proc_A`).
  * `receiver`: Định danh tiến trình nhận (ví dụ: `Consumer_1`, `Buffer`).
  * `message`: Nội dung thông điệp dạng chuỗi văn bản (tối đa 100 ký tự).
  * `delay_ms`: Độ trễ giả lập trước khi thực hiện bước (mili giây).
  * `priority`: Mức độ ưu tiên của gói tin (số nguyên từ 0 đến 5, số càng lớn ưu tiên càng cao).
  * `simulate_error`: Loại lỗi cố tình chèn (`NONE`, `DELAY`, `CHECKSUM`).
* **File cấu hình tham số hệ thống (`sample_config.csv`):**
  * `mechanism`: Cơ chế IPC lựa chọn (`SHARED_MEMORY` hoặc `MESSAGE_QUEUE`).
  * `buffer_capacity`: Sức chứa tối đa của bộ đệm / hàng đợi ($N$).
  * `is_priority`: Chế độ ưu tiên (`True` / `False`).

### 1.4.2. Dữ liệu đầu ra (Output)
* **Giao diện trực quan hóa Desktop GUI:**
  * Khối hiển thị ô nhớ động (`MemorySlotsWidget`): Trực quan hóa trạng thái từng ô của Circular Buffer (`EMPTY`, `OCCUPIED`, `LOCKED`, `READING`, `WRITING`) kèm vị trí con trỏ `in_ptr` và `out_ptr`.
  * Khối trạng thái biến đồng bộ: Giá trị thời gian thực của Mutex (`0` hoặc `1`), Semaphore `empty`, Semaphore `full`, danh sách tiến trình đang bị `BLOCKED`.
  * Bảng nhật ký sự kiện thời gian thực (Trace Table): Cột mốc thời gian, ID bước, trạng thái (`SUCCESS`, `BLOCKED`, `TIMEOUT`, `ERROR`), độ trễ và chi tiết.
* **File nhật ký ghi vết tự động (`data/output/trace_execution.csv`):**
  * Lưu trữ chi tiết toàn bộ vi sự kiện với độ chính xác nano giây (`timestamp_ns,event_name,details`).
* **Báo cáo đối soát tính đúng đắn (Oracle Verification Report):**
  * Tự động kiểm chứng toàn vẹn dữ liệu: không mất tin, không đọc trùng, bảo toàn thứ tự FIFO/Priority, và bảo đảm các bất biến toán học của hệ thống.

---

## 1.5. PHẠM VI MÔ PHỎNG (SCOPE)
* **Nằm trong phạm vi (In-Scope):**
  * Cài đặt hoàn chỉnh thuật toán **Shared Memory** với Bounded Buffer mảng vòng, đồng bộ hóa bằng `Lock` (Mutex) và `Semaphore` (`empty`, `full`).
  * Cài đặt hoàn chỉnh thuật toán **Message Queue** với Monitor Pattern (`Condition Variables`: `not_full`, `not_empty`), hỗ trợ cả FIFO và Priority Queue.
  * Hỗ trợ 3 chế độ thực thi: Non-blocking (`timeout=0.0`), Blocking có giới hạn (`timeout > 0`), và Blocking vô hạn (`timeout=None`).
  * Cơ chế Rollback Semaphore khi tranh chấp Mutex chống rò rỉ tài nguyên.
  * Bộ Trace Logger ghi vết vi sự kiện ở tầng nano giây và Fault Injector chèn lỗi kiểm thử.
  * Desktop GUI PyQt6 mô phỏng animation trực quan từng frame, hỗ trợ Play, Pause, Step-by-step, Reset.
  * Bộ kiểm thử tự động (Unit Tests, Stress Tests, Boundary Tests) đạt 100% tỷ lệ vượt qua.
* **Nằm ngoài phạm vi (Out-of-Scope):**
  * Không sử dụng POSIX IPC thật của hệ điều hành Linux (`shmget`, `mq_open`) do mục tiêu đồ án là ứng dụng chạy đa nền tảng (Cross-platform trên Windows/macOS/Linux) và phục vụ mục đích sư phạm mô phỏng chi tiết nội hàm giải thuật đồng bộ.
  * Không phân tán dữ liệu qua mạng (Network Socket IPC); chỉ tập trung vào truyền thông nội tại giữa các tiến trình/luồng trên một máy tính đơn.

---

## 1.6. SO SÁNH GIỮA MÔ PHỎNG DỰ ÁN VÀ CƠ CHẾ IPC THỰC TẾ TRONG HĐH

| Đặc điểm so sánh | Mô hình mô phỏng (Dự án này) | Cơ chế IPC thực tế (Linux POSIX / Windows IPC) |
| :--- | :--- | :--- |
| **Không gian thực thi** | Hoàn toàn trên **User Mode**, tách lớp kiến trúc hướng đối tượng sạch sẽ. | Chạy qua các **System Calls** chuyển ngữ cảnh vào **Kernel Mode** (Ring 0). |
| **Cơ chế Shared Memory** | Circular Buffer cấp phát trong heap của ứng dụng, được bảo vệ bằng `threading.Lock` và `threading.Semaphore`. | Sử dụng `shmget` / `shmat` hoặc `mmap` tạo các trang nhớ vật lý dùng chung giữa các PCB độc lập; đồng bộ bằng POSIX Semaphores (`sem_open`). |
| **Cơ chế Message Queue** | Danh sách đối tượng Python có khóa bảo vệ và điều hướng bằng Monitor Condition Variables. | Sử dụng POSIX Message Queue (`mq_open`, `mq_send`, `mq_receive`) lưu trữ trong kernel buffers của hệ điều hành. |
| **Kiểm soát nghẽn (Blocking)** | Hỗ trợ cờ `timeout=0.0` trả về đối tượng `IPCResult(BLOCKED)` để GUI vẽ animation mà không làm đơ giao diện. | Tiến trình gọi system call blocking sẽ được đưa vào hàng đợi `Waiting Queue` của hệ điều hành và nhường CPU (Context Switch). |
| **Ghi vết (Trace)** | Module `log_trace` ghi trực tiếp nano giây vào file CSV và phát signal cập nhật GUI. | Sử dụng các công cụ nhân như `strace`, `ftrace`, `eBPF` hoặc Event Tracing for Windows (ETW). |
| **Chèn lỗi (Fault Injection)** | Giả lập chủ động trong mã nguồn tầng ứng dụng (bơm delay, làm sai lệch checksum). | Sử dụng các công cụ kernel testing chuyên dụng như `chaos-mesh`, Linux Fault Injection Framework (`failmalloc`, `fail_page_alloc`). |
