# ĐẶC TẢ KỸ THUẬT: MODULE SHARED MEMORY (BOUNDED BUFFER IPC)

> **Mã nhiệm vụ Jira:** `HDH-10` (Soạn đặc tả) & `HDH-24` (Hiện thực luồng lõi)  
> **Cơ chế IPC:** Vùng nhớ chia sẻ (Shared Memory)  
> **Mô hình:** Bounded Buffer (Bài toán Nhà sản xuất - Người tiêu thụ / Producer - Consumer)  
> **Nền tảng mục tiêu:** Python 3.10+, Desktop GUI PyQt6  

---

## 1. Tổng quan & Mục tiêu thiết kế

Module `SharedMemory` hiện thực cơ chế truyền thông liên tiến trình (IPC) qua vùng nhớ chia sẻ, mô phỏng quá trình trao đổi dữ liệu tốc độ cao giữa nhiều tiến trình **Producer** và **Consumer**.

### Mục tiêu kiến trúc:
1. **Độc lập hoàn toàn khỏi Giao diện (Decoupled Core):** Tầng logic cốt lõi không phụ thuộc vào bất kỳ thư viện UI nào, cho phép kiểm thử độc lập qua Console script hoặc Unit test.
2. **Không gây treo UI (Non-blocking Thread Safety):** Tuyệt đối loại trừ vòng lặp vô tận `while True` hoặc lệnh chờ chặn vô hạn (`wait` blocking) trên luồng chính của PyQt6. Hỗ trợ cơ chế `timeout` và `try_acquire` (non-blocking) trả về cờ `BLOCKED` tức thì.
3. **An toàn đồng bộ hóa (Race-free & Deadlock-free):** Sử dụng chuẩn các nguyên thủy đồng bộ hoá của Hệ điều hành (`threading.Semaphore` và `threading.Lock`) tuân thủ nghiêm ngặt thứ tự Wait/Signal.

---

## 2. Cấu trúc dữ liệu (Data Structures)

### 2.1. Mảng vòng (Circular Buffer)
Dữ liệu được tổ chức dưới dạng một mảng một chiều có kích thước cố định $N = \text{capacity}$. Hai con trỏ số nguyên điều hướng tuần hoàn trên mảng:

```
                  in_ptr (Ghi tiếp theo)
                        │
                        ▼
    ┌──────────┬──────────┬──────────┬──────────┐
    │  Slot 0  │  Slot 1  │  Slot 2  │  Slot 3  │   (Capacity = 4)
    └──────────┴──────────┴──────────┴──────────┘
                        ▲
                        │
                  out_ptr (Đọc tiếp theo)
```

- `buffer: list[Any | None]`: Mảng chứa dữ liệu các ô nhớ (khởi tạo `[None] * capacity`).
- `in_ptr: int`: Chỉ số ô nhớ Producer sẽ ghi dữ liệu ở bước tiếp theo ($0 \le \text{in\_ptr} < \text{capacity}$).
- `out_ptr: int`: Chỉ số ô nhớ Consumer sẽ đọc dữ liệu ở bước tiếp theo ($0 \le \text{out\_ptr} < \text{capacity}$).
- `count: int`: Số lượng ô nhớ đang chứa dữ liệu thực tế ($0 \le \text{count} \le \text{capacity}$).

**Quy tắc tịnh tiến con trỏ tuần hoàn (Modulo Arithmetic):**
$$\text{in\_ptr} = (\text{in\_ptr} + 1) \pmod{\text{capacity}}$$
$$\text{out\_ptr} = (\text{out\_ptr} + 1) \pmod{\text{capacity}}$$

### 2.2. Cấu trúc dữ liệu trạng thái phục vụ GUI (`get_state`)
Hàm `get_state()` cung cấp một bản chụp (snapshot) an toàn luồng với lược đồ (schema) sau:

