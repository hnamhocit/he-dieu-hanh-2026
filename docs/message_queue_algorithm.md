# THUẬT TOÁN MESSAGE QUEUE: PRIORITY QUEUE, PSEUDOCODE GỬI/NHẬN VÀ CHI PHÍ NGẮT/ĐÁNH THỨC

> **Mã nhiệm vụ Jira:** HDH-89
> **Bám theo:** `src/core/message_queue.py` (class `MessageQueue`, `MessagePacket`) và `src/core/ipc_interface.py`
> **Tài liệu liên quan:** `message_queue_spec.md` (HDH-22), `queue_mechanism_spec.md` (HDH-14)

---

## 1. Phạm vi

Tài liệu này mô tả ba nội dung của task HDH-89:

1. Cấu trúc dữ liệu Priority Queue và quy tắc xếp thứ tự gói tin.
2. Pseudocode `SEND` (gửi) và `RECEIVE` (nhận) có điều kiện theo mô hình Monitor.
3. Phân tích chi phí chặn (ngắt) và đánh thức (wake-up) của luồng.

"Có điều kiện" nghĩa là: gửi chỉ khi hàng đợi chưa đầy, nhận chỉ khi hàng đợi chưa rỗng. Nếu điều kiện chưa thỏa thì luồng chờ, trả về ngay hoặc hết hạn tùy tham số `timeout`. Hàng đợi không lọc gói tin theo trường `receiver`.

---

## 2. Cấu trúc Priority Queue

### 2.1. Thành phần

| Thành phần | Kiểu | Vai trò |
|---|---|---|
| `_queue` | `list[MessagePacket]` | Danh sách luôn được giữ ở trạng thái đã sắp xếp. Phần tử đầu là gói tin sẽ được lấy ra kế tiếp |
| `_capacity` | `int` | Số gói tin tối đa (> 0) |
| `_seq_counter` | `int` | Bộ đếm tăng dần, chỉ thay đổi khi đang giữ mutex |
| `_is_priority` | `bool` | `False`: chế độ FIFO. `True`: chế độ Priority |

Mỗi `MessagePacket` có thêm trường `sequence`, được gán tại thời điểm gói tin thực sự vào hàng đợi (không phải lúc tạo gói tin).

### 2.2. Quan hệ thứ tự

Gói tin `a` được lấy ra trước gói tin `b` khi khóa sắp xếp của `a` nhỏ hơn:

```
key(p) = ( -p.priority , p.sequence )
```

1. `priority` lớn hơn thì xếp trước (số lớn = ưu tiên cao).
2. Cùng `priority` thì `sequence` nhỏ hơn (vào trước) xếp trước, nghĩa là FIFO trong cùng mức ưu tiên.

Vì `sequence` là duy nhất nên không bao giờ có hai gói tin hòa nhau hoàn toàn, thứ tự lấy ra luôn xác định.

### 2.3. Bất biến (invariants)

Các điều kiện sau luôn đúng mỗi khi mutex được nhả:

- `0 <= len(_queue) <= capacity`.
- `_queue` được sắp tăng dần theo `key`.
- Các `sequence` trong `_queue` đôi một khác nhau và `_seq_counter` lớn hơn tất cả chúng.
- Chế độ FIFO: mọi gói tin được thêm vào cuối nên thứ tự ra trùng thứ tự vào.

### 2.4. Ví dụ

Dung lượng 4, chế độ Priority. Thứ tự gửi: gói 1 (P0), gói 2 (P2), gói 3 (P0), gói 4 (P2).

| Sau lệnh | `sequence` gán | Trạng thái hàng đợi (`buffer_state`) |
|---|---|---|
| SEND gói 1 (P0) | 0 | `[ID:1(P0)]` |
| SEND gói 2 (P2) | 1 | `[ID:2(P2), ID:1(P0)]` |
| SEND gói 3 (P0) | 2 | `[ID:2(P2), ID:1(P0), ID:3(P0)]` |
| SEND gói 4 (P2) | 3 | `[ID:2(P2), ID:4(P2), ID:1(P0), ID:3(P0)]` |

Thứ tự nhận: 2, 4, 1, 3. Cùng P2 thì gói 2 trước gói 4, cùng P0 thì gói 1 trước gói 3.

### 2.5. So sánh các lựa chọn cấu trúc dữ liệu

Gọi `n` là số gói tin đang có trong hàng đợi.

