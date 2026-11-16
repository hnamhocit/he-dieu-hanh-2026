# 6. Quản lý nhóm và đóng góp

> **Mã nhiệm vụ Jira:** `HDH-117`
> **Người thực hiện:** Lê Hải Đăng

Đề tài mô phỏng trao đổi dữ liệu giữa các tiến trình bằng Shared Memory và Message Queue. Mục này trình bày cách nhóm tổ chức công việc, kế hoạch 8 tuần, bảng phân công và đóng góp của 5 thành viên, minh chứng trên GitHub và phần tự đánh giá rủi ro.

## 6.1. Tổ chức và phối hợp

Nhóm phân công công việc qua Jira và quản lý mã nguồn trên GitHub. Theo `MEMBER_WORKFLOW.md`, thành viên tạo nhánh `feature/<mã task>` từ `develop`, thực hiện task, mở pull request và chuyển task sang trạng thái chờ duyệt; trưởng nhóm review, yêu cầu chỉnh sửa nếu cần rồi merge vào `develop`. Nhánh `main` được bảo vệ, không cho push trực tiếp (HDH-7). Công việc được chia thành 5 sprint, mỗi sprint khoảng một tuần; trưởng nhóm Nguyễn Hoàng Nam theo dõi tiến độ Jira/Git và review code (HDH-23).

## 6.2. Kế hoạch 8 tuần

Bảng dưới tổng hợp kế hoạch theo tuần, đối chiếu với sprint trên Jira và số commit thực tế trên GitHub (tính trên mọi nhánh, gồm cả commit merge). Tuần 7 và 8 là phần kế hoạch còn lại đến khi nộp và bảo vệ.

| Tuần | Thời gian | Sprint | Nội dung chính | Task Jira | Commit |
| :---: | --- | --- | --- | --- | :---: |
| 1 | 12/10 – 18/10 | Sprint 1 | Tạo repo, quy trình Git; đặc tả Shared Memory và Message Queue; interface IIPCMechanism; khởi tạo GUI, wireframe, schema CSV, CSVParser; Test Plan, dữ liệu mẫu, Oracle tính tay; tối ưu Mutex. | HDH-6 → 34, 48, 49 | 44 |
| 2 | 19/10 – 25/10 | Sprint 2 | Trace Logger, Fault Injector và test tự động; khóa Circular Buffer, thuật toán Shared Memory; nối CSVParser vào Core; test case lỗi biên; Phần 1 báo cáo. | HDH-82 → 87, 90, 91 | 25 |
| 3 | 26/10 – 01/11 | Sprint 2 – 3 | Tie-breaking và thuật toán Message Queue; cập nhật Oracle cho ca biên; IPC Manager; xử lý ngoại lệ Message Queue; widget bộ nhớ và bảng log; metrics; kiểm thử tích hợp. | HDH-88, 89, 92, 93, 95, 97, 99, 101 | 20 |
| 4 | 02/11 – 08/11 | Sprint 3 – 4 | Hoàn thành báo cáo Mục 3.1 – 3.5; bắt đầu benchmark Shared Memory và Message Queue. | HDH-94, 96, 98, 100, 102 | 31 |
| 5 | 09/11 – 15/11 | Sprint 4 | Stress test và benchmark; sinh đồ thị; đối soát Oracle; báo cáo Mục 4 và 5; tab Benchmark trên GUI; hướng dẫn kiểm thử GUI. | HDH-103 → 112 | 22 |
| 6 | 16/11 – 22/11 | Sprint 5 | Rà soát code; kiểm thử repo sạch; đóng gói và video demo; script chạy toàn bộ test; tổng duyệt phản biện; báo cáo Mục 6, 7 và hợp nhất báo cáo. | HDH-113 → 122 | 14 |
| 7 | 23/11 – 29/11 | Kế hoạch | Rà soát báo cáo cuối, kiểm tra link demo và repo sạch, nộp bài. | — | — |
| 8 | 30/11 – 06/12 | Kế hoạch | Ôn tập theo bộ câu hỏi tổng duyệt, bảo vệ và vấn đáp. | — | — |

## 6.3. Bảng phân công và đóng góp

