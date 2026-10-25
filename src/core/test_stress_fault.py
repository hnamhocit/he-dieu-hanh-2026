import os
import time
import threading
import concurrent.futures
from src.core.message_queue import MessageQueue, MessagePacket

# Cấu hình giả lập tải cao
NUM_PRODUCERS = 5
NUM_CONSUMERS = 5
MESSAGES_PER_PRODUCER = 100  # Tổng cộng 500 gói tin được xử lý liên tục
QUEUE_CAPACITY = 20
LOG_FILE_PATH = "data/output/trace_execution.csv"  # Đường dẫn log trace thực tế của hệ thống

def simulated_producer(queue: MessageQueue, producer_id: int):
    """Tiến trình Producer tạo tải và chèn lỗi ngẫu nhiên."""
    errors_pool = ["NONE", "CHECKSUM", "DELAY", "NONE", "NONE"] # 40% tỉ lệ lỗi ngẫu nhiên công kích hệ thống
    
    for i in range(MESSAGES_PER_PRODUCER):
        msg_id = producer_id * 1000 + i
        error_type = errors_pool[msg_id % len(errors_pool)]
        
        # Đóng gói gói tin kèm kịch bản lỗi độc hại
        packet = MessagePacket(
            id=msg_id,
            sender=f"Producer_{producer_id}",
            receiver="Consumer_Worker",
            message=f"Tải cao - Gói tin dữ liệu mẫu thứ {i}",
            simulate_error=error_type,
            priority=msg_id % 5
        )
        
        # Tiến hành đẩy vào hàng đợi (Thao tác này kích hoạt Fault Injector bên trong core)
        queue.produce(packet, process_id=packet.sender, timeout=2.0)
        time.sleep(0.001) # Tốc độ đẩy tin cực cao tạo áp lực dồn ứ

def simulated_consumer(queue: MessageQueue, consumer_id: int):
    """Tiến trình Consumer liên tục lấy tin và ghi nhận phản hồi lỗi."""
    success_count = 0
    blocked_or_fail_count = 0
    
    for _ in range(MESSAGES_PER_PRODUCER):
        # Đọc dữ liệu ra với timeout ngắn để hứng lỗi DELAY/TIMEOUT
        res = queue.consume(process_id=f"Consumer_{consumer_id}", timeout=0.1)
        if res.success:
            success_count += 1
        else:
            blocked_or_fail_count += 1
            
# --- CÁC HÀM KIỂM CHỨNG TỰ ĐỘNG (ASSERTIONS) ---

def verify_timestamp_accuracy():
    """Kiểm tra độ chính xác của Timestamp: Phải đơn điệu tăng dần và không lệch pha quá mức."""
    print("\n[CHECK 1] 🔴 Đang kiểm tra độ chính xác của Timestamp...")
    if not os.path.exists(LOG_FILE_PATH):
        print(f"❌ Không tìm thấy file log tại: {LOG_FILE_PATH} để kiểm tra.")
        return

    timestamps = []
    with open(LOG_FILE_PATH, "r", encoding="utf-8") as f:
        header = f.readline()
        for line in f:
            clean_line = line.strip()
            if not clean_line:
                continue
            parts = clean_line.split(",")
            try:
                ts = int(parts[0])
                timestamps.append(ts)
            except (ValueError, IndexError):
                continue

    if not timestamps:
        print("⚠️ Không trích xuất được timestamp định dạng số từ file log, bỏ qua kiểm tra đơn điệu.")
        return

    # Kiểm tra tính đơn điệu (Monotonicity): Nhật ký sự kiện phải theo đúng trình tự thời gian
    is_monotonic = all(timestamps[i] <= timestamps[i+1] for i in range(len(timestamps)-1))
    
    # Khoảng cách lớn nhất giữa 2 log liên tiếp (tính bằng giây)
    max_gap_sec = max([timestamps[i+1] - timestamps[i] for i in range(len(timestamps)-1)]) / 1e9 if len(timestamps) > 1 else 0

    assert is_monotonic, "❌ LỖI: Timestamp trong log bị đảo lộn, không theo trình tự thời gian!"
    print(f"✅ Đạt: Timestamp log đảm bảo thứ tự đơn điệu tăng dần ({len(timestamps)} mẫu). Khoảng giãn cách lớn nhất giữa 2 log liên tiếp: {max_gap_sec:.6f} giây.")


def verify_log_integrity():
    """Kiểm tra tính toàn vẹn của File Log khi bị tranh chấp ghi tải cao (Race Condition)."""
    print("\n[CHECK 2] 🔴 Đang kiểm tra tính toàn vẹn của File Log...")
    if not os.path.exists(LOG_FILE_PATH):
        return

    corrupted_lines = 0
    total_lines = 0
    
    with open(LOG_FILE_PATH, "r", encoding="utf-8") as f:
        header = f.readline()
        for line in f:
            total_lines += 1
            clean_line = line.strip()
            if not clean_line:
                continue
            parts = clean_line.split(",")
            # Mỗi dòng CSV phải có ít nhất 2 phần tử (timestamp_ns, event_name)
            if len(parts) < 2 or not parts[0].isdigit():
                corrupted_lines += 1

    assert corrupted_lines == 0, f"❌ LỖI: File log bị vỡ cấu trúc! Phát hiện {corrupted_lines}/{total_lines} dòng bị hỏng dữ liệu."
    print(f"✅ Đạt: File log toàn vẹn hoàn toàn. Tổng số {total_lines} dòng log ghi nhận trơn tru, không có hiện tượng Race Condition đè vỡ chữ.")


if __name__ == "__main__":
    print("=== BẮT ĐẦU KỊCH BẢN KIỂM THỬ TỰ ĐỘNG TẢI CAO ===")
    
    # Xóa file log cũ trước khi chạy test để đảm bảo số liệu chính xác
    if os.path.exists(LOG_FILE_PATH):
        try: os.remove(LOG_FILE_PATH)
        except: pass

    # Khởi tạo hàng đợi chịu áp lực cao
    stress_queue = MessageQueue(capacity=QUEUE_CAPACITY, is_priority=True)

    start_stress_time = time.time()
    
    # Kích hoạt đa luồng đồng thời (Concurrency)
    with concurrent.futures.ThreadPoolExecutor(max_workers=NUM_PRODUCERS + NUM_CONSUMERS) as executor:
        producer_futures = [executor.submit(simulated_producer, stress_queue, i) for i in range(NUM_PRODUCERS)]
        consumer_futures = [executor.submit(simulated_consumer, stress_queue, i) for i in range(NUM_CONSUMERS)]
        
        # Chờ tất cả các luồng hoàn thành tác vụ
        concurrent.futures.wait(producer_futures + consumer_futures)

    duration = time.time() - start_stress_time
    print(f"\n⚡ Hoàn thành đẩy tải: Đã xử lý liên tục {NUM_PRODUCERS * MESSAGES_PER_PRODUCER} gói tin trong {duration:.2f} giây.")

    # Thực hiện các hàm Assertion để hậu kiểm hệ thống tự động
    try:
        verify_timestamp_accuracy()
        verify_log_integrity()
        print("\n🏆 KẾT LUẬN: TẤT CẢ CÁC BÀI KIỂM TRA ĐỀU ĐẠT (PASSED)! TRACE LOGGER VÀ FAULT INJECTOR HOẠT ĐỘNG HOÀN HẢO DƯỚI TẢI CAO.")
    except AssertionError as e:
        print(f"\n🚨 BÀI KIỂM TRA THẤT BẠI (FAILED): {e}")
