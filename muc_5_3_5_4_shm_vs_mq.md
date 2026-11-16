# Mục 5.3. Chi phí sao chép bộ nhớ và giới hạn khi hàng đợi đầy

## 5.3.1. Chi phí sao chép bộ nhớ: hai lần copy User ↔ Kernel

Message Queue là cơ chế truyền thông điệp gián tiếp: dữ liệu đi qua vùng đệm do nhân hệ điều hành (kernel) quản lý. Mỗi thông điệp phải được sao chép **hai lần**:

| Bước | Thao tác | Hướng sao chép |
| --- | --- | --- |
| 1 | Tiến trình gửi gọi `SEND` | Bộ nhớ người dùng (User) của bên gửi → vùng đệm của Kernel |
| 2 | Tiến trình nhận gọi `RECEIVE` | Vùng đệm của Kernel → bộ nhớ người dùng (User) của bên nhận |

Mỗi lần sao chép tốn thời gian tỉ lệ với kích thước thông điệp. Gọi `s` là số byte của một thông điệp thì tổng lượng dữ liệu phải chép cho mỗi thông điệp là `2s`. Ngoài ra mỗi lần gọi `SEND`/`RECEIVE` là một lệnh gọi hệ thống (system call), kéo theo chi phí chuyển giữa chế độ người dùng và chế độ nhân.

Shared Memory khác ở chỗ vùng nhớ chung được ánh xạ vào không gian địa chỉ của cả hai tiến trình. Sau khi thiết lập, bên gửi ghi thẳng vào vùng nhớ và bên nhận đọc thẳng từ đó, nên **không có lần sao chép nào qua Kernel** cho mỗi thông điệp (chi phí system call chỉ phát sinh ở bước tạo và ánh xạ vùng nhớ, và ở các thao tác đồng bộ nếu có chờ).

| | Message Queue | Shared Memory |
| --- | --- | --- |
| Số lần sao chép mỗi thông điệp qua Kernel | 2 | 0 |
| Dữ liệu phải chép mỗi thông điệp | `2s` byte | 0 byte (ghi và đọc trực tiếp trên vùng chung) |
| System call mỗi thông điệp | 2 (gửi và nhận) | Không bắt buộc (chỉ khi cần chờ đồng bộ) |

**Trong đồ án này:** payload tối đa 100 ký tự (tầng Guard chặn hơn mức này), nên `2s` rất nhỏ và chênh lệch về thời gian là không đáng kể. Bản mô phỏng bằng Python cũng không thực hiện sao chép qua Kernel thật; hai lần sao chép ở trên là mô hình lý thuyết dùng để đánh giá, chưa có số đo thực nghiệm. Sự khác biệt chỉ trở nên đáng kể khi thông điệp lớn hoặc tần suất gửi rất cao.

## 5.3.2. Giới hạn khi hàng đợi đầy

Hàng đợi có sức chứa cố định `capacity`. Khi hàng đợi đầy, Producer không thể gửi thêm, và kết quả phụ thuộc vào tham số `timeout`:

| `timeout` | Hành vi khi hàng đợi đầy | Kết quả |
| --- | --- | --- |
| `0.0` | Không chờ (non-blocking, dùng cho GUI) | `BLOCKED` ngay, mã `QUEUE_OVERFLOW` |
| `> 0.0` | Ngủ trên `not_full` tối đa `timeout` giây | `TIMEOUT` (`PRODUCE_TIMEOUT`) nếu hết hạn |
| `None` | Ngủ trên `not_full` đến khi có chỗ trống | Chỉ trả về khi gửi thành công |

Hệ quả cần lưu ý:

1. **Tốc độ hệ thống bị giới hạn bởi bên chậm nhất:** nếu Consumer nhận chậm hơn Producer gửi, hàng đợi đầy và Producer phải chờ hoặc bị từ chối.
2. **Nguy cơ chờ vô hạn:** với `timeout=None`, nếu không còn Consumer nào lấy tin thì Producer ngủ mãi. Vì vậy luồng worker nên đặt `timeout` hữu hạn.
3. **Không mất gói tin:** gói tin không vào được hàng đợi thì bị từ chối rõ ràng (`BLOCKED` hoặc `TIMEOUT`), không bị ghi đè hay bỏ qua âm thầm.
4. **Chi phí đánh thức:** Producer đang ngủ chỉ được đánh thức khi Consumer lấy một gói tin ra (`notify` trên `not_full`), tốn thêm chuyển ngữ cảnh so với đường không chờ.

