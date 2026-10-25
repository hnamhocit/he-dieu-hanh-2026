# ĐẶC TẢ KỸ THUẬT: MODULE MESSAGE QUEUE (IPC)

> **Mã nhiệm vụ Jira:** `HDH-14` (Cơ chế hàng đợi FIFO/Priority & Đồng bộ), `HDH-15` (Khai báo module), `HDH-22` & `HDH-27` (Hiện thực lõi), `HDH-28` (Blocking/Non-blocking)  
> **Cơ chế IPC:** Hàng đợi thông điệp (Message Queue)  
> **Mô hình đồng bộ:** Monitor Pattern (Mutex Lock + Condition Variables `not_full`, `not_empty`)  
> **Phụ thuộc:** Tuân thủ Interface `IIPCMechanism` tại `src/core/ipc_interface.py`  

---

## 1. TỔNG QUAN KIẾN TRÚC

`MessageQueue` hiện thực cơ chế truyền thông điệp gián tiếp. Khác với vùng nhớ chia sẻ (Shared Memory) nơi các tiến trình trực tiếp truy cập vào ô nhớ chung, Message Queue lưu trữ dữ liệu dưới dạng các **gói tin độc lập (MessagePacket)** có cấu trúc, được điều phối bởi hệ điều hành hoặc module lõi quản lý hàng đợi.

### Đặc tính cốt lõi:
- **Cơ chế sắp xếp hàng đợi (Queue Policy):**
  - **FIFO (First-In, First-Out):** Mặc định xử lý các gói tin theo đúng trình tự thời gian gửi đến, đảm bảo tính công bằng và minh bạch giữa các tiến trình.
  - **Priority Queue:** Khi bật cờ `is_priority=True`, các gói tin có độ ưu tiên cao hơn (`priority` lớn hơn) sẽ được đưa lên đầu hàng đợi để tiêu thụ trước. Nếu hai gói tin có cùng `priority`, gói tin nào đến trước (dựa trên `timestamp`) sẽ được lấy ra trước.
- **An toàn đa luồng (Thread-safe Monitor Pattern):** Sử dụng `threading.Lock` kết hợp cùng hai `threading.Condition` (`not_full`, `not_empty`) để loại trừ tương hỗ và đánh thức tiến trình.

---

## 2. CẤU TRÚC DỮ LIỆU TRONG BỘ NHỚ (DATA STRUCTURES)

### 2.1. Lớp `MessagePacket` (Gói tin chuẩn HDH-13)
Mỗi thông điệp được chuẩn hóa thành một đối tượng `MessagePacket`:

| Thuộc tính | Kiểu dữ liệu | Mặc định | Ý nghĩa kỹ thuật |
| :--- | :--- | :---: | :--- |
| `id` | `int` | *Bắt buộc* | Định danh duy nhất của gói tin (> 0). |
| `sender` | `str` | *Bắt buộc* | Định danh tiến trình gửi (Producer). |
| `receiver` | `str` | *Bắt buộc* | Định danh tiến trình nhận đích (Consumer). |
| `message` | `str` | `""` | Nội dung payload của thông điệp. |
| `delay_ms` | `int` | `0` | Độ trễ giả lập trước khi gửi (ms). |
| `priority` | `int` | `0` | Mức độ ưu tiên (0 đến 5; số lớn hơn = ưu tiên cao hơn). |
| `simulate_error` | `str` | `"NONE"` | Loại lỗi giả lập (`NONE`, `DELAY`, `CHECKSUM`). |
| `mechanism` | `str` | `"MESSAGE_QUEUE"` | Định danh cơ chế truyền tin. |
| `timestamp` | `float` | `time.time()` | Mốc thời gian gói tin được khởi tạo. |
| `payload_size_bytes` | `int` | Tự động | Kích thước chuỗi payload tính theo bytes (`utf-8`). |

### 2.2. Lớp `MessageQueue`
Kế thừa từ `IIPCMechanism`, quản lý danh sách các `MessagePacket` với giới hạn dung lượng `capacity`:
- `_queue: list[MessagePacket]`: Danh sách lưu trữ các gói tin trong hàng đợi.
- `_is_priority: bool`: Cờ cấu hình chế độ hàng đợi ưu tiên.
- `_mutex = threading.Lock()`: Khóa nhị phân bảo vệ Critical Section của hàng đợi.
- `_not_full = threading.Condition(_mutex)`: Biến điều kiện báo hiệu hàng đợi có chỗ trống (được notify bởi Consumer).
- `_not_empty = threading.Condition(_mutex)`: Biến điều kiện báo hiệu hàng đợi có dữ liệu (được notify bởi Producer).

---

## 3. CƠ CHẾ ĐỒNG BỘ HÓA (MONITOR SYNCHRONIZATION)

### 3.1. Thao tác Produce (`SEND` / Enqueue)
1. Kiểm tra dung lượng hàng đợi: Nếu `len(_queue) >= capacity`:
   - Nếu `timeout == 0.0` (Non-blocking): Lập tức trả về `IPCResult(status="BLOCKED", success=False)` mà không làm treo luồng.
   - Nếu `timeout > 0`: Gọi `_not_full.wait(timeout)` chờ cho tới khi có chỗ trống hoặc hết giờ.
   - Nếu `timeout is None`: Gọi `_not_full.wait()` chờ vô hạn.
2. Đưa gói tin vào `_queue`:
   - Nếu `is_priority`: Dùng `heapq` hoặc chèn theo thứ tự `priority` giảm dần và `timestamp` tăng dần.
   - Nếu FIFO: Nạp vào cuối danh sách (`_queue.append(packet)`).
3. Đánh thức Consumer đang ngủ: Gọi `_not_empty.notify()`.
4. Ghi vết vi sự kiện qua `log_trace("ENQUEUE", f"Packet_ID: {packet.id}")`.

### 3.2. Thao tác Consume (`RECEIVE` / Dequeue)
1. Kiểm tra dữ liệu hàng đợi: Nếu `len(_queue) == 0`:
   - Nếu `timeout == 0.0` (Non-blocking): Lập tức trả về `IPCResult(status="BLOCKED", success=False)`.
   - Nếu `timeout > 0`: Gọi `_not_empty.wait(timeout)` chờ có tin nhắn mới hoặc hết giờ.
   - Nếu `timeout is None`: Gọi `_not_empty.wait()` chờ vô hạn.
2. Lấy gói tin ra khỏi `_queue`:
   - Rút phần tử đầu danh sách (`_queue.pop(0)`).
3. Đánh thức Producer đang ngủ: Gọi `_not_full.notify()`.
4. Ghi vết vi sự kiện qua `log_trace("DEQUEUE", f"Packet_ID: {packet.id}")`.

---

## 4. QUY ƯỚC GHI VẾT TRACE VÀ SNAPSHOT GUI

Module cung cấp hàm `get_state()` trả về snapshot phục vụ GUI và kiểm chứng Oracle:
- `buffer`: Danh sách ID hoặc dictionary tóm tắt các gói tin đang xếp hàng (ví dụ: `[ID:5(P2), ID:1(P0)]`).
- `count`: Số lượng gói tin hiện có trong hàng đợi.
- `capacity`: Sức chứa tối đa của hàng đợi.
- `is_full`: Cờ boolean kiểm tra hàng đợi đã đầy hay chưa.
- `is_empty`: Cờ boolean kiểm tra hàng đợi có rỗng hay không.
- `blocked_processes`: Danh sách định danh các tiến trình đang bị chặn tại `_not_full` hoặc `_not_empty`.
