# ĐẶC TẢ KỸ THUẬT: CƠ CHẾ HÀNG ĐỢI VÀ ĐỒNG BỘ (HDH-14)

**Mã nhiệm vụ Jira:** HDH-14  
**Chủ đề:** Xác định cơ chế hàng đợi (FIFO / Priority) và cơ chế Blocking / Non-blocking.

---

## 1. Cơ chế sắp xếp và quản lý hàng đợi (Queue Type)
- **Lựa chọn:** **FIFO (First-In, First-Out)** làm cơ chế cốt lõi.
- **Lý do kỹ thuật:** 
  - Đảm bảo tính tuần tự, minh bạch và công bằng giữa các tiến trình truyền nhận bản tin.
  - Các gói tin (`MessagePacket`) gửi vào trước sẽ được xử lý và lấy ra trước theo đúng trình tự thời gian.
- **Hỗ trợ mở rộng:** Cấu trúc hàng đợi có thể kiểm tra thêm cờ ưu tiên (`priority`) trong trường hợp cần mô phỏng các gói tin ngắt khẩn cấp.

---

## 2. Cơ chế Đồng bộ (Blocking & Non-blocking Strategy)
Hệ thống thiết kế cơ chế xử lý trạng thái đầy/rỗng của hàng đợi thông qua tham số `timeout`:

### A. Blocking Mode (Mặc định)
- **Khi Hàng đợi đầy (`Full`):** Tiến trình gửi (`SEND`) sẽ bị chặn (chuyển sang trạng thái `WAIT`) cho đến khi có ô trống trong hàng đợi hoặc hết thời gian `timeout` cấu hình.
- **Khi Hàng đợi rỗng (`Empty`):** Tiến trình nhận (`RECEIVE`) sẽ ở trạng thái chờ cho đến khi xuất hiện thông điệp mới hoặc hết thời gian `timeout`.

### B. Non-blocking Mode
- Được kích hoạt khi truyền tham số `timeout = 0`.
- Nếu hàng đợi đầy hoặc rỗng, hàm sẽ **trả về ngay lập tức** kèm theo mã trạng thái lỗi tương ứng (`BUFFER_OVERFLOW` hoặc `QUEUE_EMPTY`), tuyệt đối **không làm treo giao diện** hoặc luồng chính của ứng dụng PyQt6.