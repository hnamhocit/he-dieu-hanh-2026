### Bảng tổng hợp các kịch bản kiểm thử tích hợp ban đầu (Test Cases)

| STT | Mã Kịch Bản | Tên File Cấu Hình CSV | Mục Tiêu Kiểm Thử | Hành Động Khởi Chạy | Kết Quả Kỳ Vọng |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **1** | TC_INT_001 | normal_config.csv | Kiểm tra luồng tích hợp thông thường trong điều kiện lý tưởng. | INIT_SYSTEM, WRITE_SHM, SEND_MQ | Toàn bộ chuỗi trả về trạng thái SUCCESS. Bộ đệm ghi nhận đúng số lượng phần tử gia tăng. |
| **2** | TC_INT_002 | sample_config.csv | Kiểm tra tính ổn định của chuỗi nạp thông điệp mẫu cơ bản. | SETUP, PRODUCE_SHM, PRODUCE_MQ | Trả về trạng thái SUCCESS. Dữ liệu cấu hình được trích xuất chính xác. |
| **3** | TC_INT_003 | sample_messages.csv | Kiểm tra khả năng định tuyến và xử lý liên tục nhiều gói tin cùng lúc. | SEND_MQ (Liên tục nhiều dòng) | Trả về trạng thái SUCCESS. MessageQueue phân phối gói tin mượt mà không bị nghẽn luồng. |
| **4** | TC_INT_004 | edge_empty.csv | Kiểm tra điều kiện biên khi tệp cấu hình trống không chứa dòng lệnh. | Nạp file rỗng từ data/input/ | Hàm csv.DictReader bắt được lỗi file trống. Hệ thống ghi vết FAILED hoặc SKIPPED an toàn. |
| **5** | TC_INT_005 | invalid_format.csv | Kiểm tra khả năng chịu lỗi khi file cấu hình sai định dạng cột hoặc lỗi kiểu dữ liệu. | Nạp file lỗi định dạng | Khối lệnh try-except ép kiểu số nguyên bắt được ngoại lệ ValueError, gán giá trị mặc định (=0) và chạy tiếp. |
| **6** | TC_INT_006 | test_slots.csv | Kiểm tra thuật toán điều phối vị trí ghi trên cấu trúc mảng vòng. | WRITE_SHM (Ghi tuần tự dịch chuyển ô) | Các con trỏ _in_ptr và _out_ptr tịnh tiến chính xác theo công thức toán học modulo. |
| **7** | TC_INT_007 | test_slots_edges.csv | Kiểm tra cơ chế phi nghẽn khi cố tình bơm tràn dữ liệu vượt quá dung lượng. | WRITE_SHM / SEND_MQ liên tục vượt giới hạn (Capacity = 5) | Khi bộ đệm đầy, tham số timeout=0.0 kích hoạt cơ chế an toàn, trả về trạng thái BLOCKED chống treo giao diện. |