| Cấu trúc | Chèn | Lấy phần tử đầu | Snapshot theo thứ tự ưu tiên | Ghi chú |
|---|---|---|---|---|
| Danh sách sắp xếp (đang dùng) | O(n) so sánh + O(n) dịch chuyển | O(n) với `pop(0)` | O(n), danh sách đã có sẵn thứ tự | Dễ cho GUI hiển thị đúng thứ tự |
| `heapq` | O(log n) | O(log n) | O(n log n), phải sắp xếp một bản sao | Nhanh hơn khi `n` lớn, nhưng khó hiển thị |
| `collections.deque` (chỉ FIFO) | O(1) | O(1) với `popleft()` | O(n) | Phù hợp chế độ FIFO |

Dung lượng hàng đợi trong đồ án nhỏ (hiển thị trên GUI) nên chênh lệch thực tế không đáng kể. Danh sách sắp xếp được chọn vì `get_state()` cần thứ tự ưu tiên sẵn có. Cần nhớ rằng phép chèn nằm trong vùng găng (xem mục 5.4).

---

## 3. Mô hình đồng bộ: Monitor

```
mutex      : Lock                       -- bảo vệ _queue, _seq_counter
not_full   : Condition(mutex)           -- chờ khi hàng đợi đầy;  Consumer notify
not_empty  : Condition(mutex)           -- chờ khi hàng đợi rỗng; Producer notify
```

- Hai Condition dùng chung một mutex nhưng chờ hai điều kiện khác nhau, nên mỗi lần chỉ đánh thức đúng loại luồng cần thiết.
- Python thực hiện Monitor kiểu Mesa: sau khi được đánh thức, luồng phải lấy lại mutex và **kiểm tra lại điều kiện**. Vì vậy điều kiện chờ luôn viết bằng `WHILE`, không bao giờ bằng `IF`.

### Quy ước tham số `timeout`

| `timeout` | Hành vi khi điều kiện chưa thỏa | Kết quả trả về |
|---|---|---|
| `0.0` | Không chờ, trả về ngay (non-blocking, dùng cho GUI) | `BLOCKED` |
| `> 0.0` | Chờ tối đa `timeout` giây | Hết hạn: `TIMEOUT` |
| `None` | Chờ vô hạn | Chỉ trả về khi thành công |

Lưu ý: docstring trong `ipc_interface.py` và `shared_memory.py` mô tả trường hợp hết hạn là `BLOCKED`, còn `message_queue.py` trả về `TIMEOUT`. Tài liệu này mô tả đúng theo code hiện tại của `message_queue.py`.

---

## 4. Pseudocode

### 4.1. SEND (produce)

```
PROCEDURE SEND(item, pid, timeout):
    packet   <- NORMALIZE(item, pid)
    deadline <- (timeout = None) ? +INF : now() + timeout

    LOCK(mutex)
    WHILE size(queue) >= capacity DO              -- điều kiện gửi: còn chỗ trống
        IF timeout = 0 THEN
            UNLOCK(mutex)
            RETURN BLOCKED("queue full")
        remaining <- deadline - now()
        IF remaining <= 0 THEN
            UNLOCK(mutex)
            RETURN TIMEOUT
        mark pid as blocked producer
        WAIT(not_full, remaining)                 -- nhả mutex, ngủ; tỉnh dậy phải lấy lại mutex
    END WHILE
    unmark pid as blocked producer                -- code thực hiện trong khối finally

    packet.sequence <- seq_counter
    seq_counter     <- seq_counter + 1

    IF mode = PRIORITY THEN
        i <- chỉ số nhỏ nhất sao cho key(packet) < key(queue[i])
             (nếu không có thì i <- size(queue))
        INSERT(queue, i, packet)
    ELSE
        APPEND(queue, packet)

    NOTIFY(not_empty)                             -- đánh thức đúng 1 Consumer đang chờ
    UNLOCK(mutex)
    RETURN SUCCESS(packet)
```

### 4.2. RECEIVE (consume)

```
PROCEDURE RECEIVE(pid, timeout):
    deadline <- (timeout = None) ? +INF : now() + timeout

    LOCK(mutex)
    WHILE size(queue) = 0 DO                      -- điều kiện nhận: có gói tin
        IF timeout = 0 THEN
            UNLOCK(mutex)
            RETURN BLOCKED("queue empty")
        remaining <- deadline - now()
        IF remaining <= 0 THEN
            UNLOCK(mutex)
            RETURN TIMEOUT
        mark pid as blocked consumer
        WAIT(not_empty, remaining)
    END WHILE
    unmark pid as blocked consumer

    packet <- REMOVE_FIRST(queue)                 -- gói tin ưu tiên cao nhất, vào sớm nhất
    NOTIFY(not_full)                              -- đánh thức đúng 1 Producer đang chờ
    UNLOCK(mutex)
    RETURN SUCCESS(packet)
```

