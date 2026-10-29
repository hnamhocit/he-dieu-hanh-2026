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

---

## Kịch bản 4: Test biên - Đẩy gói tin vào bộ đệm cấu hình cực tiểu (Buffer Size = 1)
* **Mô tả:** Hệ thống được cấu hình giới hạn dung lượng tối thiểu là 1 ô trống (`capacity = 1`). Tiến trình sản xuất (P) ghi tin `M1`. Ngay sau đó, P cố tình nhồi nhét tiếp tin `M2` khi bộ đệm chưa được giải phóng nhằm kiểm tra khả năng phòng vệ tràn vùng nhớ đệm.

| Bước | Hành động | Trạng thái Buffer | Con trỏ `in` / `out` | Biến Semaphore `(mutex, empty, full)` | Có ai bị nghẽn (Blocked) không? | Giải thích chi tiết từng bước |
| :---: | :--- | :---: | :---: | :---: | :---: | :--- |
| 0 | Ban đầu | `[-]` | `in=0, out=0` | `(1, 1, 0)` | Không | Bộ đệm cấu hình cực tiểu với dung lượng tối đa là 1 ô trống, hiện tại đang rỗng. |
| 1 | P ghi tin `M1` | `[M1]` | **`in=0`, `out=0`** | **`(1, 0, 1)`** | Không | P vào thấy `empty = 1`, giảm xuống 0. Ghi dữ liệu `M1` vào ô số 0. Con trỏ `in` dịch vòng `(0+1)%1 = 0`. Tăng `full` lên 1. Bộ đệm chính thức **ĐẦY**. |
| 2 | P cố ghi tiếp `M2` | `[M1]` | `in=0, out=0` | **`(1, 0, 1)`** | **P bị chặn ngay lập tức (Blocked)** | P gọi hàm với `timeout=0.0`. Hệ thống chạy lệnh `try_acquire` trên Semaphore `empty`. Vì `empty = 0`, hàm thất bại, không block luồng GUI mà trả về cờ từ chối an toàn, bảo vệ nguyên vẹn gói dữ liệu `M1`. |

**Kết quả kỳ vọng:** Bộ đệm dung lượng 1 nhận gói tin đầu tiên thành công và kích hoạt cơ chế phòng vệ chặn đứng gói tin thứ 2 lịch sự (trả về trạng thái `BLOCKED`).

---

### Kịch bản 5: Test biên - Tải trọng gói tin truyền nhận bị trống (Payload rỗng)
* **Mô tả:** Tiến trình sản xuất (P) truyền đi một gói tin điều khiển trạng thái hệ thống (ví dụ: Keep-Alive hoặc Ping) có phần Header đầy đủ nhưng nội dung tin nhắn bên trong bị trống rỗng hoàn toàn (`message = ""`).

| Bước | Hành động | Trạng thái Buffer | Con trỏ `in` / `out` | Biến Semaphore `(mutex, empty, full)` | Có ai bị nghẽn (Blocked) không? | Giải thích chi tiết từng bước |
| :---: | :--- | :---: | :---: | :---: | :---: | :--- |
| 0 | Ban đầu | `[-, -, -, -]` | `in=0, out=0` | `(1, 4, 0)` | Không | Bộ đệm quay về cấu hình chuẩn 4 ô trống và đang ở trạng thái trống rỗng. |
| 1 | P ghi tin rỗng `""` | `["", -, -, -]` | **`in=1`, `out=0`** | **`(1, 3, 1)`** | Không | Tầng Core kiểm tra thấy chuỗi rỗng hợp lệ, tiến hành lệnh `wait(empty)`. Ghi chuỗi kí tự độ dài bằng 0 byte vào ô số 0 an toàn mà không làm gãy/nứt cấu trúc vùng đệm. |
| 2 | C vào đọc dữ liệu | `[-, -, -, -]` | `in=1`, **`out=1`** | **`(1, 4, 0)`** | Không | Consumer thấy `full = 1` nên vào lấy chuỗi rỗng ra xử lý logic bình thường, giải phóng ô nhớ số 0 quay về trạng thái ban đầu sạch sẽ. |

**Kết quả kỳ vọng:** Hệ thống xử lý mượt mà, cấp phát bộ nhớ an toàn và tuyệt đối không phát sinh lỗi con trỏ Null (`Null Pointer Exception`).

---

### Kịch bản 6: Test biên - Tải trọng chạm ngưỡng giới hạn cực đại (Maximum Payload = 100 bytes)
* **Mô tả:** Hệ thống quy định giới hạn kích thước nội dung tin nhắn tối đa được phép đi qua vùng nhớ chung Shared Memory là 100 ký tự. Tiến trình sản xuất (P) thực hiện truyền một gói tin có nội dung dài vừa khít đúng 100 ký tự `X`.

