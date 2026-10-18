## Bảng tính tay (Oracle) cho 3 kịch bản kiểm thử mẫu

Để kiểm tra xem code chạy có đúng không, nhóm em tiến hành tính tay trước trạng thái của bộ đệm (Buffer) và các biến khóa (Mutex/Semaphore) qua từng bước chạy. 

### Cấu hình giả định:
* Bộ đệm có **4 ô trống** (Buffer size = 4). Ban đầu chưa có dữ liệu `[-, -, -, -]`.
* Con trỏ ghi `in = 0`, con trỏ đọc `out = 0`.
* Khóa **mutex = 1** (ai vào vùng nhớ thì khóa lại = 0, ra thì mở = 1).
* Biến đếm ô trống **empty = 4**, biến đếm ô có dữ liệu **full = 0**.

---

### Kịch bản 1: Đọc và Ghi bình thường (Không có tranh chấp)
* **Mô tả:** Tiến trình sản xuất (P) ghi liên tiếp 2 tin là `M1` và `M2`. Sau đó tiến trình tiêu thụ (C) đọc liên tiếp 2 tin đó ra xem có đúng thứ tự trước sau không.

| Bước | Hành động | Trạng thái Buffer | Con trỏ `in` / `out` | Biến Semaphore `(mutex, empty, full)` | Có ai bị nghẽn (Blocked) không? | Giải thích chi tiết từng bước |
| :---: | :--- | :---: | :---: | :---: | :---: | :--- |
| 0 | Ban đầu | `[-, -, -, -]` | `in=0, out=0` | `(1, 4, 0)` | Không | Hệ thống mới bật, chưa có gì bên trong. |
| 1 | P ghi tin `M1` | `[M1, -, -, -]` | **`in=1`, `out=0`** | **`(1, 3, 1)`** | Không | P vào giảm `empty` xuống 3, giữ `mutex`. Ghi `M1` vào ô 0 xong tăng `full` lên 1, nhả `mutex`. |
| 2 | P ghi tiếp tin `M2` | `[M1, M2, -, -]` | **`in=2`, `out=0`** | **`(1, 2, 2)`** | Không | Tương tự bước 1, `empty` giảm còn 2, `full` tăng lên 2. `M2` nằm ở ô số 1. |
| 3 | C vào đọc | `[-, M2, -, -]` | `in=2`, **`out=1`** | **`(1, 3, 1)`** | Không | C thấy `full > 0` nên vào lấy `M1` ở ô 0 ra. `empty` tăng lại thành 3, `full` giảm còn 1. |
| 4 | C đọc tiếp | `[-, -, -, -]` | `in=2`, **`out=2`** | **`(1, 4, 0)`** | Không | C lấy nốt `M2` ở ô 1 ra. Bộ đệm rỗng, các biến quay về y như lúc đầu. |

**Kết quả kỳ vọng:** Nhận đủ 2 tin theo đúng thứ tự `M1` trước, `M2` sau (chuẩn FIFO).

---

### Kịch bản 2: Test biên - Consumer vào đọc khi bộ đệm đang rỗng (Underflow)
* **Mô tả:** Bộ đệm đang hết sạch dữ liệu nhưng ông Consumer (`C1`) lại đòi vào đọc tin. Một lúc sau ông Producer (`P1`) mới vào cứu viện bằng cách ghi tin `M1`.

| Bước | Hành động | Trạng thái Buffer | Con trỏ `in` / `out` | Biến Semaphore `(mutex, empty, full)` | Có ai bị nghẽn (Blocked) không? | Giải thích chi tiết từng bước |
| :---: | :--- | :---: | :---: | :---: | :---: | :--- |
| 0 | Ban đầu | `[-, -, -, -]` | `in=0, out=0` | `(1, 4, 0)` | Không | Bộ đệm đang trống rỗng. |
| 1 | `C1` vào đọc | `[-, -, -, -]` | `in=0, out=0` | **`(1, 4, -1)`** | **`C1` bị đứng im (Blocked)** | `C1` chạy lệnh thấy `full = 0` nên khi giảm xuống sẽ thành **-1**. `C1` bị treo luồng, phải xếp hàng chờ ở hàng đợi. |
| 2 | `P1` ghi tin `M1` | `[M1, -, -, -]` | **`in=1`, `out=0`** | **`(1, 3, 0)`** | Không | `P1` vào ghi `M1` vào ô 0 bình thường. Khi `P1` tăng `full` từ -1 lên **0** \(\rightarrow\) Hệ thống tự động gọi `C1` thức dậy. |
| 3 | `C1` tỉnh dậy đọc | `[-, -, -, -]` | `in=1`, **`out=1`** | **`(1, 4, 0)`** | Không | `C1` tiếp tục chạy nốt đoạn lệnh đang dở, lấy `M1` ra rồi giải phóng bộ đệm an toàn. |

**Kết quả kỳ vọng:** Hệ thống từ chối an toàn, treo `C1` lại chứ không bị sập hay treo đơ toàn bộ chương trình (trả về cờ `BLOCKED`).

---

### Kịch bản 3: Tranh chấp biên - Producer cố ghi khi bộ đệm đã đầy (Overflow)
* **Mô tả:** Bộ đệm của nhóm cấu hình là 4 ô. Hiện tại các bạn đã ghi đầy 3 ô rồi. Ông Producer cố tình nhồi nhét thêm 2 tin nữa là `M4` và `M5` xem hệ thống xử lý thế nào.

| Bước | Hành động | Trạng thái Buffer | Con trỏ `in` / `out` | Biến Semaphore `(mutex, empty, full)` | Có ai bị nghẽn (Blocked) không? | Giải thích chi tiết từng bước |
| :---: | :--- | :---: | :---: | :---: | :---: | :--- |
| 0 | Ban đầu | `[M1, M2, M3, -]` | `in=3, out=0` | `(1, 1, 3)` | Không | Đã đầy 3 ô, còn đúng 1 ô trống cuối cùng ở vị trí số 3. |
| 1 | P ghi tin `M4` | `[M1, M2, M3, M4]` | **`in=0`, `out=0`** | **`(1, 0, 4)`** | Không | P ghi nốt `M4` vào ô số 3. Bộ đệm chính thức **đầy 4/4**. Con trỏ `in` xoay vòng về lại ô số 0. |
| 2 | P cố ghi tiếp `M5` | `[M1, M2, M3, M4]` | `in=0, out=0` | **`(1, -1, 4)`** | **Producer bị chặn (Blocked)** | P lại đòi ghi tiếp nhưng lúc này `empty = 0`. Khi giảm xuống sẽ thành **-1**. P bị khóa chân lại ngay lập tức, không cho ghi đè để bảo vệ 4 tin cũ. |

**Kết quả kỳ vọng:** Hệ thống chặn đứng ông Producer lại khi bộ đệm đầy 4/4 (báo trạng thái `is_blocked = True`), bảo vệ dữ liệu cũ không bị ghi đè lung tung.