# 7. Kết luận, nguồn tham khảo và phụ lục

> **Mã nhiệm vụ Jira:** `HDH-118`
> **Người thực hiện:** Lê Hải Đăng

Mục này tổng kết kết quả đạt được, nêu các hạn chế còn tồn tại và hướng phát triển, liệt kê tài liệu tham khảo, khai báo việc sử dụng công cụ AI và cung cấp phụ lục để tái lập kết quả.

## 7.1. Kết luận

Nhóm đã xây dựng một ứng dụng desktop bằng Python và PyQt6 mô phỏng hai cơ chế trao đổi dữ liệu giữa các tiến trình là Shared Memory và Message Queue, có ghi vết vi sự kiện (trace) và bơm lỗi chủ động (fault injection). Các kết quả chính:

- **Shared Memory:** bộ đệm vòng dùng hai Semaphore đếm `empty`, `full` và một `mutex`. Producer và Consumer chiếm Semaphore đếm trước rồi mới chiếm `mutex` để tránh deadlock, và hoàn trả Semaphore (rollback) khi không chiếm được `mutex`.
- **Message Queue:** cài đặt theo mô hình Monitor gồm một `mutex` và hai biến điều kiện `not_full`, `not_empty`. Hàng đợi hỗ trợ FIFO và Priority; các gói tin cùng độ ưu tiên được xử lý theo thứ tự vào trước ra trước; kết quả phân biệt rõ `BLOCKED` và `TIMEOUT`.
- **Kiến trúc:** tầng thuật toán lõi tách khỏi giao diện qua interface `IIPCMechanism` với các phương thức `produce()`, `consume()` và `get_state()`. Giao diện nạp và kiểm tra file cấu hình CSV, hiển thị trạng thái từng ô nhớ, bảng trace theo thời gian thực, tab Benchmark & Analysis và xuất file trace CSV.
- **Kiểm chứng:** cả 10 kịch bản đối chiếu với Oracle tính tay đều đạt (Mục 4.1), trong đó kịch bản tiến trình bị crash khi đang giữ khóa đạt có điều kiện vì thời điểm mở khóa thực tế lệch so với mốc 300 ms lý thuyết. Script `tests/run_all_tests.py` chạy 127 test (83 unit, 40 tích hợp, 4 benchmark) không có test lỗi hay hỏng.
- **Hiệu năng:** với 1.000 gói tin, chạy ba lần trên tab Benchmark, Message Queue đạt khoảng 9.300 đến 11.400 gói/giây, độ trễ trung bình 0,72 đến 0,83 ms; Shared Memory đạt khoảng 3.500 đến 3.900 gói/giây, độ trễ trung bình 2,22 đến 2,46 ms.

Kết quả hiệu năng trên cần được đọc đúng bối cảnh. Trong bản mô phỏng, mỗi thao tác Shared Memory phải qua hai Semaphore và một `mutex` viết bằng Python, còn chi phí sao chép User ↔ Kernel của Message Queue không được mô phỏng (Mục 5.3). Vì vậy Message Queue nhanh hơn trong mô phỏng; điều này không mâu thuẫn với lý thuyết rằng trên hệ điều hành thật Shared Memory nhanh hơn khi dữ liệu lớn. Kết luận về trade-off ở Mục 5.4 vẫn giữ nguyên: Shared Memory đổi sự đơn giản và an toàn lấy tốc độ, Message Queue đổi tốc độ lấy thứ tự, độ ưu tiên và sự cô lập dữ liệu.

Qua đề tài, nhóm rút ra ba bài học chính: thứ tự chiếm khóa quyết định việc có xảy ra deadlock hay không; luồng chờ nên dùng timeout hữu hạn để tránh treo vô hạn; và giao diện phải dùng chế độ non-blocking để không bị đứng khi bộ đệm đầy hoặc rỗng.

## 7.2. Hạn chế và hướng phát triển

**Hạn chế**

- Producer và Consumer được mô phỏng bằng luồng trong cùng một tiến trình Python, không phải tiến trình riêng của hệ điều hành; cơ chế GIL của Python ảnh hưởng đến số đo hiệu năng.
- Chi phí hai lần sao chép User ↔ Kernel của Message Queue mới là mô hình lý thuyết, chưa có số đo thực nghiệm.
- Payload giới hạn tối đa 100 ký tự và benchmark trên giao diện dùng tải nhỏ, nên chưa phản ánh hành vi với khối dữ liệu lớn.
- Thời gian khôi phục khóa khi tiến trình bị crash lệch so với giá trị thiết kế 300 ms.

**Hướng phát triển**

- Hiện thực thêm phiên bản dùng IPC thật của hệ điều hành, như `multiprocessing.shared_memory` kết hợp Semaphore liên tiến trình và POSIX message queue (`mq_open`), để so sánh trực tiếp mô phỏng với thực tế.
- Đo hiệu năng với nhiều tiến trình và payload lớn, kết hợp công cụ hệ thống để đếm số lần chuyển ngữ cảnh và system call.
- Bổ sung các cơ chế IPC khác như pipe và socket theo cùng interface `IIPCMechanism` để so sánh trên cùng giao diện.
- Trực quan hóa phát hiện deadlock bằng đồ thị chờ (wait-for graph) và biểu đồ Gantt theo từng tiến trình.
- Chạy `tests/run_all_tests.py` tự động trên mỗi pull request bằng CI và đóng gói ứng dụng cho nhiều hệ điều hành.

## 7.3. Tài liệu tham khảo

