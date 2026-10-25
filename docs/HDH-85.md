# PHẦN 1: TỔNG QUAN VỀ BÀI TẬP LỚN / DỰ ÁN MÔ PHỎNG

---

## 1.1. BỐI CẢNH (CONTEXT)
Trong khoa học máy tính, hệ điều hành (HĐH) đóng vai trò là tầng trung gian quản lý và điều phối toàn bộ tài nguyên phần cứng, đồng thời cung cấp môi trường chạy ứng dụng. Tuy nhiên, việc trực tiếp can thiệp, theo dõi và đo lường các thuật toán quản trị tài nguyên (như lập lịch CPU, quản lý bộ nhớ, đồng bộ hóa tiến trình) trên một HĐH thực tế gặp nhiều rào cản: các cơ chế này chạy ở chế độ đặc quyền (Kernel Mode), có tốc độ xử lý hàng triệu lệnh/giây và bị che giấu bởi các thư viện hệ thống phức tạp. 

Dự án này được xây dựng nhằm thiết kế và triển khai một **chương trình mô phỏng (Simulation)** cấu trúc cốt lõi của một hệ điều hành. Bằng cách tái hiện lại các thuật toán kinh điển dưới dạng một ứng dụng phần mềm chạy trên tầng người dùng (User Mode), dự án giúp trực quan hóa, phân tích định lượng và đánh giá hiệu năng của các chiến lược quản lý tài nguyên trong các điều kiện tải khác nhau.

---

## 1.2. THUẬT NGỮ (TERMINOLOGY)
* **Tiến trình mô phỏng (Simulated Process / Job):** Một thực thể logic được chương trình tạo ra để đại diện cho một chương trình đang thực thi, sở hữu các thông số giả lập như CPU Burst Time, độ ưu tiên, dung lượng bộ nhớ yêu cầu.
* **CPU giả lập (Simulated CPU Core):** Bộ xử lý trung tâm trong môi trường mô phỏng, chịu trách nhiệm tiêu thụ "thời gian xử lý" (Burst Time) của các tiến trình theo từng chu kỳ tick (clock cycle).
* **Hàng đợi lập lịch (Scheduling Queues):** Tập hợp các danh sách liên kết hoặc mảng lưu trữ tiến trình ở các trạng thái khác nhau: *Ready Queue* (Sẵn sàng), *Waiting/Blocked Queue* (Chờ I/O).
* **Không gian địa chỉ giả lập (Simulated Address Space):** Vùng nhớ ảo được chia thành các Page (Trang) hoặc Segment (Phân đoạn) để cấp phát cho tiến trình mô phỏng.
* **Lỗi trang giả lập (Simulated Page Fault):** Sự kiện xảy ra khi tiến trình mô phỏng truy cập vào một trang dữ liệu không nằm trong "Bộ nhớ chính giả lập" (Simulated RAM), kích hoạt thuật toán thay thế trang (ví dụ: LRU, FIFO).
* **Thời gian hoàn thành (Turnaround Time):** Khoảng thời gian tính từ lúc tiến trình mô phỏng được nạp vào hệ thống cho đến khi nó kết thúc hoàn toàn.
* **Thời gian chờ (Waiting Time):** Tổng thời gian tiến trình phải nằm trong Ready Queue mà không được cấp phát CPU giả lập.

---

## 1.3. GIẢ ĐỊNH HỆ THỐNG (SYSTEM ASSUMPTIONS)
Để đơn giản hóa mô hình mô phỏng và tập trung vào bản chất thuật toán, hệ thống thiết lập các giả định sau:
1. **Tính đơn thể của tài nguyên:** CPU giả lập là một tài nguyên tuần tự tuyệt đối (đơn nhân hoặc đa nhân cố định), tại một thời điểm một lõi CPU chỉ xử lý duy nhất một tiến trình.
2. **Đơn vị thời gian đồng nhất:** Toàn bộ hệ thống vận hành dựa trên một đồng hồ đếm bước logic (Simulated Clock / Tick). Một đơn vị thời gian (1 tick) là nguyên tử và không thể bị chia cắt nhỏ hơn.
3. **Bỏ qua hao phí vận hành phần cứng (Zero Overhead):** Thời gian để hệ thống thực hiện chuyển đổi ngữ cảnh (Context Switch), tính toán chọn tiến trình tiếp theo, hoặc xử lý lỗi trang được giả định bằng **0 tick** (hoặc một hằng số cố định), không phụ thuộc vào độ phức tạp của dữ liệu.
4. **Bối cảnh tải tĩnh/động được kiểm soát:** Các tiến trình có thời điểm vào hệ thống (Arrival Time) và thời gian xử lý (Burst Time) được xác định rõ ràng trước qua file cấu hình hoặc trình sinh ngẫu nhiên theo phân phối xác suất biết trước.

---

## 1.4. ĐẦU VÀO VÀ ĐẦU RA (INPUT / OUTPUT)

### 1.4.1. Dữ liệu đầu vào (Input)
Hệ thống tiếp nhận dữ liệu từ hai nguồn chính (File cấu hình cấu trúc `.txt`/`.json` hoặc giao diện dòng lệnh/đồ họa):
* **Tham số cấu hình hệ thống:** Số lượng lõi CPU, thuật toán lập lịch sử dụng (FCFS, SJF, Round Robin, RR Quantum), dung lượng bộ nhớ vật lý, kích thước trang (Page Size), thuật toán thay thế trang.
* **Danh sách tiến trình (Job List):** Mảng các tiến trình với các trường dữ liệu bắt buộc: `Process_ID`, `Arrival_Time`, `CPU_Burst_Time`, `Memory_Requirement`, `Priority`.

