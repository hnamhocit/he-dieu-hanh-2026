# ☑️ CHECKLIST TIÊU CHÍ CHẤM ĐIỂM BÀI TẬP LỚN HỆ ĐIỀU HÀNH

### 1. Quản lý Dự án & Repository (Git / Jira)
- [ ] Cấu trúc Repository đúng chuẩn đầy đủ các thư mục: src, data/input, data/output, docs.
- [ ] Thành viên commit đều đặn hàng tuần, message commit gắn kèm mã task Jira (Ví dụ: HDH-20: tao file csv...).
- [ ] Dự án không bị đóng băng (không có tiến triển) trong 3 tuần liên tiếp.
- [ ] File README.md hướng dẫn chi tiết cách cài đặt, cách chạy và mô tả định dạng file input CSV.

### 2. Yêu cầu Kỹ thuật & Sản phẩm Ứng dụng
- [ ] Ứng dụng Desktop có giao diện đồ họa GUI chạy trên Windows (Không làm Console/Web App).
- [ ] Sử dụng ngôn ngữ lập trình hợp lệ: C#, C++, Python hoặc Java.
- [ ] Phần xử lý thuật toán cốt lõi tách biệt rõ ràng khỏi mã nguồn giao diện GUI.
- [ ] Ứng dụng bẫy lỗi tốt, tuyệt đối không bị sập (crash) khi người dùng nhập dữ liệu hợp lệ.

### 3. Dữ liệu Đầu vào & Đầu ra (CSV)
- [ ] Đọc cấu hình đầu vào từ file .csv do nhóm tự định nghĩa (chứa đủ trường thông tin để tái lập kết quả).
- [ ] Có tính năng kiểm tra tính hợp lệ của dữ liệu đầu vào sau khi đọc file CSV.
- [ ] Kết quả hiển thị trực quan trên màn hình GUI và xuất được file log chi tiết ra file .csv.

### 4. Tính Đúng đắn & Kiểm thử (Testing)
- [ ] Kết quả chạy máy đối chiếu trực tiếp với mã giả, lưu đồ, giáo trình hoặc kết quả tính tay.
- [ ] Tài liệu Test Plan có bảng so sánh rõ ràng giữa Expected result và Actual result.
- [ ] Độ phủ bộ test gồm các trường hợp: thông thường, biên, hòa/bằng điểm, các trạng thái đặc thù (preemption, deadlock, page fault...).
- [ ] Thực hiện kiểm thử đầu vào rỗng/không hợp lệ, stress test và performance test trên nhiều kích thước dữ liệu.

### 5. Báo cáo, Video & Đánh giá Cá nhân
- [ ] Báo cáo dài 8-12 trang nội dung chính, có phân công rõ ràng và đồ thị phân tích hiệu năng.
- [ ] Có tối thiểu 4 nguồn tham khảo uy tín và trích dẫn đầy đủ (Khai báo rõ nếu có dùng AI).
- [ ] Video Demo chế độ công khai trình bày luồng chạy, dữ liệu và chạy thử ít nhất một test case.
- [ ] Cuối báo cáo có bảng đóng góp (Contribution statement). Thành viên hiểu sâu sắc phần việc mình phụ trách khi bảo vệ.