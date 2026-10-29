# KẾ HOẠCH KIỂM THỬ (TEST PLAN) 

## 1. Mục tiêu kiểm thử
* Test xem luồng truyền nhận dữ liệu giữa các tiến trình có chạy đúng không.
* Kiểm tra các cơ chế đồng bộ hóa (Mutex/Semaphore) xem có bị lỗi tranh chấp dữ liệu (Race Condition) khi chạy song song không.
* Đảm bảo app không bị crash hoặc đóng đột ngột khi người dùng nạp file CSV bị lỗi hoặc sai định dạng.

## 2. Danh sách các ca kiểm thử (Test Cases)

### Phần A: Kiểm thử cơ chế Bộ nhớ chia sẻ (Shared Memory)
*Mục đích: Test tính đồng bộ của vùng đệm và cơ chế khóa Mutex chống ghi đè dữ liệu.*

| Mã TC | Tên Ca Kiểm Thử | Điều Kiện Đầu Vào (Kịch bản CSV / GUI) | Kết Quả Kỳ Vọng (Expected Result) |
| :--- | :--- | :--- | :--- |
| **TC-01** | Đọc/Ghi cơ bản | File CSV có 1 lệnh PRODUCE (ghi dữ liệu) rồi đến 1 lệnh CONSUME (đọc dữ liệu). | Tiến trình gửi ghi được vào RAM dùng chung, tiến trình nhận đọc ra đúng nội dung đó, log báo SUCCESS. |
| **TC-02** | Lỗi đầy bộ đệm (Buffer Overflow) | Giới hạn buffer là 2, nhưng file CSV bắt PRODUCE liên tiếp 3 tin nhắn mà không có ai CONSUME. | Lệnh thứ 3 sẽ bị chặn lại (BLOCKED), app vẫn chạy bình thường chứ không bị đơ hay treo giao diện. |
| **TC-03** | Lỗi bộ đệm rỗng (Buffer Underflow) | Vừa bật mô phỏng lên, bộ đệm chưa có gì mà file CSV đã gọi lệnh CONSUME để lấy dữ liệu. | Tiến trình nhận sẽ bị bắt dừng lại chờ (BLOCKED) cho đến khi có tiến trình khác ghi dữ liệu vào. |
| **TC-04** | Test tranh chấp (Race Condition) | Để độ trễ bằng 0, cho 3 tiến trình cùng lao vào PRODUCE (ghi dữ liệu) vào một ô nhớ cùng một lúc. | Khóa Mutex hoạt động đúng, mỗi thời điểm chỉ 1 đứa được ghi, dữ liệu cuối cùng không bị ghi đè lỗi. |
| **TC-05** | Giải phóng bộ nhớ | Chạy kịch bản cho bộ đệm đầy hẳn -> CONSUME sạch sẽ dữ liệu -> chạy tiếp lệnh PRODUCE mới. | RAM dùng chung được giải phóng và tái sử dụng ngon lành, biểu đồ trên GUI cập nhật đúng dung lượng trống. |

### Phần B: Kiểm thử cơ chế Truyền thông điệp (Message Passing)
*Mục đích: Test cấu trúc hàng đợi tin nhắn (Message Queue), cơ chế chặn luồng và độ ưu tiên.*

| Mã TC | Tên Ca Kiểm Thử | Điều Kiện Đầu Vào (Kịch bản CSV / GUI) | Kết Quả Kỳ Vọng (Expected Result) |
| :--- | :--- | :--- | :--- |
| **TC-06** | Test hàng đợi FIFO | Gửi liên tiếp 2 tin nhắn có độ ưu tiên bằng nhau (priority = 0) vào hàng đợi. | Tiến trình nhận sẽ bốc được tin nhắn gửi trước ra đọc trước, tuân thủ đúng luật FIFO. |
| **TC-07** | Test hàng đợi ưu tiên (Priority Queue) | Nạp file CSV có tin nhắn thường (priority = 0) và tin hỏa tốc (priority = 5) cùng lúc. | Khi tiến trình gọi lệnh RECEIVE, tin nhắn hỏa tốc phải được bốc ra xử lý trước, kể cả khi nó đến sau. |
| **TC-08** | Hộp thư bị đầy (Mailbox Full) | Hộp thư giới hạn 4 tin, tiến trình gửi liên tục 5 tin mà tiến trình nhận chưa kịp RECEIVE tin nào. | Tin thứ 5 sẽ bị từ chối hoặc bắt đứng chờ, hệ thống trả về trạng thái BLOCKED an toàn. |
| **TC-09** | Giả lập độ trễ (Delay Time) | Cấu hình trong file CSV cột delay_ms = 2000 (tức là trễ 2 giây). | Khi bấm chạy, tiến trình gửi sẽ dừng đúng 2 giây rồi mới ném tin nhắn vào hàng đợi. |
| **TC-10** | Gửi sai địa chỉ (Invalid Routing) | Gói tin ghi tên tiến trình nhận là một cái tên linh tinh không tồn tại trong hệ thống. | App không bị crash, log hệ thống báo lỗi tìm không thấy tiến trình nhận và bỏ qua gói tin đó an toàn. |