### 4.3. Phương án đối chiếu: Mutex + Semaphore (theo `message_queue_spec.md`)

```
PROCEDURE SEND_SEM(item):                  PROCEDURE RECEIVE_SEM():
    WAIT(empty)        -- chặn nếu đầy         WAIT(full)         -- chặn nếu rỗng
    LOCK(mutex)                                LOCK(mutex)
    chèn theo key(packet)                      packet <- REMOVE_FIRST(queue)
    UNLOCK(mutex)                              UNLOCK(mutex)
    SIGNAL(full)                               SIGNAL(empty)
                                               RETURN packet
```

Semaphore chỉ đếm số chỗ trống và số gói tin, nên việc sắp xếp theo ưu tiên vẫn phải làm trong vùng găng dưới mutex. Điều này không khác với phương án Monitor.

---

## 5. Phân tích

### 5.1. Tính đúng đắn

- **Loại trừ tương hỗ:** mọi truy cập `_queue` và `_seq_counter` đều nằm giữa `LOCK(mutex)` và `UNLOCK(mutex)`. `WAIT` nhả mutex khi ngủ và lấy lại trước khi chạy tiếp.
- **Không tràn, không đọc rỗng:** điều kiện `size < capacity` (gửi) và `size > 0` (nhận) được kiểm tra khi đang giữ mutex, ngay trước khi thay đổi hàng đợi.
- **Không mất tín hiệu đánh thức:** `NOTIFY` luôn được gọi sau khi trạng thái đã đổi và khi vẫn giữ mutex. Dù luồng tỉnh dậy do `notify`, do hết hạn hay do thức giả (spurious wakeup), nó đều kiểm tra lại điều kiện ở đầu vòng `WHILE`, nên không bỏ sót gói tin hoặc chỗ trống.
- **Không deadlock:** thứ tự khóa luôn là `mutex` rồi mới đến khóa trạng thái chẩn đoán (`_state_lock`). `WAIT` chỉ được gọi khi không giữ `_state_lock`.
- **Công bằng trong cùng mức ưu tiên:** nhờ `sequence`, hai gói cùng `priority` luôn ra theo thứ tự vào.

### 5.2. Rủi ro đói tài nguyên (starvation)

Ưu tiên ở đây là của gói tin, không phải của luồng, nên không có đảo ngược ưu tiên (priority inversion) kiểu kinh điển. Tuy nhiên nếu gói ưu tiên cao liên tục được gửi vào, gói ưu tiên thấp có thể bị trì hoãn vô hạn. Hiện chưa có cơ chế aging. Cách khắc phục nếu cần: cứ sau một khoảng thời gian chờ hoặc số lần bị vượt, tăng dần `priority` hiệu dụng của gói tin.

### 5.3. Chi phí chặn (ngắt) và đánh thức

Khi điều kiện chưa thỏa và `timeout` khác 0, luồng không busy-wait mà bị đưa vào trạng thái ngủ. Chi phí chia theo bốn đường đi:

| Đường đi | Việc phải làm | Chi phí chính |
|---|---|---|
| **Nhanh (không chờ)** | Lấy mutex, kiểm tra điều kiện, thao tác, nhả mutex | Một lần lấy/nhả khóa. Không có context switch |
| **Non-blocking (`timeout=0.0`)** | Lấy mutex, thấy điều kiện chưa thỏa, nhả và trả `BLOCKED` | Cũng chỉ một lần lấy/nhả khóa. Phù hợp để GUI thăm dò mỗi tick mà không đóng băng |
| **Chặn (`WAIT`)** | Tạo khóa chờ, đưa vào danh sách chờ của Condition, nhả mutex, ngủ | Gọi hệ thống để ngủ và chuyển ngữ cảnh sang luồng khác (context switch) |
| **Đánh thức (`NOTIFY`)** | Chọn luồng chờ lâu nhất, mở khóa chờ của nó; luồng đó phải lấy lại mutex | Chuyển ngữ cảnh về luồng được đánh thức, tranh chấp mutex, tranh chấp GIL (CPython) |

Các khoản chi phí cụ thể của đường chặn và đánh thức:

