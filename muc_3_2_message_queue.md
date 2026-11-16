# Mục 3.2. Module Message Queue

## 3.2.1. Tổng quan module

Module Message Queue (`src/core/message_queue.py`) cho phép các tiến trình trao đổi dữ liệu gián tiếp qua một hàng đợi gói tin có sức chứa giới hạn, an toàn khi nhiều luồng chạy song song.

Khác với Shared Memory (các tiến trình cùng đọc ghi một vùng nhớ), ở đây dữ liệu được đóng gói thành `MessagePacket` độc lập rồi mới xếp hàng.

| Thành phần | Vai trò |
| --- | --- |
| `MessagePacket` | Gói tin: `id`, `sender`, `receiver`, `message`, `delay_ms`, `priority`, `simulate_error`, `sequence` |
| `MessageQueue(capacity, is_priority)` | Hàng đợi lõi, kế thừa `IIPCMechanism`; chế độ FIFO hoặc Priority |
| `produce(item, process_id, timeout)` | Gửi gói tin vào hàng đợi |
| `consume(process_id, timeout)` | Lấy gói tin ra khỏi hàng đợi |
| `get_state()` | Chụp trạng thái cho GUI và kiểm chứng Oracle |

Mọi thao tác trả về `IPCResult` với trạng thái `SUCCESS`, `BLOCKED`, `TIMEOUT` hoặc `ERROR`. Module không ném ngoại lệ ra ngoài khi gửi hoặc nhận.

## 3.2.2. Cấu trúc Priority Queue

Hàng đợi là một `list` các `MessagePacket` luôn được giữ ở trạng thái đã sắp xếp. Phần tử đầu là gói tin được lấy ra trước.

Khóa sắp xếp:

```
key(p) = ( -p.priority , p.sequence )
```

1. `priority` lớn hơn thì xếp trước (số lớn = ưu tiên cao).
2. **Luật phân xử hòa (tie-breaking):** cùng `priority` thì gói tin vào hàng đợi trước được lấy ra trước (FIFO trong cùng mức ưu tiên).

`sequence` là số nguyên tăng dần, được gán khi gói tin thực sự vào hàng đợi, lúc đang giữ mutex nên không bao giờ trùng. Vì thế không có hai gói tin nào hòa hoàn toàn. Dùng `sequence` thay cho `timestamp` vì `timestamp` chỉ là thời điểm tạo gói tin và hai gói có thể trùng giá trị.

Khi chèn, gói tin mới chỉ chèn trước gói tin có `priority` **thấp hơn hẳn**. Nếu bằng nhau thì đứng sau. Chế độ FIFO (`is_priority=False`) luôn thêm vào cuối.

**Ví dụ** (`capacity` = 10, chế độ Priority; gửi theo thứ tự A(P1), B(P5), C(P5), D(P5), E(P1)):

| Sau lần gửi | Hàng đợi, đầu → cuối |
| --- | --- |
| A(P1) | A(P1) |
| B(P5) | B(P5), A(P1) |
| C(P5) | B(P5), C(P5), A(P1) |
| D(P5) | B(P5), C(P5), D(P5), A(P1) |
| E(P1) | B(P5), C(P5), D(P5), A(P1), E(P1) |

Thứ tự lấy ra: **B, C, D, A, E**.

## 3.2.3. Cơ chế đánh thức luồng bằng Condition Variable

Module dùng mô hình **Monitor**: một `mutex` bảo vệ hàng đợi và hai Condition Variable dùng chung mutex đó.

| Thành phần | Ai ngủ | Ai đánh thức |
| --- | --- | --- |
| `not_full` | Producer, khi hàng đợi đầy | Consumer, sau khi lấy 1 gói tin |
| `not_empty` | Consumer, khi hàng đợi rỗng | Producer, sau khi thêm 1 gói tin |

`wait()` nhả mutex và đưa luồng vào trạng thái ngủ. `notify()` đánh thức đúng một luồng đang chờ trên điều kiện đó, luồng này phải lấy lại mutex trước khi chạy tiếp. Tách thành hai Condition giúp Producer không đánh thức nhầm Producer khác và tránh đánh thức hàng loạt. `notify_all()` chỉ dùng trong `reset()`.

**Vì sao dùng `WHILE` thay vì `IF`:** sau khi tỉnh dậy, luồng phải kiểm tra lại điều kiện, vì luồng khác có thể đã chiếm mất chỗ trống hoặc gói tin, hoặc luồng tỉnh dậy giả (spurious wakeup).

**Tham số `timeout`:**

| `timeout` | Khi điều kiện chưa thỏa | Kết quả |
| --- | --- | --- |
| `0.0` | Không chờ (non-blocking, dùng cho GUI) | `BLOCKED` ngay |
| `> 0.0` | Chờ tối đa `timeout` giây | `TIMEOUT` nếu hết hạn |
| `None` | Chờ vô hạn | Chỉ trả về khi thành công |
| Âm, NaN, sai kiểu | Không chạy | `ERROR` (`INVALID_TIMEOUT`) |