| Tên trường (Key) | Kiểu dữ liệu | Ý nghĩa kỹ thuật |
| :--- | :--- | :--- |
| `buffer` | `list[Any]` | Bản sao mảng dữ liệu hiện tại (các ô trống mang giá trị `None`). |
| `in_ptr` | `int` | Vị trí con trỏ ghi tiếp theo của Producer. |
| `out_ptr` | `int` | Vị trí con trỏ đọc tiếp theo của Consumer. |
| `mutex` | `int` | Trạng thái khóa Mutex: `1` (Rảnh - Unlocked), `0` (Bận - Locked). |
| `empty` | `int` | Giá trị Semaphore `empty` (Số ô trống khả dụng: $\text{capacity} - \text{count}$). |
| `full` | `int` | Giá trị Semaphore `full` (Số ô có dữ liệu khả dụng: $\text{count}$). |
| `blocked_processes` | `list[str]` | Danh sách tên/ID các tiến trình hiện đang bị nghẽn (Wait). |
| `capacity` | `int` | Sức chứa tối đa của bộ đệm. |
| `count` | `int` | Số phần tử hiện có trong buffer. |

---

## 3. Định nghĩa các biến đồng bộ (Synchronization Primitives)

Để giải quyết triệt để vấn đề tranh chấp bộ nhớ (Race Condition) và đồng bộ giữa tiến trình nhanh/chậm, hệ thống sử dụng 3 nguyên thủy đồng bộ:

| Tên biến | Kiểu nguyên thủy | Giá trị khởi tạo | Vai trò & Ý nghĩa kỹ thuật |
| :--- | :--- | :---: | :--- |
| `mutex` | Binary Semaphore / Lock | `1` | **Loại trừ tương hỗ (Mutual Exclusion):** Bảo vệ đoạn găng (Critical Section). Đảm bảo tại một thời điểm chỉ có DUY NHẤT một tiến trình được phép ghi hoặc đọc vào `buffer`, cập nhật `in_ptr`, `out_ptr` và `count`. |
| `empty` | Counting Semaphore | `capacity` | **Đếm ô nhớ trống:** Báo hiệu số lượng vị trí còn trống trong bộ đệm. Khi $\text{empty} = 0$, bộ đệm đã **ĐẦY**; mọi Producer muốn ghi thêm đều bị chuyển sang trạng thái **BLOCKED**. |
| `full` | Counting Semaphore | `0` | **Đếm ô nhớ có dữ liệu:** Báo hiệu số lượng vị trí đã có dữ liệu sẵn sàng để đọc. Khi $\text{full} = 0$, bộ đệm đang **RỖNG**; mọi Consumer muốn đọc đều bị chuyển sang trạng thái **BLOCKED**. |

### Bất biến toán học của hệ thống (System Invariants)
Tại mọi thời điểm nằm ngoài Critical Section, hệ thống luôn thỏa mãn:
1. $\text{empty} + \text{full} = \text{capacity}$
2. $0 \le \text{count} \le \text{capacity}$
3. $\text{mutex} \in \{0, 1\}$

---

## 4. Mã giả giải thuật (Pseudocode)

### 4.1. Thuật toán Producer (Nhà sản xuất)

```text
Algorithm Producer(item):
    // BƯỚC 1: Chờ và chiếm dụng 1 ô nhớ trống (Wait on Counting Semaphore)
    wait(empty)

    // BƯỚC 2: Vào đoạn găng (Critical Section)
    wait(mutex)

    // --- CRITICAL SECTION BẮT ĐẦU ---
    buffer[in_ptr] = item
    in_ptr = (in_ptr + 1) mod capacity
    count = count + 1
    // --- CRITICAL SECTION KẾT THÚC ---

    // BƯỚC 3: Rời khỏi đoạn găng (Signal Binary Semaphore)
    signal(mutex)

    // BƯỚC 4: Báo hiệu đã có thêm 1 ô dữ liệu sẵn sàng cho Consumer
    signal(full)
```

### 4.2. Thuật toán Consumer (Người tiêu thụ)

```text
Algorithm Consumer():
    // BƯỚC 1: Chờ và chiếm dụng 1 ô có dữ liệu (Wait on Counting Semaphore)
    wait(full)

    // BƯỚC 2: Vào đoạn găng (Critical Section)
    wait(mutex)

    // --- CRITICAL SECTION BẮT ĐẦU ---
    item = buffer[out_ptr]
    buffer[out_ptr] = NULL          // Dọn dẹp ô nhớ sau khi đọc
    out_ptr = (out_ptr + 1) mod capacity
    count = count - 1
    // --- CRITICAL SECTION KẾT THÚC ---

    // BƯỚC 3: Rời khỏi đoạn găng (Signal Binary Semaphore)
    signal(mutex)

    // BƯỚC 4: Báo hiệu đã giải phóng 1 ô trống cho Producer
    signal(empty)

    return item
```

