# Câu hỏi vấn đáp nội bộ (Mock Defense) – HDH-122

## 1. Race condition
1. Race condition là gì? Cho một ví dụ cụ thể trong dự án.
2. Nhóm kiểm chứng hệ thống không có race condition bằng cách nào?
3. Nếu bỏ khóa khỏi hàm `produce`, theo bạn chuyện gì sẽ xảy ra khi 5 Producer chạy cùng lúc?

## 2. Lock (khóa)
4. Đoạn găng (critical section) là gì? Vì sao phải khóa?
5. Mutex khác Semaphore đếm ở điểm nào?
6. Trong Shared Memory, vì sao phải chiếm Semaphore đếm (`empty`, `full`) trước Mutex? Nếu làm ngược lại thì sao?
7. Rollback Semaphore là gì? Khi nào cần dùng?
8. Message Queue đồng bộ bằng cơ chế nào? Monitor là gì?
9. Vì sao khi chờ Condition phải dùng `WHILE` mà không dùng `IF`?
10. Vì sao tách thành hai Condition `not_full` và `not_empty` thay vì dùng một?
11. Deadlock là gì? Dự án đã tránh Deadlock như thế nào?

## 3. Zero-copy
12. Zero-copy là gì? Vì sao Shared Memory được gọi là gần như không sao chép dữ liệu?
13. Ở hệ điều hành thật, mỗi thông điệp trong Message Queue bị sao chép mấy lần và theo hướng nào?
14. Bản mô phỏng của nhóm có thực sự sao chép dữ liệu qua Kernel không? Vì sao?

## 4. Biên bộ đệm (buffer boundary)
15. Bộ đệm vòng (Circular Buffer) hoạt động thế nào? Con trỏ `in` và `out` thay đổi ra sao?
16. Chuyện gì xảy ra khi bộ đệm đầy? Khi rỗng? Hai tình huống này gọi là gì?
17. Tham số `timeout` bằng `0.0`, lớn hơn 0 và `None` khác nhau thế nào?
18. Vì sao Message Queue phân biệt `BLOCKED` với `TIMEOUT`?
19. Vì sao payload bị giới hạn 100 ký tự? Tầng Guard làm gì?

## 5. Context switch
20. Context switch là gì? Vì sao nó tốn chi phí?
21. Khi nào một luồng trong dự án bị đưa vào trạng thái chờ và gây ra context switch?
22. Benchmark đo context switch như thế nào? Vì sao trên Windows không đo được cột này?

## 6. Message Queue: thứ tự và ưu tiên
23. Priority Queue lấy gói tin theo thứ tự nào? Hai gói cùng độ ưu tiên thì ai ra trước?
24. Vì sao dùng `sequence` thay cho `timestamp` để phân xử hòa?
25. Message Queue xử lý lỗi thế nào? Kể tên vài mã lỗi.
26. Vì sao module không ném ngoại lệ ra ngoài mà trả về `IPCResult`?

## 7. Benchmark và thiết kế
27. Benchmark Message Queue đo những chỉ số nào? Với những mức payload nào?
28. Vì sao thông lượng giảm mạnh khi payload lên 1MB và 10MB?
29. Trong tab Benchmark của giao diện, Shared Memory chậm hơn Message Queue. Bạn giải thích thế nào? Có kết luận được "Message Queue nhanh hơn" không?
30. Vì sao phải tắt trace log khi đo benchmark?
31. Vì sao nhóm không dùng IPC thật của hệ điều hành (`shmget`, `mq_open`)?
32. Khi nào nên chọn Shared Memory, khi nào nên chọn Message Queue?

## Bảng ghi kết quả buổi tập

| Câu số | Người trả lời | Trả lời tốt? | Cần bổ sung |
| --- | --- | --- | --- |
|  |  |  |  |