## 3.2.4. Mã giả thuật toán

**SEND (`produce`)** — gửi có điều kiện: chỉ gửi khi hàng đợi chưa đầy.

```
PROCEDURE SEND(item, pid, timeout):
    IF timeout không hợp lệ THEN RETURN ERROR(INVALID_TIMEOUT)
    packet <- NORMALIZE(item, pid)
    IF packet không hợp lệ OR len(packet.message) > 100 THEN RETURN ERROR(INVALID_PACKET)
    deadline <- (timeout = None) ? +INF : now() + timeout

    LOCK(mutex)
    WHILE size(queue) >= capacity DO              -- Overflow: hàng đợi đầy
        IF timeout = 0 THEN
            UNLOCK(mutex); RETURN BLOCKED(QUEUE_OVERFLOW)
        remaining <- deadline - now()
        IF remaining <= 0 THEN
            UNLOCK(mutex); RETURN TIMEOUT(PRODUCE_TIMEOUT)
        ghi nhận pid đang bị chặn
        WAIT(not_full, remaining)                 -- nhả mutex, ngủ; tỉnh dậy lấy lại mutex
    END WHILE
    bỏ ghi nhận pid bị chặn

    packet.sequence <- seq_counter                -- duy nhất vì đang giữ mutex
    seq_counter     <- seq_counter + 1
    IF mode = PRIORITY THEN
        i <- chỉ số nhỏ nhất sao cho packet < queue[i]  (nếu không có thì size(queue))
        INSERT(queue, i, packet)
    ELSE
        APPEND(queue, packet)

    NOTIFY(not_empty)                             -- đánh thức 1 Consumer
    UNLOCK(mutex)
    RETURN SUCCESS(packet)
```

**RECEIVE (`consume`)** — nhận có điều kiện: chỉ nhận khi hàng đợi không rỗng.

```
PROCEDURE RECEIVE(pid, timeout):
    IF timeout không hợp lệ THEN RETURN ERROR(INVALID_TIMEOUT)
    deadline <- (timeout = None) ? +INF : now() + timeout

    LOCK(mutex)
    WHILE size(queue) = 0 DO                      -- Underflow: hàng đợi rỗng
        IF timeout = 0 THEN
            UNLOCK(mutex); RETURN BLOCKED(QUEUE_UNDERFLOW)
        remaining <- deadline - now()
        IF remaining <= 0 THEN
            UNLOCK(mutex); RETURN TIMEOUT(CONSUME_TIMEOUT)
        ghi nhận pid đang bị chặn
        WAIT(not_empty, remaining)
    END WHILE
    bỏ ghi nhận pid bị chặn

    packet <- REMOVE_FIRST(queue)                 -- ưu tiên cao nhất, vào sớm nhất
    NOTIFY(not_full)                              -- đánh thức 1 Producer
    UNLOCK(mutex)
    RETURN SUCCESS(packet)
```

Trong mã thật, vòng chờ nằm trong `try/finally` để luôn gỡ trạng thái "đang bị chặn", kể cả khi hết hạn. Mọi lỗi bất thường được bắt bởi lớp bao ngoài và trả về `ERROR`.

## 3.2.5. Xử lý ngoại lệ (HDH-95)

Mọi tình huống không thể thực hiện ngay đều trả về `IPCResult` có mã lỗi trong `detail`, không làm treo hay làm sập chương trình.

| Tình huống | `status` | Mã trong `detail` |
| --- | --- | --- |
| Hàng đợi đầy, `timeout=0.0` | `BLOCKED` | `QUEUE_OVERFLOW` |
| Hàng đợi rỗng, `timeout=0.0` | `BLOCKED` | `QUEUE_UNDERFLOW` |
| Hết hạn khi gửi | `TIMEOUT` | `PRODUCE_TIMEOUT` |
| Hết hạn khi nhận | `TIMEOUT` | `CONSUME_TIMEOUT` |
| `timeout` âm, NaN, sai kiểu | `ERROR` | `INVALID_TIMEOUT` |
| `priority`, `delay_ms`, `message` sai kiểu; dict lỗi | `ERROR` | `INVALID_PACKET` |
| Payload dài hơn 100 ký tự | `ERROR` | Bị chặn bởi tầng Guard |
| Lỗi bất thường | `ERROR` | `PRODUCE_FAILED`, `CONSUME_FAILED` |

Khi hết hạn hoặc gặp lỗi, tiến trình được xóa khỏi `blocked_processes`, nên `get_state()` không hiển thị tiến trình đã bỏ cuộc.

Tie-breaking được giữ đúng khi nhiều Producer cùng gửi song song, khi Producer bị chặn được đánh thức, và khi cùng một đối tượng gói tin được gửi lại (module tạo bản sao trước khi gán `sequence`). Các trường hợp này đều có unit test trong `tests/test_message_queue.py`.