1. A. Silberschatz, P. B. Galvin, G. Gagne, *Operating System Concepts*, 10th ed. Hoboken, NJ: Wiley, 2018. (Chương 3: Processes và IPC; Chương 6–7: Synchronization.)
2. A. S. Tanenbaum, H. Bos, *Modern Operating Systems*, 4th ed. Boston: Pearson, 2014. (Chương 2: Processes and Threads.)
3. IEEE and The Open Group, *IEEE Std 1003.1-2017 (POSIX.1-2017), The Open Group Base Specifications Issue 7*, 2018. Các hàm `shm_open`, `mmap`, `sem_wait`, `mq_open`, `mq_send`, `mq_receive`. Truy cập tại: <https://pubs.opengroup.org/onlinepubs/9699919799/>
4. M. Kerrisk, *The Linux Programming Interface*, San Francisco: No Starch Press, 2010. (Chương 51–54: POSIX IPC, message queue, semaphore, shared memory.)
5. R. H. Arpaci-Dusseau, A. C. Arpaci-Dusseau, *Operating Systems: Three Easy Pieces*, Arpaci-Dusseau Books, 2018. (Các chương Condition Variables và Semaphores.) Truy cập tại: <https://pages.cs.wisc.edu/~remzi/OSTEP/>
6. E. W. Dijkstra, *Cooperating Sequential Processes*, Technical Report EWD-123, Technological University Eindhoven, 1965. Truy cập tại: <https://www.cs.utexas.edu/~EWD/transcriptions/EWD01xx/EWD123.html>
7. Python Software Foundation, *threading: Thread-based parallelism*, Python 3 Documentation. Truy cập tại: <https://docs.python.org/3/library/threading.html>
8. Riverbank Computing, *PyQt6 Reference Guide*, tài liệu thư viện giao diện. Truy cập tại: <https://www.riverbankcomputing.com/static/Docs/PyQt6/>

## 7.4. Khai báo sử dụng AI

Theo yêu cầu của đề cương, nhóm khai báo việc sử dụng công cụ trí tuệ nhân tạo (AI) trong quá trình thực hiện đề tài. Quy tắc sử dụng AI của nhóm được ghi trong [`docs/HUONG_DAN_SU_DUNG_AI.md`](HUONG_DAN_SU_DUNG_AI.md).

| Công cụ | Mục đích sử dụng | Cách kiểm soát |
| --- | --- | --- |
| ChatGPT, Claude, Gemini | Giải thích khái niệm hệ điều hành, gợi ý và rà soát mã nguồn, hỗ trợ viết unit test, biên tập câu chữ tài liệu. | Nạp đúng file interface và file test làm ngữ cảnh; sửa trực tiếp trên file có sẵn; chạy toàn bộ unit test trước khi commit. |
| Claude Code | Đối chiếu Jira với lịch sử GitHub, hỗ trợ soạn Mục 6 (bảng đóng góp) và Mục 7. | Mọi số liệu, mã task và liên kết được kiểm tra lại với Jira, GitHub và kết quả chạy test của nhóm. |

Nhóm cam kết: thiết kế giải thuật, số liệu thực nghiệm và kết quả kiểm thử do nhóm tự thực hiện và kiểm chứng; AI chỉ đóng vai trò hỗ trợ. Mỗi thành viên chịu trách nhiệm về phần việc của mình, hiểu và giải thích được nội dung khi vấn đáp.

## 7.5. Phụ lục

### A. Liên kết sản phẩm

| Nội dung | Liên kết |
| --- | --- |
| Mã nguồn (GitHub) | <https://github.com/hnamhocit/he-dieu-hanh-2026> |
| Quản lý công việc (Jira) | [Dự án HDH trên Jira](https://hnamhocit.atlassian.net/jira/software/projects/HDH/list) |
| Video demo | [Video demo trên Google Drive](https://drive.google.com/file/d/1MO8VAnc0wXfTMEOw5fXiKHfJdAIvnBSK/view?usp=sharing) |
| Bản đóng gói Windows (.exe) | [Thư mục OS_IPC_09_Simulator trên Google Drive](https://drive.google.com/drive/folders/14hwbPLpyDXCkcFoKvYNo72GxU1Mn2aI6) |

### B. Cấu trúc thư mục

| Thư mục | Nội dung |
| --- | --- |
| `src/core` | Thuật toán lõi: Shared Memory, Message Queue, IPC Manager, Trace Logger, Fault Injector, benchmark, tính chỉ số và vẽ đồ thị. |
| `src/gui` | Giao diện PyQt6: cửa sổ chính, bộ điều khiển mô phỏng, tab Benchmark & Analysis. |
| `src/utils` | Bộ đọc và kiểm tra file cấu hình CSV. |
| `data/input`, `data/output` | File cấu hình đầu vào mẫu; file trace và kết quả benchmark xuất ra. |
| `tests` | Unit test, test tích hợp, stress test và script chạy toàn bộ `run_all_tests.py`. |
| `docs` | Đặc tả, Test Plan, Oracle tính tay và các mục báo cáo. |

### C. Lệnh tái lập kết quả

```bash
python -m venv venv
pip install -r requirements.txt
python src/main.py
python -m tests.run_all_tests
python -m tests.run_all_tests --full
```

Lệnh thứ ba mở giao diện. Lệnh thứ tư chạy toàn bộ test ở chế độ nhanh; thêm `--full` để chạy benchmark đầy đủ (ghi đè file kết quả trong `data/output`).