| Thành viên và vai trò | Nội dung đóng góp (mã task Jira) | Task hoàn thành |
| --- | --- | :---: |
| **Nguyễn Hoàng Nam**<br>074207005137<br>*Trưởng nhóm; kiến trúc và Shared Memory* | **Quản lý dự án: **tạo repo GitHub, thêm thành viên, đặt branch protection, .gitignore và cấu trúc thư mục (HDH-6, 7, 8, 9); theo dõi Jira/Git và review PR (HDH-23); hợp nhất và chuẩn hóa báo cáo (HDH-113).<br>**Thiết kế: **đặc tả cấu trúc và trạng thái đồng bộ Shared Memory (HDH-10); interface trừu tượng IIPCMechanism (HDH-22).<br>**Lập trình: **lõi Shared Memory với Mutex và Semaphore (HDH-24); khóa Circular Buffer, xử lý deadlock/starvation khi buffer đầy hoặc rỗng (HDH-86); IPC Manager điều phối Start, Pause, Stop, Reset và giải phóng tài nguyên (HDH-93); rà soát code base, bổ sung docstring, chuẩn PEP8 (HDH-114).<br>**Hiệu năng: **stress test Shared Memory với payload 64 B đến 10 MB (HDH-103).<br>**Báo cáo: **thuật toán Shared Memory (HDH-87); Mục 3.1 (HDH-94); Mục 5.1 và 5.2 (HDH-104). | **16/16** |
| **Lê Hải Đăng**<br>075207009780<br>*GUI và CSV Parser* | **Thiết kế: **khởi tạo project PyQt (HDH-16); wireframe giao diện (HDH-17); chốt schema file CSV với nhóm (HDH-18).<br>**Lập trình: **module CSVParser và kiểm tra hợp lệ (HDH-30); bắt ngoại lệ file rỗng, sai định dạng, thiếu cột (HDH-31); layout chính với nút Start, Pause, Reset (HDH-32); nối CSVParser vào Core và widget ô nhớ (HDH-90); bảng log thời gian thực (HDH-97); tab Benchmark & Analysis (HDH-110).<br>**Báo cáo: **Mục 3.3 (HDH-98); hướng dẫn kiểm thử GUI và ảnh minh chứng cho Mục 4 (HDH-111); Mục 6 (HDH-117); Mục 7 (HDH-118). | **13/13** |
| **Lương Hoài Sơn**<br>075207018633<br>*Message Queue* | **Thiết kế: **đặc tả MessagePacket và MessageQueue (HDH-13); chọn cơ chế FIFO/Priority, blocking/non-blocking (HDH-14); khai báo interface module (HDH-15).<br>**Lập trình: **MessageQueueCore (HDH-27); chế độ blocking và non-blocking (HDH-28); kiểm thử console hàng đợi đầy/rỗng (HDH-29); tie-breaking cho gói tin cùng priority (HDH-88); xử lý timeout, overflow, underflow (HDH-95).<br>**Hiệu năng và kiểm thử: **stress test Message Queue với cùng bộ tải như Shared Memory (HDH-112); script chạy toàn bộ test bằng một lệnh run_all_tests.py (HDH-121); tổ chức buổi tổng duyệt phản biện nội bộ (HDH-122).<br>**Báo cáo: **thuật toán Message Queue (HDH-89); Mục 3.2 (HDH-96); Mục 5.3 và 5.4 (HDH-105). | **14/14** |
| **Đỗ Tường Minh**<br>001207064067<br>*Trace, Fault Injection và chỉ số hiệu năng* | **Tối ưu: **giảm thời gian giữ Mutex (HDH-48); kiểm tra rò rỉ bộ nhớ và deadlock khi tăng số tiến trình (HDH-49).<br>**Lập trình: **Trace Logging Engine (HDH-82); Fault Injector (HDH-83); test tự động cho Trace Logger và Fault Injector (HDH-84); metrics_calculator.py (HDH-99); plot_benchmarks.py sinh đồ thị (HDH-106).<br>**Kiểm thử và demo: **kiểm thử repo sạch trên máy mới (HDH-115); kịch bản ca kiểm thử lỗi trong video demo (HDH-116).<br>**Báo cáo: **Phần 1 khung báo cáo (HDH-85); Mục 3.4 (HDH-100); Mục 4.2 (HDH-107). | **12/12** |
| **Huỳnh Thị Khánh Ly**<br>075307015477<br>*Kiểm thử và dữ liệu* | **Kế hoạch: **checklist tiêu chí chấm điểm (HDH-21); Test Plan tối thiểu 10 ca (HDH-19).<br>**Dữ liệu và Oracle: **file CSV mẫu (HDH-20); bộ dữ liệu normal, rỗng, sai định dạng (HDH-34); test case lỗi biên (HDH-91); Oracle tính tay (HDH-33) và cập nhật cho 5 ca biên (HDH-92).<br>**Kiểm thử: **kịch bản tích hợp test_integration_ipc.py (HDH-101); chạy toàn bộ test và đối soát Oracle (HDH-108); đóng gói và chạy thử giao diện ở nhiều độ phân giải (HDH-119).<br>**Demo: **quay và dựng video demo tổng thể (HDH-120).<br>**Báo cáo: **Mục 3.5 (HDH-102); Mục 4.1 (HDH-109). | **13/13** |