| Bước | Hành động | Trạng thái Buffer | Con trỏ `in` / `out` | Biến Semaphore `(mutex, empty, full)` | Có ai bị nghẽn (Blocked) không? | Giải thích chi tiết từng bước |
| :---: | :--- | :---: | :---: | :---: | :---: | :--- |
| 0 | Ban đầu | `[-, -, -, -]` | `in=0, out=0` | `(1, 4, 0)` | Không | Bộ đệm đang trống rỗng hoàn toàn. |
| 1 | P ghi tin 100 ký tự | `[M_max, -, -, -]` | **`in=1`, `out=0`** | **`(1, 3, 1)`** | Không | Hệ thống đo độ dài chuỗi `len == 100` (nằm chính xác trên vạch biên giới hạn cho phép). Gói tin chạm đỉnh `M_max` được nạp toàn vẹn vào ô số 0, không xảy ra lỗi cắt cụt dữ liệu. |

**Kết quả kỳ vọng:** Gói tin nằm ngay ở vạch biên cực đại được hệ thống cấp phát đủ dung lượng bộ nhớ và thực thi truyền nhận thành công (`SUCCESS`).

---

### Kịch bản 7: Test biên - Chặn gói tin vi phạm vượt ngưỡng cực đại (Payload vượt biên = 101 bytes)
* **Mô tả:** Tiến trình sản xuất (P) cố tình truyền một gói tin có nội dung dài 101 ký tự `X` nhằm kiểm tra chức năng phòng vệ phòng ngừa nguy cơ tấn công tràn bộ đệm dữ liệu thô của hệ thống.

| Bước | Hành động | Trạng thái Buffer | Con trỏ `in` / `out` | Biến Semaphore `(mutex, empty, full)` | Có ai bị nghẽn (Blocked) không? | Giải thích chi tiết từng bước |
| :---: | :--- | :---: | :---: | :---: | :---: | :--- |
| 0 | Ban đầu | `[-, -, -, -]` | `in=0, out=0` | `(1, 4, 0)` | Không | Bộ đệm đang trống rỗng. |
| 1 | P ghi tin 101 ký tự | `[-, -, -, -]` | `in=0, out=0` | **`(1, 4, 0)`** | Không | Ngay khi nhận lệnh, tầng bảo vệ Guard quét thấy độ dài chuỗi `101 > 100` (vi phạm biên trên). Hệ thống **từ chối ngay từ cổng vào**, chặn đứng không cho phép gọi lệnh nạp vào ô đệm chia sẻ thô để đảm bảo an toàn bộ nhớ. |

**Kết quả kỳ vọng:** Hệ thống phát hiện vi phạm biên cực đại, chặn ghi dữ liệu lọt lưới thành công, các biến trạng thái và vị trí con trỏ giữ nguyên vẹn.

---

### Kịch bản 8: Biên trùng độ ưu tiên - Định tuyến hàng đợi cạnh tranh (Duplicate Priority)
* **Mô tả:** Hai tiến trình cùng sản xuất dữ liệu ghi liên tiếp 2 gói tin có mức độ ưu tiên bằng nhau (`Priority = 5`) là `Tin_1` (vào trước lúc $t_1$) và `Tin_2` (vào sau lúc $t_2$). Sau đó luồng Consumer tiến hành lấy dữ liệu ra khỏi bộ đệm chia sẻ.

| Bước | Hành động | Trạng thái Buffer | Con trỏ `in` / `out` | Biến Semaphore `(mutex, empty, full)` | Có ai bị nghẽn (Blocked) không? | Giải thích chi tiết từng bước |
| :---: | :--- | :---: | :---: | :---: | :---: | :--- |
| 0 | Ban đầu | `[-, -, -, -]` | `in=0, out=0` | `(1, 4, 0)` | Không | Bộ đệm đang trống rỗng. |
| 1 | P ghi `Tin_1` (P5) | `[Tin_1, -, -, -]` | **`in=1`, `out=0`** | **`(1, 3, 1)`** | Không | `Tin_1` chui vào chiếm ô số 0 trước. Biến con trỏ `in` tăng định tiến lên vị trí số 1. |
| 2 | P ghi tiếp `Tin_2` (P5)| `[Tin_1, Tin_2, -, -]`| **`in=2`, `out=0`** | **`(1, 2, 2)`** | Không | Do trùng priority, thuật toán mảng vòng xếp `Tin_2` nằm tuần tự ngay sau ở ô nhớ số 1. Biến con trỏ `in` tăng lên vị trí số 2. |
| 3 | C vào rút dữ liệu tin | `[-, Tin_2, -, -]` | `in=2`, **`out=1`** | **`(1, 3, 1)`** | Không | Con trỏ đọc `out` dịch tiến theo mảng vòng tuần tự bắt đầu từ ô số 0 $\rightarrow$ Lấy trúng chính xác **`Tin_1`** ra trước. Đây chính là việc áp dụng quy luật phụ **FIFO (vào trước ra trước)** khi gặp trường hợp trùng độ ưu tiên. |

**Kết quả kỳ vọng:** Hệ thống giải quyết tranh chấp lập lịch trơn tru, nhận dữ liệu ra theo đúng trình tự thời gian bấm chuông xếp hàng (`Tin_1` xuất xưởng trước, `Tin_2` xuất xưởng sau).