### 1.4.2. Dữ liệu đầu ra (Output)
Chương trình trích xuất kết quả dưới dạng bảng biểu minh họa trực quan và file nhật ký (Log file):
* **Biểu đồ Gantt (Gantt Chart):** Chuỗi thời gian thể hiện rõ tiến trình nào đang chiếm giữ CPU tại mỗi mốc thời gian tick.
* **Nhật ký trạng thái (Tracer/Log):** Các dòng thông báo tường minh theo thời gian: `[Tick X]: Process P1 arrived`, `[Tick Y]: Process P2 preempted P1`, `[Tick Z]: Page Fault occurred at Page 4`.
* **Báo cáo hiệu năng (Performance Metrics):** 
  * Thời gian chờ trung bình (Average Waiting Time).
  * Thời gian hoàn thành trung bình (Average Turnaround Time).
  * Hiệu suất sử dụng CPU (CPU Utilization %).
  * Tỷ lệ lỗi trang (Page Fault Rate %).

---

## 1.5. PHẠM VI MÔ PHỎNG (SCOPE)
* **Nằm trong phạm vi (In-Scope):**
  * Mô phỏng logic dòng đời tiến trình (New $\rightarrow$ Ready $\rightarrow$ Running $\rightarrow$ Waiting $\rightarrow$ Terminated).
  * Cài đặt chính xác các thuật toán lập lịch CPU (Độc quyền và không độc quyền).
  * Mô phỏng cơ chế phân trang (Paging) và tính toán tỷ lệ lỗi trang dựa trên chuỗi truy cập trang (Page Reference String).
* **Nằm ngoài phạm vi (Out-of-Scope):**
  * Không tương tác với phần cứng thực tế (không truy cập RAM thật, không can thiệp CPU thật của máy tính đang chạy).
  * Không thực thi mã lệnh nhị phân thực sự của ứng dụng; tiến trình mô phỏng chỉ "ngủ" (sleep) hoặc giảm biến đếm chu kỳ để giả lập việc chạy.
  * Không xử lý các ngắt phần cứng (Hardware Interrupts) từ bàn phím, chuột hoặc card mạng thực tế.

---

## 1.6. PHÂN BIỆT RÕ RÀNG: MÔ PHỎNG VS. CƠ CHẾ THỰC TẾ CỦA HĐH

Để tránh nhầm lẫn trong báo cáo, bảng dưới đây phân tách ranh giới giữa phần mềm mô phỏng đang thực hiện và cơ chế vận hành thật sự của các HĐH hiện đại (như Linux, Windows):

| Đặc điểm so sánh | Môi trường mô phỏng (Dự án này) | Hệ điều hành thực tế (Linux / Windows) |
| :--- | :--- | :--- |
| **Tầng kiến trúc thực thi** | Chạy hoàn toàn trên **User Mode** dưới dạng một ứng dụng thông thường (viết bằng C/C++, Java, Python...). | Vận hành trực tiếp trên **Kernel Mode** (Ring 0), có đặc quyền tối cao thao tác với phần cứng. |
| **Khái niệm "Tiến trình"** | Là các **đối tượng/cấu trúc dữ liệu (Struct/Class)** chứa các thuộc tính giả lập nằm trong bộ nhớ của chương trình mô phỏng. | Là các thực thể quản lý bởi **Process Control Block (PCB)** thực tế của nhân (Kernel), có không gian địa chỉ cô lập do MMU phần cứng bảo vệ. |
| **Thực thi lệnh** | **Giả lập (Abstract Execution)**: Tiến trình tiêu thụ thời gian bằng cách giảm dần một biến đếm (ví dụ: `burst_time--`) sau mỗi vòng lặp. | **Thực thi thực tế (Physical Execution)**: CPU nạp các lệnh nhị phân của tiến trình từ RAM vào các thanh ghi và thực hiện tính toán vật lý. |
| **Cơ chế Lập lịch (Scheduling)** | Thực hiện bằng các **hàm điều hướng vòng lặp logic**. Việc chuyển ngữ cảnh chỉ là thay đổi con trỏ trỏ tới đối tượng tiến trình khác. | Sử dụng **ngắt đồng hồ phần cứng (Timer Interrupt)**. Chuyển ngữ cảnh (Context Switch) tốn chi phí lưu/xóa các thanh ghi, PC, SP và dọn dẹp bộ đệm TLB. |
| **Quản lý bộ nhớ** | Là một **mảng dữ liệu (Array)** đại diện cho RAM. Việc cấp phát hay lỗi trang chỉ là kiểm tra xem chỉ số mảng (Index) có hợp lệ hay không. | Phối hợp chặt chẽ với **bộ quản lý bộ nhớ phần cứng (MMU)** để dịch địa chỉ ảo sang địa chỉ vật lý, cấu hình các bảng trang (Page Tables) thực tế. |
| **Thời gian hệ thống** | **Thời gian logic (Discrete Ticks)**: Hệ thống tăng thời gian theo bước nhảy của vòng lặp `tick++`, hoàn toàn độc lập với thời gian thực tế bên ngoài. | **Thời gian thực (Real-time Clock)**: Đo bằng nano giây/mili giây dựa trên tần số dao động thạch anh của bo mạch chủ. |
