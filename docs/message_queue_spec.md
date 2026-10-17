# TÀI LIỆU ĐẶC TẢ KỸ THUẬT: CẤU TRÚC MESSAGEPACKET VÀ MESSAGEQUEUE

---

## 1. Giới thiệu chung
Trong hệ thống mô phỏng Giao tiếp Liên tiến trình (IPC) của đồ án, hai thành phần cốt lõi đảm nhận việc truyền tải dữ liệu là `MessagePacket` và `MessageQueue`:
* **MessagePacket**: Khuôn mẫu (định dạng) của một gói tin chứa đầy đủ thông tin định danh, nội dung và các cờ trạng thái lỗi.
* **MessageQueue**: Cấu trúc hàng đợi trung gian quản lý các gói tin theo cơ chế an toàn (`thread/process-safe`), giúp điều phối luồng gửi và nhận giữa các tiến trình mà không xảy ra tranh chấp dữ liệu.

---

## 2. Đặc tả cấu trúc bản tin (MessagePacket)
Mỗi bản tin truyền đi trong hệ thống được định nghĩa dưới dạng một đối tượng (hoặc struct) mang các thông tin sau:

| Tên trường (Key) | Kiểu dữ liệu | Ý nghĩa kỹ thuật |
| :--- | :--- | :--- |
| `id` | `int` | Mã định danh duy nhất của thông điệp. |
| `sender` | `str` | Tên tiến trình gửi (Ví dụ: `Process_A`). |
| `receiver` | `str` | Tên tiến trình nhận (Ví dụ: `Process_B`). |
| `mechanism` | `str` | Cơ chế IPC sử dụng (`MESSAGE_QUEUE`). |
| `payload_size_bytes` | `int` | Kích thước thực tế của nội dung thông điệp tính bằng byte. |
| `message` | `str` | Nội dung văn bản truyền đi. |
| `delay_ms` | `int` | Thời gian trễ giả lập trước khi gửi (đơn vị: mili-giây). |
| `simulate_error` | `str` | Cờ mô phỏng lỗi (`NONE`, `BUFFER_OVERFLOW`, v.v.). |
| `timestamp` | `float` | Thời điểm bản tin được khởi tạo. |

---

## 3. Đặc tả cấu trúc hàng đợi (MessageQueue)
Hàng đợi thông điệp đóng vai trò lưu trữ tạm thời các gói tin, hỗ trợ hai thao tác chính là **đẩy vào (enqueue)** và **lấy ra (dequeue)** dựa trên cơ chế hàng đợi an toàn đa tiến trình.

* **Sức chứa (Capacity):** Giới hạn số lượng gói tin tối đa mà hàng đợi có thể chứa cùng một thời điểm.
* **Cơ chế đồng bộ (Mutex / Lock):** Đảm bảo không xảy ra hiện tượng ghi đè hoặc xung đột dữ liệu (`Race Condition`) khi nhiều tiến trình cùng truy cập hàng đợi.
* **Xử lý trạng thái biên:** 
  * Khi hàng đợi đầy (`Full`), tiến trình gửi sẽ phải chờ hoặc bị chặn theo cấu hình `timeout`.
  * Khi hàng đợi rỗng (`Empty`), tiến trình nhận sẽ ở trạng thái chờ (`WAIT`) cho đến khi có dữ liệu mới.

---

## 4. Định dạng Trace Log đầu ra (CSV Specification)
Để phục vụ cho việc kiểm thử và theo dõi lịch sử hoạt động, mọi thao tác qua `MessageQueue` đều được ghi nhận ra file log dạng `.csv` với cấu trúc chuẩn sau:

```csv
timestamp,step_index,process_id,action,mechanism,status,latency_ms,detail
2026-10-16T14:00:01.002,1,Process_A,SEND,MESSAGE_QUEUE,SUCCESS,1.25,"Enqueued Packet ID 1"
2026-10-16T14:00:01.005,2,Process_B,RECEIVE,MESSAGE_QUEUE,SUCCESS,0.85,"Dequeued Packet ID 1"
16T14:00:01.010,3,Process_A,SEND,MESSAGE_QUEUE,FAILED,5.00,"Buffer Overflow: Queue is full"
