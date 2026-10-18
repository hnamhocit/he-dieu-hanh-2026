# Mô Phỏng & Hiện Thực Trao Đổi Dữ Liệu Giữa Process (IPC)

> **Môn học:** Hệ điều hành  
> **Đề tài:** Mô phỏng hoặc hiện thực trao đổi dữ liệu giữa process bằng **Shared Memory**, **Pipe** hoặc **Message Queue**; có trace và xử lý lỗi.  
> **Nền tảng mục tiêu:** Desktop GUI (Windows / Cross-platform)

---

## 📌 Mục lục
- [1. Hướng dẫn cài đặt & Khởi chạy nhanh (Quick Start)](#1-hướng-dẫn-cài-đặt--khởi-chạy-nhanh-quick-start)
- [2. Hướng dẫn kiểm thử (Testing)](#2-hướng-dẫn-kiểm-thử-testing)
- [3. Tổng quan đề tài & Yêu cầu kỹ thuật](#3-tổng-quan-đề-tài--yêu-cầu-kỹ-thuật)
- [4. Công nghệ (Tech Stack) & Cấu trúc thư mục](#4-công-nghệ-tech-stack--cấu-trúc-thư-mục)
- [5. Thiết kế kiến trúc & Tính năng cốt lõi](#5-thiết-kế-kiến-trúc--tính-năng-cốt-lõi)
- [6. Định dạng dữ liệu I/O (CSV Specification)](#6-định-dạng-dữ-liệu-io-csv-specification)
- [7. Tính đúng & Phương pháp Oracle (Verification)](#7-tính-đúng--phương-pháp-oracle-verification)
- [8. Đo lường & Benchmark hiệu năng](#8-đo-lường--benchmark-hiệu-năng)
- [9. Quy trình làm việc nhóm (Workflow)](#9-quy-trình-làm-việc-nhóm-workflow)

---

## 1. Hướng dẫn cài đặt & Khởi chạy nhanh (Quick Start)

### 1.1. Yêu cầu tiên quyết
- **Hệ điều hành:** Windows 10/11 (hoặc Linux / macOS)
- **Python:** Phiên bản **3.11+** (hoặc tối thiểu 3.10+)
- **Git:** Quản lý mã nguồn

### 1.2. Các bước cài đặt môi trường
1. **Clone repository:**
   ```bash
   git clone git@github.com:hnamhocit/he-dieu-hanh-2026.git
   cd he-dieu-hanh-2026
   ```

2. **Khởi tạo và kích hoạt môi trường ảo (Virtual Environment):**
   - Trên Windows:
     ```cmd
     python -m venv venv
     .\venv\Scripts\activate
     ```
   - Trên Linux / macOS:
     ```bash
     python3 -m venv venv
     source venv/bin/activate
     ```

3. **Cài đặt các thư viện phụ thuộc:**
   ```bash
   pip install -r requirements.txt
   ```

### 1.3. Khởi chạy ứng dụng GUI
```bash
python src/main.py
```
Giao diện HDH-32 được bố trí theo wireframe: **CSV Input**, **Cấu hình tham số**,
**Buffer Visualization** và **Trace Log**.

![Giao diện chính HDH-32](docs/hdh32_main_window.png)

1. Nhấn **Chọn file**, chọn CSV trong `data/input`.
2. Nhấn **Kiểm tra**. File được đọc ở luồng nền; lỗi được hiển thị kèm mã lỗi.
3. Khi CSV hợp lệ, chọn cơ chế IPC, dung lượng Buffer, số Producer/Consumer.
4. Thử **Start → Pause → Tiếp tục → Reset**. Reset giữ nguyên CSV đã kiểm tra.

Giao diện dùng `CSVParser` đã có trên `main`, không phụ thuộc nhánh HDH-31.
Các lỗi kiểm tra dữ liệu hiển thị mã `INVALID_DATA` kèm lý do; lỗi đọc file
hiển thị `FILE_READ_ERROR`, lỗi cú pháp CSV hiển thị `INVALID_CSV`.

Đây là bản dựng layout, **chưa thực thi mô phỏng IPC**. Các nút phát tín hiệu
`start_requested(messages, configuration)`, `pause_requested()`,
`resume_requested()` và `reset_requested()` để kết nối bộ chạy riêng.
Buffer, biểu đồ và thống kê ban đầu chưa có dữ liệu mô phỏng; bảng trace rỗng.
Bộ chạy có thể gửi log qua `MainWindow.append_trace(values)` trên UI thread;
nút xuất CSV chỉ bật khi có log. Giao diện không sinh số liệu minh họa giả.

Cũng có thể khởi chạy bằng `python -m src.main`. Cần cài PyQt6 theo
`requirements.txt`. Kiểm thử gồm GUI offscreen: `python -m unittest discover -s tests`.

---

## 2. Hướng dẫn kiểm thử (Testing)

Dự án cung cấp sẵn kịch bản chạy thử nghiệm Terminal độc lập và bộ test case tự động:

### 2.1. Chạy nhanh kịch bản mô phỏng Terminal (Không cần cài thư viện ngoài)
Chạy giả lập đồng thời **3 Producers** và **2 Consumers** tranh chấp vùng nhớ đệm chung (Shared Memory Bounded Buffer), hiển thị Trace Log chi tiết và Báo cáo đối soát Oracle:
```bash
python3 tests/console_shm_test.py
```

### 2.2. Chạy bộ Unit Tests với Python Standard Library
Kiểm tra các trường hợp biên, tính an toàn Non-blocking, và mảng vòng Modulo:
```bash
python3 -m unittest discover tests
```

### 2.3. Chạy bộ kiểm thử tự động với `pytest`
```bash
# Chạy toàn bộ test suite
pytest

# Chạy test và hiển thị chi tiết log output từng testcase
pytest -v -s

# Chạy kiểm tra độ bao phủ mã nguồn (Coverage)
pytest --cov=src tests/
```

---

## 3. Tổng quan đề tài & Yêu cầu kỹ thuật

### 3.1. Tổng quan đề tài
Dự án hiện thực và trực quan hóa các cơ chế **Giao tiếp Liên tiến trình (IPC - Inter-Process Communication)** cơ bản trong Hệ điều hành:
1. **Pipes (Anonymous / Named Pipe):** Truyền tải dữ liệu dạng dòng luồng (stream-based), mô hình Producer - Consumer tuần tự.
2. **Shared Memory:** Vùng nhớ chung cho phép các tiến trình đọc/ghi trực tiếp với tốc độ cao, đồng bộ hóa bằng Mutex / Semaphore để tránh Race Condition.
3. **Message Queue:** Hàng đợi tin nhắn lưu trữ có cấu trúc theo dạng message-based, hỗ trợ phân loại độ ưu tiên (priority) và kích thước message độc lập.

**Mục tiêu trọng tâm:**
- Xây dựng ứng dụng **Desktop GUI** trực quan, mượt mà, không block giao diện.
- Trực quan hóa dữ liệu truyền nhận dạng hoạt ảnh (**Animation**) trên Canvas / `QGraphicsView`.
- Cung cấp cơ chế **Trace log** chi tiết từng bước, kiểm soát và mô phỏng các tình huống **xử lý lỗi** (Deadlock, Buffer Full/Empty, Timeout, Race Condition).
- Thực nghiệm đo lường hiệu năng (**Throughput**, **Latency**, **CPU**, **RAM**) giữa các cơ chế IPC thông qua biểu đồ so sánh.

### 3.2. Yêu cầu kỹ thuật & Ràng buộc bắt buộc

| Hạng mục | Quy định chi tiết |
| :--- | :--- |
| **Loại ứng dụng** | **Desktop GUI chạy trên Windows** (PyQt6). **CẤM Web App**, không chỉ làm console. |
| **Ngôn ngữ** | Python (3.11+). **Bắt buộc tách rời tầng logic thuật toán khỏi tầng UI** (UI Thread không bao giờ bị block / freeze). |
| **Dữ liệu I/O** | - **Input:** Nhập từ file `.csv` kịch bản mô phỏng (có validate dữ liệu nghiêm ngặt, input lỗi/rỗng không được crash chương trình).<br>- **Output:** Hiển thị kết quả trực tiếp trên GUI và xuất file log trace chi tiết ra `.csv`. |
| **Tính đúng & Oracle** | - Đối chiếu với pseudocode/giáo trình chuẩn hoặc một **Oracle tính tay**.<br>- Cung cấp bảng so sánh **Expected vs. Actual** cho: test thường, test biên, deadlock, tranh chấp tài nguyên (race condition), buffer overflow/underflow, timeout. |
| **Đo lường & Kiểm thử** | - Đầy đủ Unit Test, Integration Test, Stress Test.<br>- Benchmark hiệu năng (**Throughput**, **Latency**, **CPU/Memory**) trên nhiều kích thước dữ liệu (payload khác nhau); có phần giải thích độ phức tạp và giới hạn kỹ thuật. |

---

## 4. Công nghệ (Tech Stack) & Cấu trúc thư mục

### 4.1. Chốt công nghệ (Tech Stack)

| Thành phần | Công nghệ lựa chọn | Ghi chú & Lý do chọn |
| :--- | :--- | :--- |
| **Ngôn ngữ** | **Python (3.11+)** | Cú pháp rõ ràng, hỗ trợ đầy đủ các module IPC chuẩn (`multiprocessing`, `mmap`, `queue`, `threading`). |
| **Giao diện (GUI)** | **PyQt6** | Bộ công cụ Desktop GUI mạnh mẽ, hỗ trợ custom widget, layout linh hoạt và phân tách luồng mượt mà qua `QThread` / `pyqtSignal`. |
| **Mô phỏng & Đồ họa** | **QGraphicsView / Canvas** | Dùng để vẽ hoạt họa (animation) dữ liệu di chuyển qua Pipe và hiển thị trạng thái các block/ô nhớ Shared Memory theo thời gian thực. |
| **Vẽ biểu đồ** | **Matplotlib (nhúng PyQt6)** | Tích hợp trực tiếp lên giao diện để vẽ đồ thị phân tích & so sánh Throughput (msg/s, KB/s) và Latency (ms). |
| **Định dạng dữ liệu** | **Module `csv` chuẩn** | Đọc cấu hình/kịch bản test từ file `.csv` và xuất toàn bộ lịch sử trace log ra `.csv`. |
| **Kiểm thử (Testing)** | **pytest** | Thực thi Unit Test, Integration Test và kiểm thử đối chiếu với mô hình tính tay (Oracle Verification). |
| **Đo lường tài nguyên** | **psutil** | Thu thập thông số phần cứng (CPU %, Memory MB) khi chạy stress test/benchmark. |

### 4.2. Cấu trúc thư mục dự án

```text
he-dieu-hanh-2026/
├── .gitignore              # Bộ lọc file chuẩn cho dự án Python
├── requirements.txt        # Danh sách thư viện phụ thuộc (PyQt6, matplotlib, pytest, psutil)
├── MEMBER_WORKFLOW.md      # Quy chuẩn Git & Jira workflow cho thành viên
├── README.md               # Tài liệu tổng quan & hướng dẫn dự án
│
├── src/                    # Mã nguồn chính của ứng dụng
│   ├── core/               # Tầng Logic IPC (Shared Memory, Pipe, Message Queue)
│   │   ├── ipc_interface.py # Abstract class IIPCMechanism & IPCResult (HDH-22)
│   │   └── shared_memory.py # Bounded Buffer Circular Memory, Mutex & Semaphore (HDH-24)
│   ├── gui/                # Tầng Giao diện PyQt6 (Main Window, Widgets, Canvas/QGraphicsView)
│   ├── benchmark/          # Module đo lường Throughput, Latency, CPU, RAM
│   ├── utils/              # Module I/O (CSV Validator, CSV Logger, Exporter)
│   └── main.py             # Điểm khởi chạy ứng dụng (Entrypoint GUI)
│
├── docs/                   # Tài liệu thiết kế, báo cáo, pseudocode & phân tích Oracle
│   └── shared_memory_spec.md # Đặc tả kỹ thuật module Shared Memory (HDH-10)
│
├── data/
│   ├── input/              # File dữ liệu đầu vào (.csv) mẫu và kịch bản mô phỏng
│   │   └── sample_messages.csv
│   └── output/             # File log trace chi tiết (.csv) được sinh ra sau khi chạy
│
└── tests/                  # Kiểm thử tự động (Unit, Integration, Oracle Verification)
    ├── console_shm_test.py # Kịch bản mô phỏng đa luồng terminal & Trace log
    └── test_shared_memory.py # Bộ kiểm thử đơn vị tự động (unittest/pytest)
```

---

## 5. Thiết kế kiến trúc & Tính năng cốt lõi

### 5.1. Sơ đồ kiến trúc phân tầng (Decoupled Architecture)

```
+-------------------------------------------------------------+
|                      PyQt6 Desktop GUI                      |
|  - QGraphicsView / Canvas (Animation trực quan hóa IPC)      |
|  - Bảng điều khiển (Cấu hình, nạp CSV, nút Play/Pause/Step) |
|  - Bảng Log Trace & Dashboard biểu đồ Matplotlib            |
+------------------------------▲------------------------------+
                               │ pyqtSignal / Slots (Non-blocking)
+------------------------------▼------------------------------+
|                    Worker Thread (QThread)                  |
|  - Điều phối mô phỏng, kiểm soát tốc độ (Clock / Delay)     |
|  - Bắt lỗi runtime, ghi nhận Trace Log                      |
+------------------------------▲------------------------------+
                               │ Gọi hàm điều phối
+------------------------------▼------------------------------+
|                    Core IPC & Logic Layer                   |
|  +--------------------+  +--------------------+  +--------+ |
|  |     Shared Memory  |  |       Pipes        |  | Message| |
|  | (Mutex/Semaphores) |  | (Named/Anonymous)  |  |  Queue | |
|  +--------------------+  +--------------------+  +--------+ |
|  - Error Simulator: Deadlock, Buffer Full/Empty, Timeout    |
|  - Metrics Collector: Throughput & Latency Engine           |
+-------------------------------------------------------------+
```

### 5.2. Các tính năng cốt lõi
1. **Đa cơ chế IPC:** Chuyển đổi linh hoạt giữa Shared Memory, Pipe và Message Queue để so sánh trực tiếp.
2. **Animation mượt mà:** Thể hiện trực quan tiến trình đẩy dữ liệu vào đường ống (Pipe), nạp/đọc các slot nhớ (Shared Memory), và xếp hàng gói tin (Message Queue).
3. **Trace Log Engine:** Mỗi hành động (`PRODUCE/SEND`, `CONSUME/RECEIVE`, `LOCK`, `UNLOCK`, `WAIT`, `BLOCKED`) đều được gán timestamp, trạng thái bộ đệm và biến đồng bộ.
4. **Xử lý ngoại lệ & Tiêm lỗi mô phỏng (Error Injection):**
   - **Buffer Overflow:** Thử nghiệm đẩy dữ liệu khi dung lượng đệm đầy -> chuyển sang trạng thái `BLOCKED` tại Semaphore empty.
   - **Buffer Underflow:** Đọc dữ liệu khi hàng đợi/kênh rỗng -> chuyển sang trạng thái `BLOCKED` tại Semaphore full.
   - **Deadlock / Race Condition:** Thử nghiệm tranh chấp tài nguyên vùng nhớ chung khi thiếu khóa hoặc khóa chéo.
   - **Timeout:** Mô phỏng tình huống chờ quá thời hạn mà không nhận được tín hiệu giải phóng tài nguyên.

---

## 6. Định dạng dữ liệu I/O (CSV Specification)

### 6.1. Dữ liệu đầu vào (`data/input/*.csv`)
File kịch bản định nghĩa danh sách các thông điệp và tiến trình tham gia mô phỏng truyền nhận.

**Bảng đặc tả cấu trúc cột (Đã tinh gọn chuẩn hóa):**

| Cột | Kiểu dữ liệu | Bắt buộc | Mô tả & Ví dụ |
| :--- | :--- | :---: | :--- |
| `id` | `int` | Có | Mã định danh thông điệp / bước thực thi duy nhất (> 0), ví dụ: `1`, `2`. |
| `action` | `string` | Có | Lệnh thực thi của tiến trình: `PRODUCE` hoặc `CONSUME` (đối với Shared Memory / Pipe); `SEND` hoặc `RECEIVE` (đối với Message Queue). |
| `sender` | `string` | Có | Tên tiến trình gửi hoặc tiến trình thực hiện hành vi, ví dụ: `Process_A`, `P1`. |
| `receiver` | `string` | Có | Tên tiến trình nhận, ví dụ: `Process_B`, `C1`. |
| `message` | `string` | Tùy chọn | Nội dung thông điệp truyền nhận (ví dụ: `"Hello from Process A"`). Để trống khi `action` là `CONSUME` hoặc `RECEIVE`. |
| `delay_ms` | `int` | Không | Độ trễ giả lập trước khi thực hiện thao tác (ms, mặc định `0`). Dùng để điều phối tốc độ mô phỏng. |
| `priority` | `int` | Không | Độ ưu tiên gói tin (mặc định `0`, số càng lớn ưu tiên càng cao — áp dụng cho **Message Queue**). |

> [!NOTE]
> **Điểm tinh gọn so với bản nháp ban đầu:**
> - **Bổ sung cột `action`:** Định nghĩa rõ hành vi của tiến trình (`PRODUCE`/`CONSUME` hoặc `SEND`/`RECEIVE`), giúp Parser phân biệt chính xác tiến trình đang muốn nạp dữ liệu hay muốn rút dữ liệu khỏi buffer.
> - **Loại bỏ cột `payload_size_bytes`:** Dư thừa vì kích thước dữ liệu (bytes) được hệ thống tự động suy ra chính xác từ `len(message.encode('utf-8'))`, tránh tình trạng xung đột thông tin (ví dụ: khai báo 1024 bytes nhưng chuỗi tin nhắn chỉ có 10 ký tự).
> - **Loại bỏ cột `mechanism` trên từng dòng:** Cơ chế IPC (`SHARED_MEMORY`, `PIPE`, `MESSAGE_QUEUE`) là thuộc tính của toàn bộ phiên mô phỏng (được người dùng chọn trên GUI hoặc cấu hình thử nghiệm), không thể trộn lẫn các cơ chế khác nhau trên từng dòng thông điệp độc lập.
> - **Loại bỏ cột `simulate_error`:** Các trạng thái như `BUFFER_OVERFLOW` (Bộ đệm đầy) hay `DEADLOCK` là **hệ quả động (runtime behavior)** khi nhiều tiến trình chạy đồng thời, không phải là thuộc tính tĩnh của một thông điệp. Chức năng tiêm lỗi được kích hoạt trực tiếp từ bảng điều khiển GUI hoặc kịch bản kiểm thử tải (Stress test).

**Ví dụ nội dung file `data/input/sample_messages.csv`:**
```csv
id,action,sender,receiver,message,delay_ms,priority
1,PRODUCE,Process_A,Process_B,"Hello from Process A",50,0
2,CONSUME,Process_B,Process_A,"",30,0
3,PRODUCE,Process_A,Process_C,"Shared data block alpha",100,0
4,CONSUME,Process_C,Process_A,"",80,0
5,PRODUCE,Process_B,Process_C,"Queue message priority 1",20,1
6,CONSUME,Process_C,Process_B,"",40,0
7,PRODUCE,Process_A,Process_B,"Large buffer test message",150,0
```
Kiểm thử riêng parser: `python -m pytest tests/test_csv_parser.py -v`.

### 6.2. Dữ liệu đầu ra Trace Log (`data/output/trace_*.csv`)
Mỗi phiên chạy mô phỏng sẽ tự động xuất ra file log chi tiết theo từng bước, ghi lại chính xác trạng thái biến đồng bộ và bộ đệm (bằng chứng phục vụ kiểm chứng Oracle):

| Cột | Kiểu dữ liệu | Mô tả |
| :--- | :--- | :--- |
| `step` | `int` | Số thứ tự bước thực thi tích lũy (1, 2, 3,...). |
| `timestamp` | `string` | Thời gian thực thi chính xác (`HH:MM:SS.mmm`). |
| `process_id` | `string` | Tiến trình thực hiện hành động (`P1`, `C1`,...). |
| `action` | `string` | Hành vi thực hiện (`PRODUCE`, `CONSUME`, `LOCK`, `UNLOCK`, `WAIT`). |
| `status` | `string` | Trạng thái (`SUCCESS`, `BLOCKED`, `TIMEOUT`, `ERROR`). |
| `buffer_state` | `string` | Snapshot trạng thái các ô nhớ trong bộ đệm, ví dụ: `['M1', '_', '_', '_']`. |
| `sync_state` | `string` | Giá trị các biến đồng bộ hệ điều hành `(Mutex, Empty, Full)`. |
| `detail` | `string` | Diễn giải chi tiết thao tác (vị trí slot ghi/đọc, con trỏ in/out, lý do bị nghẽn). |

---

## 7. Tính đúng & Phương pháp Oracle (Verification)

Để chứng minh tính đúng đắn của giải thuật, nhóm sử dụng **Mô hình Oracle tính tay / Pseudocode chuẩn** để so sánh `Expected` và `Actual`:

### Bảng kịch bản kiểm thử mẫu:
| Mã Test Case | Loại kịch bản | Mô tả điều kiện đầu vào | Kết quả kỳ vọng (Expected) | Kết quả thực tế (Actual) | Đánh giá |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **TC-01** | Test thường (Pipe) | Gửi 100 thông điệp tuần tự qua Pipe | Nhận đủ 100 tin, đúng thứ tự FIFO, không lỗi | Đang cập nhật | Chờ test |
| **TC-02** | Test thường (Shared Memory) | Đọc/ghi vùng nhớ có Mutex & Semaphore | Không mất dữ liệu, không race condition | Đạt 100% (12/12 items truyền nhận nguyên vẹn qua Bounded Buffer) | **ĐẠT (PASSED)** |
| **TC-03** | Test biên (Edge) | Payload rỗng (0 bytes) hoặc gọi non-blocking khi buffer rỗng | Hệ thống từ chối an toàn với cờ `BLOCKED`, không crash | Trả về `IPCResult(status='BLOCKED')`, `is_blocked=True` | **ĐẠT (PASSED)** |
| **TC-04** | Tranh chấp (Contention) | Nhiều tiến trình cùng tranh chấp ô nhớ | Mutex ngăn chặn ghi đè, các tiến trình chờ theo queue | 3 Producers & 2 Consumers tranh chấp đồng thời an toàn, data nguyên vẹn | **ĐẠT (PASSED)** |
| **TC-05** | Deadlock Simulation | Khóa vòng tròn giữa 2 tiến trình (P1 giữ L1 đòi L2, P2 giữ L2 đòi L1) | Phát hiện Deadlock qua Timeout/Trace, thông báo lỗi GUI | Đang cập nhật | Chờ test |
| **TC-06** | Buffer Overflow | Gửi dữ liệu liên tục vào Queue/Buffer đã đầy | Trả về trạng thái `BLOCKED`, không làm treo luồng chính | Trả về cờ `BLOCKED` tại Semaphore empty khi buffer 4/4 | **ĐẠT (PASSED)** |

---

## 8. Đo lường & Benchmark hiệu năng

Ứng dụng cung cấp module Benchmark để đo lường và hiển thị trực tiếp lên biểu đồ Matplotlib:
- **Throughput (Thông lượng):** Số lượng message/giây và băng thông (KB/s, MB/s) đạt được trên từng cơ chế IPC.
- **Latency (Độ trễ):** Thời gian trung bình từ khi gửi đến khi nhận hoàn tất (microsecond / millisecond).
- **Tiêu thụ tài nguyên:** CPU Usage (%) và Memory Footprint (RAM MB) được đo đạc bằng thư viện `psutil`.
- **Kịch bản Stress Test:** Đánh giá hiệu năng dưới các kích thước payload tăng dần: 64B, 1KB, 64KB, 1MB, 10MB.

---

## 9. Quy trình làm việc nhóm (Workflow)

Thành viên dự án bắt buộc tuân thủ quy trình Git & Jira được quy định chi tiết tại **[MEMBER_WORKFLOW.md](file:///home/hnamhocit/Workspace/learning/he-dieu-hanh-2026/MEMBER_WORKFLOW.md)**:

- **1 Jira Task = 1 Feature Branch = 1 Pull Request**.
- Nhánh cơ sở: luôn xuất phát từ `develop`.
- Đặt tên branch: `feature/<JIRA-ID>-<short-name>`.
- Mọi thay đổi đều phải qua Pull Request và được Review trước khi merge.
