# TÀI LIỆU ĐẶC TẢ KỸ THUẬT: MODULE MESSAGE QUEUE (IPC)

> **Mã nhiệm vụ Jira:** `HDH-22` (Hiện thực luồng lõi Message Queue)
> **Phụ thuộc:** Tuân thủ Interface `IIPCMechanism` tại `src/core/ipc_interface.py`

---

## 1. Tổng quan Kiến trúc
`MessageQueue` hiện thực cơ chế truyền thông điệp gián tiếp. Khác với luồng dữ liệu thô của Pipe hay vùng nhớ của Shared Memory, Message Queue lưu trữ dữ liệu dưới dạng các **gói tin độc lập (Packets)** có cấu trúc. 

Đặc tính cốt lõi của module này trong đồ án:
- Hỗ trợ **Độ ưu tiên (Priority)**: Gói tin có mức độ ưu tiên cao sẽ được đẩy lên đầu hàng đợi để xử lý trước (bất chấp thứ tự gửi).
- Đảm bảo **Thread-safe**: An toàn tuyệt đối khi có nhiều Producer (tiến trình gửi) và Consumer (tiến trình nhận) truy cập đồng thời.

---

## 2. Cấu trúc dữ liệu trong RAM (Data Structures)

### 2.1. Lớp `MessagePacket` (Gói tin)
Đối tượng lưu trữ trong bộ nhớ, được Parser khởi tạo từ việc đọc file `input/*.csv` (Tham khảo Mục 6.1 README).

- `id` (int): Định danh gói tin.
- `priority` (int): Mức độ ưu tiên (số càng lớn, ưu tiên càng cao. Mặc định: 0).
- `sender` (str): Tiến trình gửi.
- `receiver` (str): Tiến trình nhận đích.
- `message` (str): Dữ liệu truyền tải.
- `timestamp` (float): Thời điểm gói tin được sinh ra (dùng để giải quyết tranh chấp nếu 2 gói tin có cùng priority).

### 2.2. Lớp `MessageQueueCore` (Hàng đợi lõi)
Sử dụng cấu trúc **Priority Queue** (Gợi ý: Dùng module `queue.PriorityQueue` hoặc `heapq` của Python) với giới hạn kích thước (`capacity`).

---

## 3. Cơ chế Đồng bộ & Thuật toán (Synchronization)

Hệ thống sử dụng các nguyên thủy đồng bộ (Synchronization Primitives) sau để quản lý hàng đợi:

1. **`Mutex` (Lock):** Đảm bảo tại một thời điểm chỉ có ĐÚNG MỘT tiến trình được phép thao tác (Push/Pop) vào hàng đợi.
2. **`Semaphore_Empty`:** Đếm số slot trống trong hàng đợi. Khởi tạo = `capacity`.
   - Lệnh `SEND` sẽ gọi `wait(Empty)`. Nếu hàng đợi đầy (Empty = 0), tiến trình gửi bị `BLOCKED` hoặc văng lỗi `BUFFER_OVERFLOW` (tùy cấu hình).
3. **`Semaphore_Full`:** Đếm số gói tin đang có trong hàng đợi. Khởi tạo = 0.
   - Lệnh `RECEIVE` sẽ gọi `wait(Full)`. Nếu hàng đợi rỗng (Full = 0), tiến trình nhận bị `BLOCKED` (chờ) cho đến khi có dữ liệu.

---

## 4. Quy ước Ghi Log (Trace Logging)

Module phải trả về đối tượng `IPCResult` với các trường dữ liệu tuân thủ nghiêm ngặt **Mục 6.2 của README.md**. Không tự ý chế ra format log riêng.

**Hướng dẫn map dữ liệu cho Message Queue:**
- Cột `action`: Chỉ sử dụng `SEND`, `RECEIVE`, `LOCK`, `UNLOCK`, `WAIT`.
- Cột `buffer_state`: Xuất danh sách ID hoặc tóm tắt các gói tin đang nằm trong hàng đợi. 
  * Ví dụ: `"[ID:5(P2), ID:1(P0)]"` (thể hiện rõ gói tin ưu tiên 2 đang xếp trước ưu tiên 0).
- Cột `sync_state`: Ghi rõ trạng thái Semaphore. 
  * Ví dụ: `"(Mutex: 1, Empty: 8, Full: 2)"`.
- Cột `detail`: Ghi rõ lý do thành công hoặc thất bại. 
  * Ví dụ thành công: `"Enqueued with priority 2"`. 
  * Ví dụ thất bại: `"Blocked: Queue is full"`.