### 4.3. Phân tích phòng chống Deadlock (Nguyên tắc thứ tự khóa)

> [!CAUTION]
> **CẢNH BÁO NGUY CƠ DEADLOCK KINH ĐIỂN:**  
> Tuyệt đối **KHÔNG ĐƯỢC ĐẢO THỨ TỰ** `wait(mutex)` lên trước `wait(empty)` hoặc `wait(full)`.

**Kịch bản gây Deadlock nếu đảo thứ tự:**
1. Giả sử Producer thực hiện: `wait(mutex)` trước rồi mới gọi `wait(empty)`.
2. Khi bộ đệm đầy ($\text{empty} = 0$), Producer chiếm được `mutex` thành công ($\text{mutex} = 0$), sau đó bị block tại `wait(empty)`.
3. Lúc này, Producer đang **nắm giữ `mutex` trong khi đi ngủ**.
4. Consumer muốn tiêu thụ dữ liệu để giải phóng ô nhớ phải gọi `wait(mutex)`. Nhưng vì `mutex` đang bị Producer nắm giữ, Consumer cũng bị **block tại `mutex`**.
5. **Hậu quả:** Producer chờ Consumer gọi `signal(empty)`, còn Consumer chờ Producer gọi `signal(mutex)`. Hệ thống rơi vào trạng thái bế tắc vĩnh viễn (**Deadlock**).

**Kết luận:** Thứ tự bắt buộc là: `wait(counting_semaphore)` $\rightarrow$ `wait(mutex)` $\rightarrow$ thao tác dữ liệu $\rightarrow$ `signal(mutex)` $\rightarrow$ `signal(counting_semaphore)`.

---

## 5. Thiết kế Non-blocking phục vụ Desktop GUI

Để ứng dụng Desktop GUI (PyQt6) luôn đạt độ phản hồi mượt mà (60 FPS) và không bao giờ xuất hiện lỗi Windows "Not Responding":

```
[GUI Ticker / QTimer / Button Step]
                │
                ▼ (timeout = 0.0)
     try_acquire(Semaphore)
        ┌───────┴───────┐
   [Thành công]    [Thất bại (Buffer Full/Empty)]
        │               │
  Vào Mutex             Không ngủ (No Sleep / No while)
  Ghi / Đọc Buffer      Ghi nhận Process vào `blocked_processes`
  Signal Semaphore      Trả về ngay: `IPCResult(status="BLOCKED")`
        │               │
        └───────┬───────┘
                ▼
      Cập nhật State GUI
      Vẽ Canvas Animation
```

1. **Thực thi Non-blocking:** Khi GUI gọi `produce()` hoặc `consume()` với `timeout=0.0`, tầng lõi sử dụng `semaphore.acquire(blocking=False)`.
2. **Bắt cờ `BLOCKED`:** Nếu thao tác không thể hoàn tất (Buffer đầy/rỗng), hàm trả về ngay đối tượng `IPCResult(status="BLOCKED")` trong thời gian $O(1)$.
3. **Cập nhật giao diện trực quan:** Danh sách `blocked_processes` được cập nhật tức thời để GUI tô màu đỏ các tiến trình đang bị nghẽn trên Canvas đồ họa.

---

## 6. Ma trận đối soát trạng thái kiểm chứng (Oracle Verification)

| Trạng thái bộ đệm | Điều kiện $count$ | Semaphore $empty$ | Semaphore $full$ | Hành vi Producer | Hành vi Consumer |
| :--- | :---: | :---: | :---: | :--- | :--- |
| **Rỗng (Empty)** | $0$ | $\text{capacity}$ | $0$ | Ghi ngay không nghẽn | Bị **BLOCKED** tại Semaphore `full` |
| **Một phần (Normal)** | $0 < \text{count} < \text{capacity}$ | $\text{capacity} - \text{count}$ | $\text{count}$ | Ghi ngay không nghẽn | Đọc ngay không nghẽn |
| **Đầy (Full)** | $\text{capacity}$ | $0$ | $\text{capacity}$ | Bị **BLOCKED** tại Semaphore `empty` | Đọc ngay không nghẽn |
| **Tranh chấp (Contention)** | Bất kỳ | $> 0$ | $> 0$ | Một tiến trình giữ `mutex`, tiến trình kia xếp hàng chờ |