Shared Memory trong đồ án là bộ đệm vòng (Circular Buffer) kích thước `capacity` cũng có giới hạn tương tự: khi Semaphore `empty = 0` thì bộ đệm đầy và Producer bị chặn, không thể ghi thêm (ngăn Buffer Overflow). Điểm khác là Shared Memory trả `BLOCKED` cho cả hai trường hợp (không chờ và hết hạn chờ), còn Message Queue phân biệt `BLOCKED` với `TIMEOUT`. Khi Producer bị chặn do Mutex bận, Shared Memory còn hoàn trả Semaphore `empty` đã chiếm (rollback) để không rò rỉ.

---

# Mục 5.4. Bảng so sánh Trade-off giữa Shared Memory và Message Queue

| Tiêu chí | Shared Memory (SHM) | Message Queue (MQ) |
| --- | --- | --- |
| Cách truyền dữ liệu | Hai tiến trình dùng chung một vùng nhớ, tổ chức thành bộ đệm vòng gồm các ô (slot) | Gửi và nhận gói tin qua hàng đợi do Kernel quản lý |
| Sao chép qua Kernel | 0 lần cho mỗi thông điệp | 2 lần (User → Kernel, Kernel → User) |
| Tốc độ với dữ liệu lớn | Nhanh nhất, không tốn chi phí sao chép | Chậm hơn, tăng theo kích thước thông điệp |
| Đồng bộ hóa | Tự đảm bảo bằng 2 Semaphore đếm (`empty`, `full`) và 1 `mutex`; phải chiếm Semaphore đếm trước `mutex` để tránh Deadlock, và rollback khi chiếm `mutex` thất bại; dễ sai gây tranh chấp dữ liệu | Monitor (1 `mutex` và 2 Condition Variable `not_full`, `not_empty`) đã xử lý loại trừ tương hỗ và chờ/đánh thức; vòng `WHILE` kiểm tra lại điều kiện sau khi tỉnh |
| Ranh giới thông điệp | Chỉ có ranh giới ô nhớ; ý nghĩa dữ liệu trong ô do hai bên tự quy ước | Có sẵn, mỗi gói tin (`MessagePacket`) là một đơn vị độc lập có người gửi, người nhận, độ ưu tiên |
| Thứ tự và ưu tiên | Chỉ theo thứ tự ghi vòng của `in_ptr` và `out_ptr`, không có ưu tiên | FIFO hoặc Priority, cùng mức ưu tiên thì vào trước ra trước (tie-breaking bằng `sequence`) |
| Khi đầy | `empty = 0`: Producer bị chặn, trả `BLOCKED` (cả khi hết hạn chờ) | Trả `BLOCKED` (`QUEUE_OVERFLOW`), `TIMEOUT` hoặc chờ vô hạn tùy `timeout` |
| Độ an toàn và cô lập | Thấp hơn: một tiến trình ghi sai có thể làm hỏng dữ liệu của bên kia | Cao hơn: dữ liệu đi qua Kernel nên mỗi bên chỉ thấy bản sao của mình |
| Độ phức tạp lập trình | Cao (tự đồng bộ, tự quy ước định dạng) | Thấp hơn (API gửi/nhận rõ ràng) |
| Phù hợp khi | Trao đổi khối dữ liệu lớn, tần suất cao, hai bên tin cậy nhau | Trao đổi thông điệp nhỏ, cần thứ tự hoặc ưu tiên, cần đơn giản và an toàn |

**Kết luận:** SHM đánh đổi sự đơn giản và an toàn lấy tốc độ, còn MQ đánh đổi tốc độ (hai lần sao chép và system call) lấy sự tiện lợi, thứ tự, ưu tiên và cô lập dữ liệu. Với thông điệp nhỏ như trong đồ án (tối đa 100 ký tự), chi phí sao chép của MQ không đáng kể nên MQ là lựa chọn hợp lý; SHM chỉ thật sự có lợi khi khối lượng dữ liệu lớn.
