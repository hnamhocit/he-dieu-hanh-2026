# Mô Phỏng & Hiện Thực Trao Đổi Dữ Liệu Giữa Process (IPC)

> **Môn học:** Hệ điều hành  
> **Đề tài:** Mô phỏng hoặc hiện thực trao đổi dữ liệu giữa process bằng **Shared Memory**, **Pipe** hoặc **Message Queue**; có trace và xử lý lỗi.  
> **Nền tảng mục tiêu:** Desktop GUI (Windows / Cross-platform)

---

## 📌 Mục lục
- [1. Tổng quan đề tài](#1-tổng-quan-đề-tài)
- [2. Chốt công nghệ (Tech Stack)](#2-chốt-công-nghệ-tech-stack)
- [3. Yêu cầu kỹ thuật & Ràng buộc bắt buộc](#3-yêu-cầu-kỹ-thuật--ràng-buộc-bắt-buộc)
- [4. Cấu trúc thư mục dự án](#4-cấu-trúc-thư-mục-dự-án)
- [5. Thiết kế kiến trúc & Tính năng](#5-thiết-kế-kiến-trúc--tính-năng)
- [6. Định dạng dữ liệu I/O (CSV Specification)](#6-định-dạng-dữ-liệu-io-csv-specification)
- [7. Tính đúng & Phương pháp Oracle (Verification)](#7-tính-đúng--phương-pháp-oracle-verification)
- [8. Đo lường & Benchmark hiệu năng](#8-đo-lường--benchmark-hiệu-năng)
- [9. Hướng dẫn cài đặt & Chạy ứng dụng](#9-hướng-dẫn-cài-đặt--chạy-ứng-dụng)
- [10. Hướng dẫn kiểm thử (Testing)](#10-hướng-dẫn-kiểm-thử-testing)
- [11. Quy trình làm việc nhóm (Workflow)](#11-quy-trình-làm-việc-nhóm-workflow)

---

## 1. Tổng quan đề tài

Dự án hiện thực và trực quan hóa các cơ chế **Giao tiếp Liên tiến trình (IPC - Inter-Process Communication)** cơ bản trong Hệ điều hành:
1. **Pipes (Anonymous / Named Pipe):** Truyền tải dữ liệu dạng dòng luồng (stream-based), mô hình Producer - Consumer tuần tự.
2. **Shared Memory:** Vùng nhớ chung cho phép các tiến trình đọc/ghi trực tiếp với tốc độ cao, đồng bộ hóa bằng Mutex / Semaphore để tránh Race Condition.
3. **Message Queue:** Hàng đợi tin nhắn lưu trữ có cấu trúc theo dạng message-based, hỗ trợ phân loại độ ưu tiên (priority) và kích thước message độc lập.

**Mục tiêu trọng tâm:**
- Xây dựng ứng dụng **Desktop GUI** trực quan, mượt mà, không block giao diện.
- Trực quan hóa dữ liệu truyền nhận dạng hoạt ảnh (**Animation**) trên Canvas / `QGraphicsView`.
- Cung cấp cơ chế **Trace log** chi tiết từng bước, kiểm soát và mô phỏng các tình huống **xử lý lỗi** (Deadlock, Buffer Full/Empty, Timeout, Race Condition).
- Thực nghiệm đo lường hiệu năng (**Throughput**, **Latency**, **CPU**, **RAM**) giữa các cơ chế IPC thông qua biểu đồ so sánh.

---

## 2. Chốt công nghệ (Tech Stack)

| Thành phần | Công nghệ lựa chọn | Ghi chú & Lý do chọn |
| :--- | :--- | :--- |
| **Ngôn ngữ** | **Python (3.11+)** | Cú pháp rõ ràng, hỗ trợ đầy đủ các module IPC chuẩn (`multiprocessing`, `mmap`, `queue`, `threading`). |
| **Giao diện (GUI)** | **PyQt6** | Bộ công cụ Desktop GUI mạnh mẽ, hỗ trợ custom widget, layout linh hoạt và phân tách luồng mượt mà qua `QThread` / `pyqtSignal`. |
| **Mô phỏng & Đồ họa** | **QGraphicsView / Canvas** | Dùng để vẽ hoạt họa (animation) dữ liệu di chuyển qua Pipe và hiển thị trạng thái các block/ô nhớ Shared Memory theo thời gian thực. |
| **Vẽ biểu đồ** | **Matplotlib (nhúng PyQt6)** | Tích hợp trực tiếp lên giao diện để vẽ đồ thị phân tích & so sánh Throughput (msg/s, KB/s) và Latency (ms). |
| **Định dạng dữ liệu** | **Module `csv` chuẩn** | Đọc cấu hình/kịch bản test từ file `.csv` và xuất toàn bộ lịch sử trace log ra `.csv`. |
| **Kiểm thử (Testing)** | **pytest** | Thực thi Unit Test, Integration Test và kiểm thử đối chiếu với mô hình tính tay (Oracle Verification). |
| **Đo lường tài nguyên** | **psutil** | Thu thập thông số phần cứng (CPU %, Memory MB) khi chạy stress test/benchmark. |

---

## 3. Yêu cầu kỹ thuật & Ràng buộc bắt buộc

Dự án tuân thủ nghiêm ngặt bảng yêu cầu kỹ thuật:

| Hạng mục | Quy định chi tiết |
| :--- | :--- |
| **Loại ứng dụng** | **Desktop GUI chạy trên Windows** (PyQt6). **CẤM Web App**, không chỉ làm console. |
| **Ngôn ngữ** | Python (3.11+). **Bắt buộc tách rời tầng logic thuật toán khỏi tầng UI** (UI Thread không bao giờ bị block / freeze). |
| **Dữ liệu I/O** | - **Input:** Nhập từ file `.csv` do nhóm định nghĩa (có validate dữ liệu nghiêm ngặt, input lỗi/rỗng không được crash chương trình).<br>- **Output:** Hiển thị kết quả trực tiếp trên GUI và xuất file log trace chi tiết ra `.csv`. |
| **Tính đúng & Oracle** | - Đối chiếu với pseudocode/giáo trình chuẩn hoặc một **Oracle tính tay**.<br>- Cung cấp bảng so sánh **Expected vs. Actual** cho: test thường, test biên, deadlock, tranh chấp tài nguyên (race condition), buffer overflow/underflow, timeout. |
| **Đo lường & Kiểm thử** | - Đầy đủ Unit Test, Integration Test, Stress Test.<br>- Benchmark hiệu năng (**Throughput**, **Latency**, **CPU/Memory**) trên nhiều kích thước dữ liệu (payload khác nhau); có phần giải thích độ phức tạp và giới hạn kỹ thuật. |

---

## 4. Cấu trúc thư mục dự án

Hệ thống thư mục được tổ chức chuẩn hóa theo yêu cầu:

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
│   └── main.py             # Điểm khởi chạy ứng dụng (Entrypoint)
│
├── docs/                   # Tài liệu thiết kế, báo cáo, pseudocode & phân tích Oracle
│   └── shared_memory_spec.md # Đặc tả kỹ thuật module Shared Memory (HDH-10)
│
├── data/
│   ├── input/              # File dữ liệu đầu vào (.csv) mẫu và kịch bản mô phỏng
│   └── output/             # File log trace chi tiết (.csv) được sinh ra sau khi chạy
│
└── tests/                  # Kiểm thử tự động (Unit, Integration, Oracle Verification)
    ├── console_shm_test.py # Kịch bản mô phỏng đa luồng terminal & Trace log
    └── test_shared_memory.py # Bộ kiểm thử đơn vị tự động (unittest/pytest)
```

---

## 5. Thiết kế kiến trúc & Tính năng

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

### Các tính năng cốt lõi:
1. **Đa cơ chế IPC:** Chuyển đổi linh hoạt giữa Shared Memory, Pipe và Message Queue để so sánh trực tiếp.
2. **Animation mượt mà:** Thể hiện trực quan tiến trình đẩy dữ liệu vào đường ống (Pipe), nạp/đọc các slot nhớ (Shared Memory), và xếp hàng gói tin (Message Queue).
3. **Trace Log Engine:** Mỗi hành động (`SEND`, `RECEIVE`, `LOCK_ACQUIRE`, `LOCK_RELEASE`, `WAIT`, `DROPPED`) đều được gán timestamp, trạng thái và chi tiết lỗi.
4. **Xử lý ngoại lệ & Tiêm lỗi mô phỏng (Error Injection):**
   - **Buffer Overflow:** Thử nghiệm đẩy dữ liệu khi dung lượng đệm đầy.
   - **Buffer Underflow:** Đọc dữ liệu khi hàng đợi/kênh rỗng.
   - **Deadlock / Race Condition:** Thử nghiệm hai tiến trình đồng thời tranh chấp tài nguyên vùng nhớ chung khi thiếu khóa.
   - **Timeout / Packet Loss:** Mô phỏng mất mát gói tin hoặc trễ vượt ngưỡng.

---

## 6. Định dạng dữ liệu I/O (CSV Specification)

### 6.1. Dữ liệu đầu vào (`data/input/*.csv`)
File kịch bản định nghĩa các thông điệp và tiến trình tham gia mô phỏng:

| Cột | Kiểu dữ liệu | Mô tả |
| :--- | :--- | :--- |
| `id` | `int` | Mã định danh thông điệp (duy nhất, > 0) |
| `sender` | `string` | Tên tiến trình gửi (ví dụ: `Process_A`) |
| `receiver` | `string` | Tên tiến trình nhận (ví dụ: `Process_B`) |
| `mechanism` | `string` | Cơ chế IPC: `PIPE`, `SHARED_MEMORY`, hoặc `MESSAGE_QUEUE` |
| `payload_size_bytes` | `int` | Kích thước dữ liệu gửi (bytes) |
| `message` | `string` | Nội dung thông điệp |
| `delay_ms` | `int` | Độ trễ giả lập trước khi gửi (ms) |
| `simulate_error` | `string` | Lỗi giả lập: `NONE`, `BUFFER_OVERFLOW`, `DEADLOCK`, `TIMEOUT`, `CORRUPT` |

*Quy tắc Validation:* 
- Kiểm tra tính toàn vẹn của header và từng dòng.
- Nếu file rỗng, thiếu cột hoặc sai định dạng: hệ thống báo lỗi rõ ràng trên UI, không bị crash.

### 6.2. Dữ liệu đầu ra Trace Log (`data/output/trace_*.csv`)
Mỗi lần chạy sẽ xuất ra file log chi tiết:

| Cột | Kiểu dữ liệu | Mô tả |
| :--- | :--- | :--- |
| `timestamp` | `string` | Thời gian thực hiện (ISO format hoặc millisecond relative) |
| `step_index` | `int` | Số thứ tự bước mô phỏng |
| `process_id` | `string` | Tiến trình thực hiện hành vi |
| `action` | `string` | Hành động (`SEND`, `RECEIVE`, `LOCK`, `UNLOCK`, `WAIT`, `ERROR`) |
| `mechanism` | `string` | Cơ chế IPC tương ứng |
| `status` | `string` | `SUCCESS`, `PENDING`, `BLOCKED`, `FAILED` |
| `latency_ms` | `float` | Thời gian trễ hoàn thành thao tác |
| `detail` | `string` | Mô tả chi tiết hoặc thông tin lỗi |

---

## 7. Tính đúng & Phương pháp Oracle (Verification)

Để chứng minh tính đúng đắn của giải thuật, nhóm sử dụng **Mô hình Oracle tính tay / Pseudocode chuẩn** để so sánh `Expected` và `Actual`:

### Bảng kịch bản kiểm thử mẫu:
| Mã Test Case | Loại kịch bản | Mô tả điều kiện đầu vào | Kết quả kỳ vọng (Expected) | Kết quả thực tế (Actual) | Đánh giá |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **TC-01** | Test thường (Pipe) | Gửi 100 thông điệp tuần tự qua Pipe | Nhận đủ 100 tin, đúng thứ tự FIFO, không lỗi | Đang cập nhật | Chờ test |
| **TC-02** | Test thường (Shared Memory) | Đọc/ghi vùng nhớ có Mutex | Không mất dữ liệu, không race condition | Đạt 100% (12/12 items truyền nhận nguyên vẹn qua Bounded Buffer) | **ĐẠT (PASSED)** |
| **TC-03** | Test biên (Edge) | Payload rỗng (0 bytes) hoặc payload cực lớn (vượt buffer) | Hệ thống từ chối an toàn hoặc phân mảnh, không crash | Đang cập nhật | Chờ test |
| **TC-04** | Tranh chấp (Contention) | Nhiều tiến trình cùng ghi vào 1 ô nhớ | Mutex ngăn chặn ghi đè, các tiến trình chờ theo queue | 3 Producers & 2 Consumers tranh chấp đồng thời an toàn | **ĐẠT (PASSED)** |
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

## 9. Hướng dẫn cài đặt & Chạy ứng dụng

### Yêu cầu tiên quyết:
- Hệ điều hành: Windows 10/11 (hoặc Linux / macOS)
- Python: Phiên bản **3.11+**

### Các bước cài đặt:
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

3. **Cài đặt các thư viện cần thiết:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Khởi chạy ứng dụng GUI:**
   ```bash
   python src/main.py
   ```

---

## 10. Hướng dẫn kiểm thử (Testing)

### 10.1. Chạy nhanh mô phỏng Terminal (Không cần cài đặt thư viện ngoài):
Chạy kịch bản mô phỏng đồng thời 3 Producers và 2 Consumers với Trace log trực tiếp:
```bash
python3 tests/console_shm_test.py
```

### 10.2. Chạy bộ Unit Tests với Python standard library:
```bash
python3 -m unittest discover tests
```

### 10.3. Chạy bộ kiểm thử tự động với `pytest`:
```bash
# Chạy toàn bộ test suite
pytest

# Chạy test và hiển thị chi tiết log output
pytest -v -s

# Chạy kiểm tra độ bao phủ mã nguồn (Coverage)
pytest --cov=src tests/
```

---

## 11. Quy trình làm việc nhóm (Workflow)

Thành viên dự án bắt buộc tuân thủ quy trình Git & Jira được quy định chi tiết tại **[MEMBER_WORKFLOW.md](file:///home/hnamhocit/Workspace/learning/he-dieu-hanh-2026/MEMBER_WORKFLOW.md)**:

- **1 Jira Task = 1 Feature Branch = 1 Pull Request**.
- Nhánh cơ sở: luôn xuất phát từ `develop`.
- Đặt tên branch: `feature/<JIRA-ID>-<short-name>`.
- Mọi thay đổi đều phải qua Pull Request và được Review trước khi merge.