1. **Chuyển ngữ cảnh hai chiều:** một lần khi luồng đi ngủ, một lần khi được đánh thức. Đây là khoản lớn nhất, lớn hơn nhiều so với đường nhanh. Con số cụ thể phụ thuộc hệ điều hành và máy, nên cần đo thực nghiệm (xem 5.6).
2. **"Tỉnh dậy rồi lại bị chặn":** `NOTIFY` bắt buộc gọi khi đang giữ mutex (Python báo lỗi nếu gọi khi không giữ). Luồng được đánh thức có thể chạy trước khi luồng gọi `NOTIFY` kịp `UNLOCK`, nên nó lại bị chặn ở mutex trong chốc lát và tốn thêm một lần chuyển ngữ cảnh.
3. **Tranh chấp mutex và chen ngang (barging):** giữa lúc `NOTIFY` và lúc luồng được đánh thức lấy lại được mutex, một luồng khác vừa đến có thể chen vào lấy mất gói tin hoặc chỗ trống. Luồng vừa tỉnh thấy điều kiện sai, quay lại ngủ, mất công đánh thức vô ích. Đây là lý do cần vòng `WHILE`.
4. **Thức giả (spurious wakeup):** luồng có thể tỉnh dậy mà không có `notify` nào. Chi phí chỉ là một lần kiểm tra lại điều kiện, nhưng buộc phải xử lý bằng `WHILE`.
5. **Hết hạn (`timeout > 0`):** thêm chi phí đọc đồng hồ và tính thời gian còn lại ở mỗi vòng. Nên dùng `time.monotonic()` thay cho `time.time()` để không bị ảnh hưởng khi đồng hồ hệ thống bị chỉnh.

### 5.4. Ảnh hưởng của cấu trúc dữ liệu lên độ trễ đánh thức

Luồng được đánh thức phải chờ mutex được nhả. Thời gian giữ mutex càng dài thì độ trễ này càng lớn. Ở chế độ Priority, phép chèn O(n) và `pop(0)` O(n) nằm trong vùng găng, nên chi phí cấu trúc dữ liệu cộng thẳng vào độ trễ của các luồng khác. Với dung lượng nhỏ thì không đáng kể, nhưng khi tăng dung lượng thì `heapq` (chèn/lấy O(log n)) hoặc `deque` (FIFO) sẽ có lợi hơn.

### 5.5. `notify()` hay `notify_all()`, và lý do dùng hai Condition

- Code dùng `notify()`: mỗi thao tác chỉ đánh thức tối đa một luồng, nên chi phí đánh thức là O(1) cho mỗi thao tác.
- `notify_all()` đánh thức mọi luồng đang chờ (k luồng) nhưng chỉ một luồng làm được việc, k − 1 luồng còn lại lại ngủ tiếp. Đây là hiện tượng thundering herd. `notify_all()` chỉ dùng trong `reset()` (hiếm gặp và cần thiết).
- Nếu chỉ dùng **một** Condition cho cả hai điều kiện thì `notify()` có thể đánh thức nhầm loại luồng (Producer đánh thức Producer khác) và gây mất tín hiệu, buộc phải chuyển sang `notify_all()`. Tách thành `not_full` và `not_empty` giúp mỗi tín hiệu đến đúng đối tượng.

### 5.6. So sánh với Mutex + Semaphore

| Tiêu chí | Monitor (`message_queue.py`) | Mutex + 2 Semaphore (`shared_memory.py`) |
|---|---|---|
| Số lần lấy/nhả khóa cho mỗi thao tác | 1 mutex | `threading.Semaphore` của Python tự dùng một Condition bên trong, nên mỗi thao tác chạm tới khóa của semaphore thứ nhất, mutex, rồi khóa của semaphore thứ hai |
| Điều kiện chờ | Viết tùy ý trong `WHILE` | Cố định là đếm chỗ trống/gói tin |
| Đánh thức | Qua `Condition.notify` | Qua `Semaphore.release` |
| Xử lý thức giả, chen ngang | Tự xử lý bằng `WHILE` | Semaphore tự xử lý |

Theo đó phương án Monitor có xu hướng ít thao tác đồng bộ hơn cho mỗi gói tin. Đây là nhận định từ cách thư viện hiện thực, cần xác nhận bằng đo thực nghiệm.

---

## 6. Hạn chế đã biết và hướng cải tiến

1. Quy ước trạng thái khi hết `timeout > 0` (`TIMEOUT` ở Message Queue so với `BLOCKED` ở Shared Memory và docstring interface) cần được nhóm thống nhất.
2. Ở chế độ non-blocking (`timeout=0.0`), tiến trình bị chặn không được ghi vào `blocked_processes`, nên GUI không hiển thị được tiến trình đang bị chặn khi chạy từng bước.
3. `_normalize_packet` với đầu vào `dict` chưa chuyển `simulate_error` và `mechanism` vào gói tin.
4. Chưa có cơ chế aging chống đói gói tin ưu tiên thấp.
5. Dùng `time.monotonic()` thay cho `time.time()` trong tính thời gian chờ.
6. Ở chế độ FIFO có thể dùng `deque`; khi dung lượng lớn có thể cân nhắc `heapq` cho chế độ Priority.