Mã task trong bảng là các task được giao cho từng thành viên trên Jira. Nhóm có tổng cộng 68 task và tất cả đã hoàn thành.

**Tuyên bố đóng góp (Contribution statement). **Cả 5 thành viên cùng tham gia thiết kế, lập trình, kiểm thử và viết báo cáo. Phần việc của mỗi người được ghi đúng theo bảng trên, đối chiếu với phân công trên Jira và lịch sử commit, pull request trên GitHub ở Mục 6.4. Mỗi thành viên chịu trách nhiệm về phần mình phụ trách và có thể giải thích được nội dung đó khi vấn đáp. Các thành viên đã đọc và thống nhất với bảng phân công này thông qua pull request của Mục 6.

## 6.4. Minh chứng đóng góp trên GitHub

Bảng dưới liệt kê commit hoặc pull request tiêu biểu của từng thành viên. Đường dẫn được ghi đầy đủ để vẫn tra cứu được khi báo cáo được in ra. Kho mã nguồn: [https://github.com/hnamhocit/he-dieu-hanh-2026](https://github.com/hnamhocit/he-dieu-hanh-2026).

| Thành viên | Minh chứng và đường dẫn |
| --- | --- |
| Nguyễn Hoàng Nam | IPC Manager và kiểm thử: [github.com/hnamhocit/he-dieu-hanh-2026/commit/15f7c15](https://github.com/hnamhocit/he-dieu-hanh-2026/commit/15f7c15)<br>Tài liệu kiến trúc Mục 3.1: [github.com/hnamhocit/he-dieu-hanh-2026/commit/2414923](https://github.com/hnamhocit/he-dieu-hanh-2026/commit/2414923)<br>Stress test Shared Memory và Message Queue: [github.com/hnamhocit/he-dieu-hanh-2026/commit/dcd7f16](https://github.com/hnamhocit/he-dieu-hanh-2026/commit/dcd7f16)<br>Phân tích độ phức tạp và chỉ số hiệu năng SHM: [github.com/hnamhocit/he-dieu-hanh-2026/commit/046f313](https://github.com/hnamhocit/he-dieu-hanh-2026/commit/046f313) |
| Lê Hải Đăng | GUI kết nối Core và trực quan ô nhớ: [github.com/hnamhocit/he-dieu-hanh-2026/commit/934fe3e](https://github.com/hnamhocit/he-dieu-hanh-2026/commit/934fe3e)<br>Tab Benchmark và kiểm thử (PR #53): [github.com/hnamhocit/he-dieu-hanh-2026/pull/53](https://github.com/hnamhocit/he-dieu-hanh-2026/pull/53)<br>Hướng dẫn GUI và ảnh minh chứng (PR #54): [github.com/hnamhocit/he-dieu-hanh-2026/pull/54](https://github.com/hnamhocit/he-dieu-hanh-2026/pull/54) |
| Lương Hoài Sơn | Xử lý ngoại lệ Message Queue (PR #48): [github.com/hnamhocit/he-dieu-hanh-2026/pull/48](https://github.com/hnamhocit/he-dieu-hanh-2026/pull/48)<br>Báo cáo so sánh SHM – MQ (PR #61): [github.com/hnamhocit/he-dieu-hanh-2026/pull/61](https://github.com/hnamhocit/he-dieu-hanh-2026/pull/61)<br>Benchmark stress test MQ (PR #62): [github.com/hnamhocit/he-dieu-hanh-2026/pull/62](https://github.com/hnamhocit/he-dieu-hanh-2026/pull/62)<br>Script chạy toàn bộ test (PR #73): [github.com/hnamhocit/he-dieu-hanh-2026/pull/73](https://github.com/hnamhocit/he-dieu-hanh-2026/pull/73)<br>Câu hỏi tổng duyệt phản biện (PR #74): [github.com/hnamhocit/he-dieu-hanh-2026/pull/74](https://github.com/hnamhocit/he-dieu-hanh-2026/pull/74) |
| Đỗ Tường Minh | Module tính chỉ số hiệu năng: [github.com/hnamhocit/he-dieu-hanh-2026/commit/a29b858](https://github.com/hnamhocit/he-dieu-hanh-2026/commit/a29b858)<br>Báo cáo trace protocol và fault injector: [github.com/hnamhocit/he-dieu-hanh-2026/commit/89a788c](https://github.com/hnamhocit/he-dieu-hanh-2026/commit/89a788c)<br>Module sinh đồ thị benchmark (PR #55): [github.com/hnamhocit/he-dieu-hanh-2026/pull/55](https://github.com/hnamhocit/he-dieu-hanh-2026/pull/55) |
| Huỳnh Thị Khánh Ly | Kiểm thử lỗi biên: [github.com/hnamhocit/he-dieu-hanh-2026/commit/a440297](https://github.com/hnamhocit/he-dieu-hanh-2026/commit/a440297)<br>Kịch bản kiểm thử tích hợp: [github.com/hnamhocit/he-dieu-hanh-2026/commit/766832e](https://github.com/hnamhocit/he-dieu-hanh-2026/commit/766832e)<br>Báo cáo kiểm chứng sai khác (PR #52): [github.com/hnamhocit/he-dieu-hanh-2026/pull/52](https://github.com/hnamhocit/he-dieu-hanh-2026/pull/52)<br>Đóng gói và chạy thử giao diện (PR #71): [github.com/hnamhocit/he-dieu-hanh-2026/pull/71](https://github.com/hnamhocit/he-dieu-hanh-2026/pull/71)<br>Video demo (PR #75): [github.com/hnamhocit/he-dieu-hanh-2026/pull/75](https://github.com/hnamhocit/he-dieu-hanh-2026/pull/75) |

Phân công và trạng thái task trên Jira: [https://hnamhocit.atlassian.net/jira/software/projects/HDH/list](https://hnamhocit.atlassian.net/jira/software/projects/HDH/list).

## 6.5. Tự đánh giá rủi ro

Trong quá trình thực hiện, nhóm đã nhận diện các rủi ro sau và có biện pháp xử lý tương ứng.

| Rủi ro | Mức độ | Biện pháp | Kết quả |
| --- | :---: | --- | --- |
| Code do AI sinh ra lệch kiến trúc chung, tạo file trùng hoặc làm vỡ unit test (đã xảy ra ở Sprint 1). | Cao | Viết cẩm nang sử dụng AI: bắt buộc nạp file interface và file test làm ngữ cảnh, không tạo file mới ở thư mục gốc, chạy toàn bộ test trước khi commit. | Đã khắc phục từ Sprint 2 |
| Race condition hoặc deadlock khi nhiều Producer/Consumer cùng truy cập bộ đệm. | Cao | Chiếm Semaphore đếm trước Mutex, rollback khi không chiếm được Mutex; dùng Monitor cho Message Queue; stress test và test kiểm tra rò rỉ, deadlock (HDH-49). | Đã kiểm soát |
| Giao diện bị đứng khi bộ đệm đầy hoặc rỗng. | Trung bình | Chế độ non-blocking (timeout = 0) cho thao tác từ GUI, chạy mô phỏng ở luồng nền. | Đã khắc phục |
| Xung đột code khi 5 người cùng sửa một repo. | Trung bình | Branch protection cho main, mỗi task một nhánh feature, merge qua pull request có review. | Đã kiểm soát |
| Sai lệch thời gian khôi phục khi tiến trình bị crash so với thiết kế 300 ms. | Thấp | Ghi nhận ở Mục 4.1, nêu trong hạn chế ở Mục 7.2. | Chấp nhận, đã ghi nhận |
| Ứng dụng không chạy được trên máy khác do thiếu thư viện. | Trung bình | requirements.txt, hướng dẫn trong README, kiểm thử repo sạch trên máy mới (HDH-115), script chạy toàn bộ test (HDH-121). | Đã kiểm soát |
| Dồn việc vào cuối kỳ, trễ hạn nộp. | Trung bình | Chia 5 sprint khoảng một tuần, trưởng nhóm theo dõi Jira hằng tuần; dành tuần 7 – 8 để rà soát và ôn tập. | Đang theo dõi |
| Link video demo hoặc bản đóng gói không mở được khi giảng viên chấm. | Thấp | Kiểm tra quyền chia sẻ công khai của mọi link Google Drive trước khi nộp. | Kiểm tra trước khi nộp |
